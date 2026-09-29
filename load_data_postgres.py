import os
import csv
import django
from datetime import datetime
from django.db import connection

# Configuración de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "casa_cultura.settings")
django.setup()

from app.models import Book, Author, Copy, LibraryUser, Rating


# Tamaño de los lotes para inserciones masivas.
# 50.000 ofrece un buen equilibrio entre rendimiento y consumo de memoria.
BATCH_SIZE = 50000

# None = cargar todos los ratings.
# Para pruebas se puede poner, por ejemplo, 100000.
LIMITE_RATINGS = None


def parse_date(value):
    """
    Convierte las fechas de los CSV a objetos date.
    Admite los formatos utilizados en los datos originales.
    """
    if not value:
        return None

    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


# ==========================================================
# COMPROBACIÓN DE BASE DE DATOS
# ==========================================================

if connection.vendor != "postgresql":
    raise RuntimeError(
        "Este script está diseñado para PostgreSQL. "
        f"Backend detectado: {connection.vendor}"
    )


print("Iniciando carga rápida de datos en PostgreSQL...")
print(f"Base de datos: {connection.settings_dict['NAME']}")
print(f"Usuario: {connection.settings_dict['USER']}")
print(f"Host: {connection.settings_dict['HOST']}")
print()


# ==========================================================
# LIMPIEZA
# ==========================================================

print("Limpiando datos anteriores...")

Rating.objects.all().delete()
Copy.objects.all().delete()

# Elimina las relaciones ManyToMany libro-autor.
Book.authors.through.objects.all().delete()

Book.objects.all().delete()
Author.objects.all().delete()
LibraryUser.objects.all().delete()

print("Datos anteriores eliminados.")


# ==========================================================
# USUARIOS
# ==========================================================

print("Cargando usuarios...")

users = []

with open("data/users_clean.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        try:
            users.append(
                LibraryUser(
                    user_id=int(row["user_id"]),
                    comment=row.get("comentario") or "",
                    birth_date=parse_date(row.get("fecha_nacimiento")),
                )
            )
        except Exception:
            continue


LibraryUser.objects.bulk_create(
    users,
    batch_size=BATCH_SIZE,
    ignore_conflicts=True,
)

print(f"Usuarios cargados: {LibraryUser.objects.count()}")


# ==========================================================
# LIBROS
# ==========================================================

print("Cargando libros...")

books = []

with open("data/books_with_genre.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        try:
            year = row.get("original_publication_year") or None

            books.append(
                Book(
                    book_id=int(row["book_id"]),
                    isbn=row.get("isbn") or None,
                    title=row.get("title") or "",
                    original_title=row.get("original_title") or None,
                    publication_year=int(float(year)) if year else None,
                    language_code=row.get("language_code") or None,
                )
            )
        except Exception:
            continue


Book.objects.bulk_create(
    books,
    batch_size=BATCH_SIZE,
    ignore_conflicts=True,
)

print(f"Libros cargados: {Book.objects.count()}")


# ==========================================================
# AUTORES
# ==========================================================

print("Cargando autores...")

author_names = set()
book_author_rows = []

with open(
    "data/book_authors_extended.csv",
    newline="",
    encoding="utf-8"
) as f:

    reader = csv.DictReader(f)

    for row in reader:
        try:
            book_id = int(row["book_id"])
            author_name = row["author"].strip()

            if not author_name:
                continue

            author_names.add(author_name)
            book_author_rows.append(
                (book_id, author_name)
            )

        except Exception:
            continue


Author.objects.bulk_create(
    [Author(name=name) for name in author_names],
    batch_size=BATCH_SIZE,
    ignore_conflicts=True,
)


# Relación entre identificador externo y PK interna de Django
books_by_book_id = {
    book.book_id: book.id
    for book in Book.objects.only("id", "book_id")
}

authors_by_name = {
    author.name: author.id
    for author in Author.objects.only("id", "name")
}


# Creamos las relaciones ManyToMany libro-autor
through_model = Book.authors.through
relations = []

for book_id, author_name in book_author_rows:

    django_book_id = books_by_book_id.get(book_id)
    author_id = authors_by_name.get(author_name)

    if django_book_id and author_id:
        relations.append(
            through_model(
                book_id=django_book_id,
                author_id=author_id,
            )
        )


through_model.objects.bulk_create(
    relations,
    batch_size=BATCH_SIZE,
    ignore_conflicts=True,
)

print(f"Autores cargados: {Author.objects.count()}")
print(
    "Relaciones libro-autor cargadas: "
    f"{through_model.objects.count()}"
)


# ==========================================================
# COPIAS
# ==========================================================

print("Cargando copias...")

copies = []

with open("data/copies_clean.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        try:
            external_book_id = int(row["book_id"])

            django_book_id = books_by_book_id.get(
                external_book_id
            )

            if not django_book_id:
                continue

            copies.append(
                Copy(
                    copy_id=int(row["copy_id"]),
                    book_id=django_book_id,
                    available=True,
                )
            )

        except Exception:
            continue


Copy.objects.bulk_create(
    copies,
    batch_size=BATCH_SIZE,
    ignore_conflicts=True,
)

print(f"Copias cargadas: {Copy.objects.count()}")


# ==========================================================
# RATINGS
# ==========================================================

print(
    f"Cargando ratings, límite actual: "
    f"{LIMITE_RATINGS}..."
)


# Mapeamos los IDs originales de los CSV a las PK internas
# generadas por PostgreSQL/Django.
users_by_user_id = {
    user.user_id: user.id
    for user in LibraryUser.objects.only("id", "user_id")
}

copies_by_copy_id = {
    copy.copy_id: copy.id
    for copy in Copy.objects.only("id", "copy_id")
}


ratings = []
creados = 0
omitidos = 0


with open("data/ratings.csv", newline="", encoding="utf-8") as f:

    reader = csv.DictReader(f)

    for i, row in enumerate(reader, start=1):

        if (
            LIMITE_RATINGS is not None
            and i > LIMITE_RATINGS
        ):
            break

        try:
            external_user_id = int(row["user_id"])
            external_copy_id = int(row["copy_id"])
            rating_value = int(row["rating"])

            django_user_id = users_by_user_id.get(
                external_user_id
            )

            django_copy_id = copies_by_copy_id.get(
                external_copy_id
            )

            if not django_user_id or not django_copy_id:
                omitidos += 1
                continue

            ratings.append(
                Rating(
                    user_id=django_user_id,
                    copy_id=django_copy_id,
                    rating=rating_value,
                )
            )

            # Insertamos los ratings por lotes para evitar
            # mantener millones de objetos simultáneamente
            # en memoria.
            if len(ratings) >= BATCH_SIZE:

                Rating.objects.bulk_create(
                    ratings,
                    batch_size=BATCH_SIZE,
                    ignore_conflicts=True,
                )

                creados += len(ratings)
                ratings = []

                print(
                    f"Ratings procesados: {i} | "
                    f"creados aprox: {creados} | "
                    f"omitidos: {omitidos}"
                )

        except Exception:
            omitidos += 1


# Inserta el último lote si no alcanza BATCH_SIZE
if ratings:

    Rating.objects.bulk_create(
        ratings,
        batch_size=BATCH_SIZE,
        ignore_conflicts=True,
    )

    creados += len(ratings)


# ==========================================================
# RESUMEN
# ==========================================================

print()
print("Carga rápida terminada.")
print("--------------------------------------")
print(f"Usuarios: {LibraryUser.objects.count()}")
print(f"Libros: {Book.objects.count()}")
print(f"Autores: {Author.objects.count()}")
print(f"Copias: {Copy.objects.count()}")
print(f"Ratings procesados aprox.: {creados}")
print(f"Ratings omitidos: {omitidos}")
print(f"Ratings almacenados: {Rating.objects.count()}")
print("--------------------------------------")
print("Datos cargados correctamente en PostgreSQL.")