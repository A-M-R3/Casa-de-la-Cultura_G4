from django.test import TestCase
from app.models import Book, Author, AprioriRun, AssociationRule, AssociationRuleTarget

class RecommendationSystemTestCase(TestCase):
    def setUp(self):
        # 1. Crear entorno y libros de prueba
        self.author = Author.objects.create(name="J.K. Rowling")
        
        self.book1 = Book.objects.create(
            book_id=90001,
            title="Harry Potter and the Sorcerer's Stone",
            publication_year=1997
        )
        self.book1.authors.add(self.author)

        self.book2 = Book.objects.create(
            book_id=90002,
            title="Harry Potter and the Chamber of Secrets",
            publication_year=1998
        )
        self.book2.authors.add(self.author)

        # 2. Registrar ejecución de Apriori
        self.run = AprioriRun.objects.create(
            min_support=0.01,
            min_confidence=0.30,
            min_lift=1.0,
            min_rating=4,
            max_len=3,
            is_active=True,
            transactions_count=53424,
            rules_count=1
        )

        # 3. Crear regla de asociación
        self.rule = AssociationRule.objects.create(
            run=self.run,
            source_book=self.book1,
            support=0.015,
            confidence=0.85,
            lift=12.5
        )

        # 4. Vincular consecuente
        AssociationRuleTarget.objects.create(
            rule=self.rule,
            book=self.book2
        )

    def test_rule_association_integrity(self):
        """Verifica que el libro antecedente recupera correctamente sus consecuentes."""
        rule = AssociationRule.objects.get(id=self.rule.id)
        self.assertEqual(rule.source_book.title, "Harry Potter and the Sorcerer's Stone")
        targets = [t.book.title for t in rule.targets.all()]
        self.assertIn("Harry Potter and the Chamber of Secrets", targets)

    def test_lift_threshold_validity(self):
        """Valida que no existan reglas con Lift menor que 1.0 (independencia estocástica)."""
        rule = AssociationRule.objects.get(id=self.rule.id)
        self.assertGreaterEqual(rule.lift, 1.0)

    def test_dashboard_url_status(self):
        """Comprueba que el endpoint del dashboard responde con código HTTP 200."""
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_inspector_search_simulation(self):
        """Comprueba la búsqueda interactiva del inspector de recomendaciones."""
        response = self.client.get('/dashboard/?q_inspect=Harry')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Harry Potter and the Chamber of Secrets")