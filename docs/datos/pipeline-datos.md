# Pipeline de datos — Casa de la Cultura

> Última actualización: 29/09/2026
> Responsable: Jose Luis Mus Peñarroja (Ingeniero de Datos)

Este documento describe el ciclo de vida de los datos del proyecto, desde los ficheros originales entregados por el cliente hasta su carga en PostgreSQL y su uso por la aplicación y el sistema de recomendaciones.

---

## 1. Datos de origen

Los ficheros brutos se almacenan en `data/raw/` y no se modifican directamente. Esta carpeta está excluida de Git.

| Fichero | Descripción | Registros |
|---|---|---:|
| `books.csv` | Catálogo bibliográfico | 9.998 |
| `copies.csv` | Ejemplares físicos | — |
| `user_info.csv` | Usuarios registrados | 53.424 |
| `ratings.csv` | Valoraciones históricas de 1 a 5 | 5,7 M |

---

## 2. ETL y limpieza

Los scripts se encuentran en `etl/`, leen desde `data/raw/` y generan artefactos procesados.

### Libros — `etl_books_extended.py`

- Normaliza `language_code`.
- Recupera ISBNs de 9 dígitos mediante zero-padding.
- Conserva años negativos cuando corresponden a fechas a.C.
- Genera identificadores sintéticos `SIN-ISBN-{book_id:05d}` para libros sin ISBN.
- Separa autores para representar la relación N:M con `Book`.

**Salida:**

- `data/clean/books_clean_extended.csv`
- `data/clean/book_authors_extended.csv`

> Existe una versión anterior, `etl_books.py`, que descartaba libros sin ISBN. Se mantiene la versión extendida para no perder registros con ejemplares físicos.

### Ejemplares — `etl_copies_extended.py`

Limpia y normaliza `copies.csv`.

**Salida:** `data/clean/copies_clean_extended.csv`

### Usuarios — `etl_users.py`

Elimina el campo `sexo` según las decisiones funcionales del proyecto y el principio de minimización de datos.

**Salida:** `data/clean/users_clean.csv`

### Valoraciones — `etl_ratings.py`

Limpia `ratings.csv`.

Las valoraciones se mantienen en el rango de 1 a 5 y constituyen la principal fuente de información para el recomendador.

**Salida:** `data/clean/ratings_clean.csv`

### Géneros — `etl_genres.py`

Clasifica los libros por género a partir de título, autor y año.

Proceso original:

1. `generate-prompts`
2. `process-prompts`
3. `merge-responses`
4. `validate`

**Requiere:** `ANTHROPIC_API_KEY` y acceso a internet.

**Salida:**

- `data/clean/books_clean_final.csv`
- `data/clean/book_genres.csv`

> El fichero `books_with_genre.csv` fue generado en una fase anterior y representa un único género por libro, mientras que el modelo actual admite una relación N:M entre `Book` y `Genre`.

---

## 3. Artefactos versionados en `data/`

Los principales artefactos procesados se conservan en Git para evitar tener que repetir todo el ETL en cada entorno.

| Fichero | Descripción |
|---|---|
| `books_with_genre.csv` | Catálogo procesado con información bibliográfica y género |
| `book_authors_extended.csv` | Relación libro-autor |
| `copies_clean.csv` | Ejemplares procesados |
| `users_clean.csv` | Usuarios procesados |
| `book_genres.csv` | Relación libro-género |
| `isbn_recuperados.csv` | ISBNs recuperados mediante Open Library |
| `sinopsis.csv` | Sinopsis disponibles offline |

También existen artefactos del recomendador anterior:

- `votos_precalculados.csv`
- `recs_libros.csv`
- `recs_usuarios.csv`

Estos ficheros fueron generados por `train.py` mediante similitud coseno y se consideran legado dentro de la reevaluación.

---

## 4. Carga en PostgreSQL

La versión actual del proyecto utiliza PostgreSQL como sistema principal de persistencia.

Antes de cargar datos:

```cmd
python manage.py migrate
```

La carga se realiza mediante:

```cmd
python load_data_postgres.py
```

El script utiliza Django ORM y `bulk_create` para poblar las principales entidades:

- `Book`
- `Author`
- relaciones libro-autor
- `Copy`
- `LibraryUser`
- `Rating`

La carga completa puede tardar varios minutos debido al volumen de valoraciones.

La conexión a PostgreSQL se configura mediante un archivo `.env` basado en `.env.example`.

---

## 5. Sistema de recomendación anterior

La primera versión del proyecto utilizaba:

```cmd
python train.py
```

Este proceso calculaba similitud coseno ítem-ítem sobre la matriz de valoraciones y generaba:

- `votos_precalculados.csv`
- `recs_libros.csv`
- `recs_usuarios.csv`

Este sistema se mantiene únicamente como referencia histórica y compatibilidad temporal con componentes aún no migrados.

---

## 6. Sistema de recomendación actual — Apriori

La reevaluación sustituye el recomendador anterior por reglas de asociación generadas con Apriori.

El flujo previsto es:

```text
Rating
  |
  v
Copy
  |
  v
Book
  |
  v
Agrupación por usuario
  |
  v
Transacciones
  |
  v
Apriori
  |
  v
Reglas de asociación
  |
  v
PostgreSQL
```

Las transacciones se construyen agrupando libros valorados positivamente por cada usuario.

El parámetro `min_rating` determina la valoración mínima necesaria para incluir un libro en una transacción.

Ejemplo:

```text
Usuario 1 -> [Libro A, Libro B, Libro C]
Usuario 2 -> [Libro A, Libro C]
Usuario 3 -> [Libro B, Libro D]
```

Apriori podrá generar reglas como:

```text
Libro A => [Libro C]
Libro A => [Libro B, Libro C]
```

Las métricas principales serán:

- `support`
- `confidence`
- `lift`

---

## 7. Persistencia de Apriori

Cada ejecución se registra en `AprioriRun`.

Se almacenan, entre otros datos:

- `min_support`
- `min_confidence`
- `min_lift`
- `min_rating`
- `max_len`
- número de transacciones
- número de reglas
- estado activo de la ejecución

Las reglas se persisten en:

- `AssociationRule`
- `AssociationRuleTarget`

`AssociationRule` almacena el libro antecedente y las métricas de la regla.

`AssociationRuleTarget` almacena los libros del consecuente, permitiendo representar reglas como:

```text
Libro A => [Libro B, Libro C]
```

---

## 8. Enriquecimiento externo

Existen scripts auxiliares que consultan Open Library.

### Recuperar ISBNs

```cmd
python recuperar_isbn.py
```

Genera:

```text
data/isbn_recuperados.csv
```

### Generar sinopsis

```cmd
python generar_sinopsis.py
```

Genera:

```text
data/sinopsis.csv
```

Estos procesos requieren internet, pero los artefactos resultantes pueden utilizarse después de forma offline.

---

## 9. Configuración de PostgreSQL

El archivo `.env` debe contener una configuración equivalente a:

```env
DB_NAME=casa_cultura
DB_USER=casa_cultura_user
DB_PASSWORD=TU_PASSWORD
DB_HOST=localhost
DB_PORT=5432
```

`.env` está excluido de Git y `.env.example` actúa como plantilla.

---

## 10. Orden de ejecución en un entorno nuevo

### 1. Crear entorno virtual

```cmd
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar PostgreSQL

Crear el usuario y la base de datos y preparar el archivo `.env`.

### 3. Aplicar migraciones

```cmd
python manage.py migrate
```

### 4. Cargar datos

```cmd
python load_data_postgres.py
```

### 5. Generar reglas Apriori

El script definitivo deberá:

1. leer las valoraciones desde PostgreSQL;
2. construir las transacciones por usuario;
3. aplicar `min_rating`;
4. ejecutar Apriori;
5. filtrar por `min_support`, `min_confidence` y `min_lift`;
6. registrar la ejecución en `AprioriRun`;
7. guardar reglas en `AssociationRule`;
8. guardar consecuentes en `AssociationRuleTarget`;
9. marcar como activa la nueva ejecución.

### 6. Arrancar la aplicación

```cmd
python manage.py runserver
```

Disponible en [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

## 11. Resumen

```text
Datos originales
      |
      v
ETL y limpieza
      |
      v
Artefactos procesados
      |
      v
load_data_postgres.py
      |
      v
PostgreSQL
      |
      +------------------+
      |                  |
      v                  v
Aplicación Django    Algoritmo Apriori
                         |
                         v
                Reglas de asociación
                         |
                         v
                    PostgreSQL
```

PostgreSQL actúa como fuente principal de datos para la aplicación y para el sistema de recomendaciones.

---

## Véase también

- [Esquema de base de datos](esquema-bd.md)
- [Requisitos del cliente](../requisitos/requisitos_cliente_foro.md)
