# Casa de la Cultura

**Sistema de Gestión Bibliotecaria y Recomendación Inteligente**

Proyecto de la asignatura *Proyectos de Software* del Bachelor en Ingeniería Informática de la Universitat Carlemany. Curso 2025-2026, Grupo 4.

## Sobre el proyecto

La Casa de la Cultura es un bibliobús municipal con un fondo amplio de libros y un histórico de usuarios y valoraciones que hasta ahora no se estaba aprovechando. El encargo del cliente (Albert Calvo Ibáñez, en representación del ayuntamiento) consiste en construir un sistema que permita:

- Gestionar el catálogo a partir de los datos depurados del sistema anterior.
- Generar recomendaciones de libros mediante reglas de asociación obtenidas con el algoritmo Apriori.
- Visualizar el uso del fondo y los gustos de los lectores en cuadros de mando.

El sistema debe funcionar de forma local y offline en un único PC en la sede de la Casa de la Cultura, sin dependencias de internet ni licencias de pago.

## Equipo

| Nombre | Rol |
|---|---|
| Bruno Clemente Mora Hernández | Jefe de Proyecto |
| Juan Gabriel Carvajal Franco | Ingeniero de Software (Backend) |
| Adrián Meneses Ramos | Ingeniero de Software (Recomendación) |
| Jose Luis Mus Peñarroja | Ingeniero de Datos |

## Stack tecnológico

- **Lenguaje:** Python 3
- **Framework:** Django
- **Base de datos:** PostgreSQL
- **Control de versiones:** GitHub
- **Metodología:** AGILE (iterativa, con entregables al final de cada fase)

## Estructura de la aplicación

```text
Casa-de-la-Cultura_G4/
├── casa_cultura/           # Configuración y recursos de Django
├── app/                    # Catálogo, dashboard y modelos de recomendación
├── data/                   # Datos procesados utilizados por la aplicación
├── load_data_postgres.py   # Carga masiva de datos en PostgreSQL
├── manage.py
├── requirements.txt        # Dependencias del proyecto
└── README.md               # Documentación del proyecto
```

### Modelo de recomendaciones

La reevaluación utiliza un sistema de reglas de asociación basado en Apriori.

Las ejecuciones del algoritmo se registran en `AprioriRun`, incluyendo sus parámetros y métricas generales.

Las reglas generadas se almacenan en:

- `AssociationRule`: antecedente de la regla y métricas `support`, `confidence` y `lift`.
- `AssociationRuleTarget`: libros que forman el conjunto consecuente de cada regla.

Este diseño permite representar reglas del tipo:

`Libro A => [Libro B, Libro C, ...]`

## Configuración del entorno local

El proyecto utiliza PostgreSQL como sistema de persistencia. Cada entorno local debe disponer de una base de datos propia y de un archivo `.env` con las credenciales de conexión.

### Entorno Python

```cmd
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### PostgreSQL

Ejemplo de creación del usuario y de la base de datos:

```sql
CREATE USER casa_cultura_user WITH PASSWORD 'TU_PASSWORD';

CREATE DATABASE casa_cultura
    OWNER casa_cultura_user
    ENCODING 'UTF8';

GRANT ALL PRIVILEGES ON DATABASE casa_cultura TO casa_cultura_user;
```

### Variables de entorno

Crear un archivo `.env` en la raíz del proyecto con la configuración local:

```env
DB_NAME=casa_cultura
DB_USER=casa_cultura_user
DB_PASSWORD=TU_PASSWORD
DB_HOST=localhost
DB_PORT=5432
```

El archivo `.env` está excluido del control de versiones mediante `.gitignore`.

### Inicialización de la base de datos

Aplicar las migraciones de Django:

```cmd
python manage.py migrate
```

Cargar los datos de trabajo en PostgreSQL:

```cmd
python load_data_postgres.py
```

La carga completa puede tardar varios minutos debido al volumen de registros de valoraciones.

## Ejecución

Con el entorno virtual activo:

```cmd
python manage.py runserver
```

La aplicación queda disponible en [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
