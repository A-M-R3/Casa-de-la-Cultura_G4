import time
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import AprioriRun, AssociationRule, AssociationRuleTarget, Rating, Book

class Command(BaseCommand):
    help = 'Pipeline optimizado de Apriori para generar recomendaciones en la Casa de la Cultura.'

    def handle(self, *args, **options):
        # [VÍDEO - KEYWORD: EXTRACCIÓN Y FILTRADO POSITIVO EN BBDD]
        # Filtramos valoraciones >= 4 para eliminar ruido de lecturas que no gustaron
        self.stdout.write(self.style.NOTICE("Extrayendo valoraciones positivas (rating >= 4) desde PostgreSQL..."))
        start_time = time.time()

        qs = Rating.objects.filter(rating__gte=4).values_list('user_id', 'copy__book_id')
        df = pd.DataFrame(list(qs), columns=['user_id', 'book_id']).drop_duplicates()

        if df.empty:
            self.stdout.write(self.style.ERROR("No hay suficientes valoraciones para entrenar."))
            return

        # [VÍDEO - KEYWORD: MATRIZ DE TRANSACCIONES BINARIAS]
        # pd.crosstab con bool minimiza el consumo de RAM a < 500 MB
        self.stdout.write("Transformando datos en matriz One-Hot optimizada...")
        basket_sets = pd.crosstab(df['user_id'], df['book_id']).astype(bool)

        # [VÍDEO - KEYWORD: APRIORI CON SOPORTE 1% Y MAX_LEN 3]
        # max_len=3 permite combinaciones A => B, C y optimiza el tiempo de cálculo
        self.stdout.write("Calculando itemsets frecuentes (soporte min: 1%, max_len: 3)...")
        min_support = 0.01
        frequent_itemsets = apriori(
            basket_sets, 
            min_support=min_support, 
            use_colnames=True, 
            max_len=3, 
            low_memory=True
        )

        # [VÍDEO - KEYWORD: GENERACIÓN Y FILTRADO DE REGLAS]
        # Filtro de confianza >= 30% y lift > 1 para asociaciones de alta afinidad
        self.stdout.write("Extrayendo reglas de asociación...")
        min_confidence = 0.30
        rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
        
        if not rules.empty:
            rules = rules[rules['lift'] > 1.0]
            rules['antecedent_len'] = rules['antecedents'].apply(lambda x: len(x))
            rules['consequent_len'] = rules['consequents'].apply(lambda x: len(x))
            # Restricción: Libro A => [Libro B] o Libro A => [Libro B, Libro C]
            rules = rules[(rules['antecedent_len'] == 1) & (rules['consequent_len'] <= 2)]
        
        execution_time = time.time() - start_time
        total_rules = len(rules)
        self.stdout.write(self.style.SUCCESS(f"Generación finalizada en {execution_time:.2f}s. Reglas aptas: {total_rules}"))

        # [VÍDEO - KEYWORD: INTROSPECCIÓN DINÁMICA DE CAMPOS DEL MODELO]
        # Identificamos automáticamente los nombres de ForeignKey definidos en models.py
        fk_book_rule = next(f for f in AssociationRule._meta.fields if f.is_relation and issubclass(f.related_model, Book))
        fk_book_target = next(f for f in AssociationRuleTarget._meta.fields if f.is_relation and issubclass(f.related_model, Book))
        fk_rule_target = next(f for f in AssociationRuleTarget._meta.fields if f.is_relation and issubclass(f.related_model, AssociationRule))

        # [VÍDEO - KEYWORD: PERSISTENCIA ATÓMICA Y ESCRITURA MASIVA]
        # Uso de bulk_create para insertar en lotes dentro de una transacción atómica
        self.stdout.write("Persistiendo ejecuciones y reglas en PostgreSQL...")
        with transaction.atomic():
            AprioriRun.objects.filter(is_active=True).update(is_active=False)

            run = AprioriRun.objects.create(
                min_support=min_support,
                min_confidence=min_confidence,
                min_lift=1.0,
                max_len=3,
                min_rating=4,
                is_active=True
            )

            rules_to_create = []
            for _, row in rules.iterrows():
                antecedent_id = list(row['antecedents'])[0]
                rule_kwargs = {
                    'run': run,
                    fk_book_rule.attname: antecedent_id,
                    'support': row['support'],
                    'confidence': row['confidence'],
                    'lift': row['lift']
                }
                rules_to_create.append(AssociationRule(**rule_kwargs))

            created_rules = AssociationRule.objects.bulk_create(rules_to_create, batch_size=1000)

            targets_to_create = []
            for rule_obj, (_, row) in zip(created_rules, rules.iterrows()):
                consequents = list(row['consequents'])
                for target_id in consequents:
                    target_kwargs = {
                        fk_rule_target.attname: rule_obj.id,
                        fk_book_target.attname: target_id
                    }
                    targets_to_create.append(AssociationRuleTarget(**target_kwargs))
            
            AssociationRuleTarget.objects.bulk_create(targets_to_create, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(f"¡Persistencia completada! {total_rules} reglas guardadas en PostgreSQL."))