"""
LEGACY - Recomendador anterior basado en similitud coseno.

Este script pertenece a la versión original del proyecto y no es compatible
con el esquema actual de la base de datos, ya que utiliza el modelo
Recommendation, eliminado durante la adaptación de la reevaluación.

El sistema de recomendación actual se implementará mediante Apriori y las
entidades AprioriRun, AssociationRule y AssociationRuleTarget.

Se conserva únicamente como referencia histórica de la evolución del proyecto.
"""

import os
import django
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "casa_cultura.settings")
django.setup()

from app.models import Rating, Recommendation, LibraryUser, Book

print("Cargando valoraciones desde SQLite...")
qs = Rating.objects.values_list('user__user_id', 'copy__book__book_id', 'rating')
df = pd.DataFrame(list(qs), columns=['user_id', 'book_id', 'rating'])
print(f"{len(df)} valoraciones cargadas")

users = df['user_id'].unique()
books = df['book_id'].unique()

user_map = {u: i for i, u in enumerate(users)}
book_map = {b: i for i, b in enumerate(books)}
rev_book_map = {i: b for b, i in book_map.items()}

row = df['user_id'].map(user_map).values
col = df['book_id'].map(book_map).values

sparse_matrix = csr_matrix((df['rating'].values, (row, col)), shape=(len(users), len(books)))

print("Entrenando modelo (similitud coseno item-item)...")
item_sim = cosine_similarity(sparse_matrix.T, dense_output=True)

print("Cargando géneros por libro...")
book_genre_map = {}
if os.path.exists('data/books_with_genre.csv'):
    df_g = pd.read_csv('data/books_with_genre.csv', encoding='utf-8-sig', usecols=['book_id', 'genre'])
    df_g = df_g.dropna(subset=['genre'])
    book_genre_map = dict(zip(df_g['book_id'].astype(int), df_g['genre'].str.strip()))

# índice invertido: género → conjunto de columnas de libro
genre_to_cols = defaultdict(set)
for col_idx, ext_id in rev_book_map.items():
    g = book_genre_map.get(ext_id)
    if g:
        genre_to_cols[g].add(col_idx)

print("Cargando preferencias de género por usuario...")
user_genre_map = {}
for uid, comment in LibraryUser.objects.values_list('user_id', 'comment'):
    if comment and comment not in ('nan', 'None', ''):
        generos = [g.strip() for g in comment.split(',') if g.strip()]
        if generos:
            user_genre_map[uid] = generos

print(f"  {len(user_genre_map)} usuarios con géneros preferidos")

book_pk_map = dict(Book.objects.values_list('book_id', 'pk'))
user_pk_map = dict(LibraryUser.objects.values_list('user_id', 'pk'))

print("Borrando recomendaciones antiguas...")
Recommendation.objects.all().delete()

print("Guardando recomendaciones en BD...")
batch = []
BATCH = 5000

for start in range(0, len(users), 2000):
    end = min(start + 2000, len(users))
    chunk = sparse_matrix[start:end]
    scores = chunk.dot(item_sim)
    scores[chunk.nonzero()] = 0  # excluir libros ya leidos

    # boost del 30% para libros del género favorito del usuario
    for i in range(end - start):
        uid = users[start + i]
        user_genres = user_genre_map.get(uid, [])
        if user_genres:
            cols_boost = set()
            for g in user_genres:
                cols_boost |= genre_to_cols.get(g, set())
            if cols_boost:
                scores[i, list(cols_boost)] *= 1.3

    top5 = np.argsort(-scores, axis=1)[:, :5]

    for i, top_idx in enumerate(top5):
        uid = users[start + i]
        user_pk = user_pk_map.get(uid)
        if not user_pk:
            continue
        for j in top_idx:
            s = float(scores[i, j])
            if s <= 0:
                continue
            book_pk = book_pk_map.get(rev_book_map[j])
            if not book_pk:
                continue
            batch.append(Recommendation(user_id=user_pk, book_id=book_pk, score=s))

        if len(batch) >= BATCH:
            Recommendation.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []

if batch:
    Recommendation.objects.bulk_create(batch, ignore_conflicts=True)

print("Listo. Recomendaciones guardadas en SQLite.")
