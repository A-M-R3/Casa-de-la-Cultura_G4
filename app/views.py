from django.shortcuts import render, redirect

from django.http import JsonResponse

from django.db.models import Avg, Max, Count, Q

from app.models import AssociationRule, AssociationRuleTarget, AprioriRun, Book

import pandas as pd

import os

import unicodedata

import re

import ast

from app.models import (
    Book,
    Author,
    Genre,
    Copy,
    LibraryUser,
    Rating,
    AprioriRun,
    AssociationRule,
    AssociationRuleTarget,
)



BASE_CACHE = pd.DataFrame()

VOTOS_CACHE = pd.DataFrame()

TOP_VALORADOS_CACHE = None

TOP_POPULARES_CACHE = None

RECS_USER_CACHE = {}

RECS_BOOK_CACHE = {}



MAPA_IDIOMAS = {

    'en': 'Inglés', 'eng': 'Inglés', 'en-US': 'Inglés', 'en-GB': 'Inglés',

    'spa': 'Español', 'es': 'Español', 'fre': 'Francés', 'fr': 'Francés',

    'ger': 'Alemán', 'de': 'Alemán', 'ita': 'Italiano', 'it': 'Italiano',

    'jpn': 'Japonés', 'ara': 'Árabe', 'dan': 'Danés', 'fil': 'Filipino',

    'ind': 'Indonesio', 'mul': 'Múltiples idiomas', 'nl': 'Neerlandés',

    'nor': 'Noruego', 'per': 'Persa', 'pol': 'Polaco', 'por': 'Portugués',

    'rum': 'Rumano', 'rus': 'Ruso', 'swe': 'Sueco', 'tur': 'Turco',

    'vie': 'Vietnamita', 'nan': 'Desconocido'

}


def dashboard_view(request):
    total_reglas = AssociationRule.objects.count()
    
    # Cobertura de antecedentes únicos
    libros_con_reglas = AssociationRule.objects.values('antecedent_id').distinct().count()
    
    # Métricas agregadas del algoritmo
    agregados = AssociationRule.objects.aggregate(
        conf_media=Avg('confidence'),
        max_lift=Max('lift')
    )
    
    # Top 10 reglas con mayor lift
    reglas = AssociationRule.objects.select_related('antecedent')\
                                    .prefetch_related('targets__book')\
                                    .order_by('-lift')[:10]

    context = {
        'total_reglas': f"{total_reglas:,}".replace(",", "."),
        'libros_con_reglas': libros_con_reglas,
        'confianza_media': confianza_media,
        'lift_max': lift_max,
        'reglas': top_reglas,  # <-- Debe llamarse 'reglas' para coincidir con el HTML
    }
    return render(request, 'app/dashboard_personalizado.html', context)

def parsear_generos(val):

    if pd.isna(val):

        return ['Desconocido']

    val_str = str(val).strip()

    if val_str.startswith('[') and val_str.endswith(']'):

        try:

            parsed = ast.literal_eval(val_str)

            if isinstance(parsed, list):

                return [str(g).strip().title() for g in parsed if g.strip()]

        except:

            pass

    return [g.strip().title() for g in val_str.split(',') if g.strip()]



def cargar_recomendaciones():

    global RECS_USER_CACHE, RECS_BOOK_CACHE

    if not RECS_USER_CACHE and os.path.exists('data/recs_usuarios.csv'):

        try:

            df_u = pd.read_csv('data/recs_usuarios.csv')

            RECS_USER_CACHE = df_u.set_index('user_id')[['rec_1', 'rec_2', 'rec_3']].apply(list, axis=1).to_dict()

        except: pass



    if not RECS_BOOK_CACHE and os.path.exists('data/recs_libros.csv'):

        try:

            df_b = pd.read_csv('data/recs_libros.csv')

            RECS_BOOK_CACHE = df_b.set_index('book_id')[['rec_1', 'rec_2', 'rec_3']].apply(list, axis=1).to_dict()

        except: pass



def cargar_datos_completos():

    global BASE_CACHE

    if not BASE_CACHE.empty:

        return BASE_CACHE.copy()



    try:

        books_qs = list(Book.objects.values('id', 'book_id', 'title', 'isbn', 'language_code', 'publication_year'))

        if books_qs:

            df_books = pd.DataFrame(books_qs)

            df_books['book_id'] = pd.to_numeric(df_books['book_id'], errors='coerce').fillna(0).astype(int)

            df_books.rename(columns={'publication_year': 'original_publication_year'}, inplace=True)



            try:

                m2m_qs = list(Book.authors.through.objects.values('book_id', 'author_id'))

                a_qs = list(Author.objects.values('id', 'name'))

                if m2m_qs and a_qs:

                    df_m2m = pd.DataFrame(m2m_qs).rename(columns={'book_id': 'book_pk'})

                    df_a = pd.DataFrame(a_qs).rename(columns={'id': 'author_id'})

                    df_merged = pd.merge(df_m2m, df_a, on='author_id')

                    pk_map = df_books[['id', 'book_id']].rename(columns={'id': 'book_pk'})

                    df_merged = pd.merge(df_merged, pk_map, on='book_pk')

                    autores = df_merged.groupby('book_id')['name'].apply(lambda x: ', '.join([str(i) for i in x if pd.notna(i)])).reset_index()

                    autores.rename(columns={'name': 'authors'}, inplace=True)

                    df_books = pd.merge(df_books, autores, on='book_id', how='left')

            except: pass



            df_books['authors'] = df_books.get('authors', pd.Series(['Desconocido']*len(df_books))).fillna('Desconocido')



            ruta_csv = 'data/books_with_genre.csv'

            if os.path.exists(ruta_csv):

                df_csv = pd.read_csv(ruta_csv, encoding='utf-8-sig')

                csv_pk = 'book_id' if 'book_id' in df_csv.columns else 'id'

                df_csv['book_id'] = pd.to_numeric(df_csv[csv_pk], errors='coerce').fillna(0).astype(int)

                missing_cols = [c for c in df_csv.columns if c not in df_books.columns and c != 'id']

                if missing_cols:

                    df_books = pd.merge(df_books, df_csv[['book_id'] + missing_cols], on='book_id', how='left')



            try:

                ruta_genres = 'data/book_genres.csv'

                if os.path.exists(ruta_genres):

                    df_g = pd.read_csv(ruta_genres, encoding='utf-8-sig')

                    g_pk = 'book_id' if 'book_id' in df_g.columns else 'id'

                    df_g[g_pk] = pd.to_numeric(df_g[g_pk], errors='coerce').fillna(0).astype(int)

                    generos_agrupados = df_g.groupby(g_pk)['genre'].apply(lambda x: [str(i).strip().title() for i in x if pd.notna(i)]).reset_index()

                    generos_agrupados.rename(columns={g_pk: 'book_id', 'genre': 'genre_list_multi'}, inplace=True)

                    df_books = pd.merge(df_books, generos_agrupados, on='book_id', how='left')

                    df_books['genre_list'] = df_books['genre_list_multi']

            except: pass



            if 'genre_list' not in df_books.columns:

                col_g = next((c for c in ['genres', 'genre'] if c in df_books.columns), None)

                if col_g:

                    df_books['genre_list'] = df_books[col_g].apply(parsear_generos)

                else:

                    df_books['genre_list'] = [['Desconocido']] * len(df_books)



            df_books['genre_list'] = df_books['genre_list'].apply(lambda x: x if isinstance(x, list) else ['Desconocido'])



            df_books['original_publication_year'] = pd.to_numeric(df_books.get('original_publication_year', pd.Series([0]*len(df_books))), errors='coerce').fillna(0).astype(int)



            if 'language_code' in df_books.columns:

                df_books['language_display'] = df_books['language_code'].map(MAPA_IDIOMAS).fillna(df_books['language_code'])

            else:

                df_books['language_display'] = 'Desconocido'



            df_books['isbn'] = df_books.get('isbn', pd.Series(['N/A']*len(df_books))).fillna('N/A')

            df_books['title'] = df_books.get('title', pd.Series(['Sin título']*len(df_books))).fillna('Sin título')



            BASE_CACHE = df_books.drop_duplicates('book_id')

            return BASE_CACHE.copy()

    except: pass

    return pd.DataFrame()



def obtener_votos_totales():

    global VOTOS_CACHE

    if not VOTOS_CACHE.empty:

        return VOTOS_CACHE.copy()



    ruta_precalc = 'data/votos_precalculados.csv'

    if os.path.exists(ruta_precalc):

        try:

            df_votos = pd.read_csv(ruta_precalc, encoding='utf-8-sig')

            df_votos['book_id'] = pd.to_numeric(df_votos['book_id'], errors='coerce').fillna(0).astype(int)

            VOTOS_CACHE = df_votos

            return VOTOS_CACHE.copy()

        except: pass

    return pd.DataFrame()



def obtener_tops_generales():

    global TOP_VALORADOS_CACHE, TOP_POPULARES_CACHE

    if TOP_VALORADOS_CACHE is not None and TOP_POPULARES_CACHE is not None:

        return TOP_VALORADOS_CACHE, TOP_POPULARES_CACHE



    df_completo = cargar_datos_completos()

    votos_df = obtener_votos_totales()



    if not df_completo.empty and not votos_df.empty:

        populares_df = votos_df.sort_values('votos', ascending=False).head(5)

        top_pop_unificado = pd.merge(populares_df, df_completo, on='book_id')

        max_votos_pop = top_pop_unificado['votos'].max()



        TOP_POPULARES_CACHE = []

        for _, fila in top_pop_unificado.iterrows():

            TOP_POPULARES_CACHE.append({

                'title': fila['title'],

                'ratings': int(fila['votos']),

                'pct': int((fila['votos'] / max_votos_pop) * 100) if max_votos_pop else 0

            })



        valorados_df = votos_df[votos_df['votos'] >= 1000].sort_values(['nota_media', 'votos'], ascending=[False, False]).head(5)

        if valorados_df.empty:

            valorados_df = votos_df.sort_values(['nota_media', 'votos'], ascending=[False, False]).head(5)



        top_val_unificado = pd.merge(valorados_df, df_completo, on='book_id')



        TOP_VALORADOS_CACHE = []

        for _, fila in top_val_unificado.iterrows():

            TOP_VALORADOS_CACHE.append({

                'title': fila['title'],

                'nota_media': float(fila['nota_media']),

                'votos': int(fila['votos']),

                'pct': int((fila['nota_media'] / 5.0) * 100)

            })



        return TOP_VALORADOS_CACHE, TOP_POPULARES_CACHE

    return [], []



def normalizar_texto(texto):

    if not isinstance(texto, str): 

        return ""

    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')

    return re.sub(r'[^a-zA-Z0-9]', '', texto).lower()



def obtener_menor_id_disponible():
    """
    Localiza el número entero positivo más bajo disponible a partir de 1
    (reutiliza huecos de usuarios eliminados).
    """
    existing_ids = set(LibraryUser.objects.values_list('user_id', flat=True))
    candidate = 1
    while candidate in existing_ids:
        candidate += 1
    return candidate


def login_view(request):
    error = None
    mensaje_exito = None
    user_id_ingresado = ''

    if request.method == 'POST':
        action = request.POST.get('action', 'login')
        user_id_raw = request.POST.get('user_id', '').strip()
        user_id_ingresado = user_id_raw

        if not user_id_raw or not user_id_raw.isdigit():
            error = "Por favor, introduce un número de ID de usuario válido."
            return render(request, 'login.html', {'error': error, 'user_id_ingresado': user_id_ingresado})

        uid = int(user_id_raw)
        user_obj = LibraryUser.objects.filter(user_id=uid).first()

        if action == 'login':
            if not user_obj:
                error = f"Usuario no identificado. El lector con ID {uid} no existe en el sistema."
                return render(request, 'login.html', {'error': error, 'user_id_ingresado': user_id_ingresado})
            request.session['user_id'] = str(uid)
            return redirect('buscador')

        elif action == 'edit':
            if not user_obj:
                error = f"Usuario no identificado. No se pueden modificar los gustos de un usuario que no existe."
                return render(request, 'login.html', {'error': error, 'user_id_ingresado': user_id_ingresado})
            request.session['user_id'] = str(uid)
            return redirect('perfil')

        elif action == 'delete':
            if not user_obj:
                error = f"Usuario no identificado. No se puede borrar el lector con ID {uid} porque no existe."
                return render(request, 'login.html', {'error': error, 'user_id_ingresado': user_id_ingresado})
            
            # Al borrar el usuario, PostgreSQL elimina sus valoraciones en cascada
            user_obj.delete()
            if request.session.get('user_id') == str(uid):
                del request.session['user_id']
            mensaje_exito = f"El usuario {uid} y todo su historial de valoraciones han sido eliminados correctamente."
            return render(request, 'login.html', {'mensaje_exito': mensaje_exito})

    return render(request, 'login.html', {
        'error': error, 
        'mensaje_exito': mensaje_exito, 
        'user_id_ingresado': user_id_ingresado
    })


def registro_view(request):
    generos_disponibles = []
    try:
        df_base = cargar_datos_completos()
        if not df_base.empty:
            generos_disponibles = sorted(set(g for sub in df_base['genre_list'] for g in sub if g and g != 'Desconocido'))
    except:
        pass

    siguiente_id = obtener_menor_id_disponible()
    error = None

    if request.method == 'POST':
        generos_elegidos = request.POST.getlist('generos')
        gustos = ', '.join(generos_elegidos)
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '')
        custom_id_raw = request.POST.get('user_id', '').strip()

        if custom_id_raw:
            if not custom_id_raw.isdigit():
                error = "El ID de usuario debe ser un número entero positivo."
            else:
                target_id = int(custom_id_raw)
                if LibraryUser.objects.filter(user_id=target_id).exists():
                    error = f"Este número de usuario ya existe (ID {target_id}). Por favor, elige otro o usa el sugerido."
                else:
                    nuevo_id = target_id
        else:
            nuevo_id = siguiente_id

        if not error:
            try:
                user = LibraryUser.objects.create(
                    user_id=nuevo_id,
                    comment=gustos,
                    birth_date=fecha_nacimiento or None
                )
                request.session['user_id'] = str(user.user_id)
                return redirect('buscador')
            except Exception as e:
                error = f"Error al registrar usuario: {e}"

    return render(request, 'registro.html', {
        'generos_disponibles': generos_disponibles,
        'siguiente_id': siguiente_id,
        'error': error,
    })



def logout_view(request):

    if 'user_id' in request.session: 

        del request.session['user_id']

    return redirect('login')


def perfil_view(request):

    user_id = request.session.get('user_id')

    if not user_id:

        return redirect('login')



    gustos_actuales = ""

    fecha_actual = ""



    try:

        user = LibraryUser.objects.filter(user_id=user_id).first()

        if user:

            gustos_actuales = str(getattr(user, 'comment', getattr(user, 'preferences', getattr(user, 'gustos', '')))).strip()

            fecha_actual = str(getattr(user, 'birth_date', getattr(user, 'birthdate', getattr(user, 'fecha_nacimiento', '')))).strip()

    except: pass



    if gustos_actuales in ['nan', 'None']: gustos_actuales = ""

    if fecha_actual in ['nan', 'None']: fecha_actual = ""



    generos_seleccionados = [g.strip() for g in gustos_actuales.split(',') if g.strip()] if gustos_actuales else []



    generos_disponibles = []

    try:

        df_base = cargar_datos_completos()

        if not df_base.empty:

            generos_disponibles = sorted(set(g for sub in df_base['genre_list'] for g in sub if g and g != 'Desconocido'))

    except: pass



    if request.method == 'POST':

        nueva_fecha = request.POST.get('fecha_nacimiento', '')

        generos_elegidos = request.POST.getlist('generos')

        nuevos_gustos = ', '.join(generos_elegidos)



        try:

            user = LibraryUser.objects.filter(user_id=user_id).first()

            if user:

                if hasattr(user, 'comment'): user.comment = nuevos_gustos

                elif hasattr(user, 'preferences'): user.preferences = nuevos_gustos

                if hasattr(user, 'birth_date'): user.birth_date = nueva_fecha or None

                elif hasattr(user, 'birthdate'): user.birthdate = nueva_fecha or None

                user.save()

        except: pass

        return redirect('buscador')



    return render(request, 'perfil.html', {

        'generos_disponibles': generos_disponibles,

        'generos_seleccionados': generos_seleccionados,

        'fecha': fecha_actual,

        'user_id': user_id,

    })



def buscador_catalogo(request):
    query_busqueda = request.GET.get('q', '')
    filtro_genero = request.GET.get('genre', '')
    filtro_idioma = request.GET.get('lang', '')
    filtro_ano_min = request.GET.get('year_min', '')
    filtro_ano_max = request.GET.get('year_max', '')
    filtro_nota = request.GET.get('rating', '0')
    filtro_votos = request.GET.get('votes', '0')
    filtro_ejemplares = request.GET.get('available', '')
    metodo_orden = request.GET.get('sort', 'relevance')

    try: pagina_actual = int(request.GET.get('page', 1))
    except ValueError: pagina_actual = 1

    usuario_activo = request.session.get('user_id')

    df_base = cargar_datos_completos()
    votos_df = obtener_votos_totales()
    top_valorados_general, top_populares_general = obtener_tops_generales()
    cargar_recomendaciones()

    recomendaciones = []
    top_dinamico = []
    titulo_sidebar_dinamico = ""
    top_por_genero = []
    autor_destacado = ""
    sugerencia = None
    valorado = request.GET.get('valorado', '')
    user_top_rated = []

    if usuario_activo:
        try:
            uid = int(usuario_activo)
            user_obj = LibraryUser.objects.filter(user_id=uid).first()
            if user_obj:
                user_top_rated = list(Rating.objects.filter(
                    user=user_obj
                ).select_related('copy__book').order_by('-rating', '-created_at')[:5])

                # 1. EVALUAR TODAS LAS VALORACIONES POSITIVAS (Rating >= 4)
                ratings_candidatos = Rating.objects.filter(
                    user=user_obj, 
                    rating__gte=4
                ).select_related('copy__book').order_by('-rating', '-created_at')

                for r_cand in ratings_candidatos:
                    ext_id = r_cand.copy.book.book_id
                    recs_ids = RECS_BOOK_CACHE.get(ext_id, [])

                    if recs_ids:
                        df_tmp2 = cargar_datos_completos()
                        destino_rows = df_tmp2[df_tmp2['book_id'].isin(recs_ids)].drop_duplicates(subset=['authors'])

                        if not destino_rows.empty:
                            sugerencia = {
                                'tipo': 'libro',
                                'origen': r_cand.copy.book.title[:35],
                                'destino': destino_rows.iloc[0]['title'][:35],
                            }
                            recomendaciones = destino_rows.head(3).to_dict('records')
                            break  # Se encontró una regla activa válida

                # 2. RESOLUCIÓN DE COLD START / FALLBACK A GÉNEROS SI NINGÚN LIBRO TIENE REGLAS
                if not recomendaciones:
                    gustos = str(getattr(user_obj, 'comment', '') or '').strip()
                    if gustos and gustos not in ('nan', 'None'):
                        generos_usuario = [g.strip() for g in gustos.split(',') if g.strip()]
                        if generos_usuario and not df_base.empty:
                            df_gen = df_base[
                                df_base['genre_list'].apply(lambda x: any(g in x for g in generos_usuario))
                            ]
                            if not df_gen.empty:
                                top_cands = df_gen.sort_values(
                                    ['nota_media', 'votos'], ascending=[False, False]
                                ).drop_duplicates(subset=['authors'])

                                if not top_cands.empty:
                                    primer_libro = top_cands.iloc[0]
                                    gen_match = next((g for g in generos_usuario if g in primer_libro.get('genre_list', [])), generos_usuario[0])
                                    sugerencia = {
                                        'tipo': 'genero',
                                        'origen': gen_match,
                                        'destino': primer_libro['title'][:35],
                                    }
                                    recomendaciones = top_cands.head(3).to_dict('records')
        except:
            pass

    filtros_activos = bool(query_busqueda.strip() or filtro_genero.strip() or filtro_idioma.strip() or 
                           filtro_ano_min.strip() or filtro_ano_max.strip() or 
                           (filtro_nota and str(filtro_nota) != '0') or 
                           (filtro_votos and str(filtro_votos) != '0') or 
                           filtro_ejemplares == 'on')

    if filtros_activos:
        titulo_recomendacion = "Recomendado según tu búsqueda:"
    elif usuario_activo and recomendaciones:
        titulo_recomendacion = "Recomendado según tus gustos:"
    else:
        titulo_recomendacion = "Tendencias Actuales en el Catálogo:"

    if not df_base.empty:
        if not votos_df.empty and 'book_id' in votos_df.columns:
            df_base = pd.merge(df_base, votos_df, on='book_id', how='left').fillna({'votos': 0, 'nota_media': 0})
        else:
            if 'votos' not in df_base.columns: df_base['votos'] = 0
            if 'nota_media' not in df_base.columns: df_base['nota_media'] = 0

        lista_generos = sorted(list(set(g for sublist in df_base['genre_list'] for g in sublist if g != 'Desconocido')))
        lista_idiomas = sorted(df_base['language_display'].dropna().unique().tolist())
        resultados_busqueda = df_base.copy()

        def aplicar_filtros_adicionales(df):
            res = df.copy()
            if filtro_genero and not res.empty:
                res = res[res['genre_list'].apply(lambda x: filtro_genero.lower() in [g.lower() for g in x]).astype(bool)]
            if filtro_idioma and not res.empty:
                res = res[res['language_display'] == filtro_idioma]
            if filtro_ano_min and not res.empty:
                try: res = res[res['original_publication_year'] >= int(filtro_ano_min)]
                except ValueError: pass
            if filtro_ano_max and not res.empty:
                try: res = res[res['original_publication_year'] <= int(filtro_ano_max)]
                except ValueError: pass
            if filtro_nota and str(filtro_nota) != '0' and not res.empty:
                try: res = res[res['nota_media'] >= float(filtro_nota)]
                except ValueError: pass
            if filtro_votos and str(filtro_votos) != '0' and not res.empty:
                try: res = res[res['votos'] >= int(filtro_votos)]
                except ValueError: pass
            if filtro_ejemplares == 'on' and not res.empty:
                try:
                    qs = list(Copy.objects.values_list('book__book_id', flat=True).distinct())
                    valid_books = [int(x) for x in qs if x is not None]
                    res = res[res['book_id'].isin(valid_books)]
                except: pass
            return res

        if query_busqueda:
            texto_normalizado = normalizar_texto(query_busqueda)
            resultados_busqueda['title_norm'] = resultados_busqueda['title'].apply(normalizar_texto)
            resultados_busqueda['authors_norm'] = resultados_busqueda['authors'].fillna("").apply(normalizar_texto)
            resultados_busqueda['isbn_norm'] = resultados_busqueda['isbn'].fillna("").astype(str).apply(normalizar_texto)

            resultados_busqueda = resultados_busqueda[
                (resultados_busqueda['title_norm'].str.contains(texto_normalizado, na=False)) | 
                (resultados_busqueda['authors_norm'].str.contains(texto_normalizado, na=False)) |
                (resultados_busqueda['isbn_norm'].str.contains(texto_normalizado, na=False))
            ]

            if not resultados_busqueda.empty:
                primer_libro = resultados_busqueda.iloc[0]
                autor_completo = primer_libro['authors']
                if pd.notna(autor_completo) and autor_completo != "":
                    autor_destacado = autor_completo.split(',')[0].strip()

                if autor_destacado and texto_normalizado in normalizar_texto(autor_destacado):
                    titulo_sidebar_dinamico = f"Lo mejor de {autor_destacado}"
                    top_dinamico = df_base[df_base['authors'].fillna('').str.contains(autor_destacado, regex=False)].sort_values(['nota_media', 'votos'], ascending=[False, False]).head(3).to_dict('records')
                else:
                    titulo_sidebar_dinamico = f"Top para '{query_busqueda}'"
                    top_dinamico = resultados_busqueda.sort_values(['nota_media', 'votos'], ascending=[False, False]).head(3).to_dict('records')

        resultados_busqueda = aplicar_filtros_adicionales(resultados_busqueda)

        if filtro_genero and not df_base.empty:
            top_por_genero = df_base[df_base['genre_list'].apply(lambda x: filtro_genero.lower() in [g.lower() for g in x]).astype(bool)].sort_values(['nota_media', 'votos'], ascending=[False, False]).head(3).to_dict('records')

        if metodo_orden == 'popular':
            resultados_busqueda = resultados_busqueda.sort_values('votos', ascending=False)
        elif metodo_orden == 'top_rated':
            resultados_busqueda = resultados_busqueda.sort_values('nota_media', ascending=False)
        elif metodo_orden == 'year_new':
            resultados_busqueda = resultados_busqueda.sort_values('original_publication_year', ascending=False)
        elif metodo_orden == 'year_old':
            resultados_busqueda = resultados_busqueda[resultados_busqueda['original_publication_year'] > 0].sort_values('original_publication_year', ascending=True)

        total_resultados = len(resultados_busqueda)
        total_paginas = max(1, (total_resultados + 19) // 20)
        indice_inicio = (pagina_actual - 1) * 20
        indice_fin = pagina_actual * 20
        listado_final = resultados_busqueda.iloc[indice_inicio:indice_fin].to_dict('records')

        if not recomendaciones:
            df_tendencias = aplicar_filtros_adicionales(df_base) if filtros_activos else df_base.copy()
            if not df_tendencias.empty:
                recomendaciones = df_tendencias[df_tendencias['votos'] > 50].sort_values('nota_media', ascending=False).drop_duplicates(subset=['authors']).head(3).to_dict('records')

    else:
        lista_generos, lista_idiomas, listado_final = [], [], []
        total_paginas, pagina_actual = 1, 1

    return render(request, 'lista_libros.html', {
        'libros': listado_final, 
        'top_valorados_general': top_valorados_general,
        'top_populares_general': top_populares_general, 
        'top_dinamico': top_dinamico,
        'titulo_sidebar_dinamico': titulo_sidebar_dinamico,
        'top_genero': top_por_genero,
        'recomendaciones': recomendaciones,
        'titulo_recomendacion': titulo_recomendacion, 
        'query': query_busqueda, 
        'generos': lista_generos, 
        'idiomas': lista_idiomas,
        'genre_sel': filtro_genero, 
        'lang_sel': filtro_idioma, 
        'year_min_sel': filtro_ano_min,
        'year_max_sel': filtro_ano_max,
        'rating_sel': filtro_nota,
        'votes_sel': filtro_votos,
        'available_sel': filtro_ejemplares,
        'sort_sel': metodo_orden, 
        'user_active': usuario_activo,
        'user_top_rated': user_top_rated,
        'page': pagina_actual,
        'total_paginas': total_paginas,
        'sugerencia': sugerencia,
        'valorado': valorado,
    })



def valorar_libro(request, book_id):

    if request.method != 'POST':

        return redirect('buscador')

    user_id = request.session.get('user_id')

    if not user_id:

        return redirect('login')

    try:

        rating_val = int(request.POST.get('rating', 0))

        if not 1 <= rating_val <= 5:

            return redirect('buscador')

        user_obj = LibraryUser.objects.filter(user_id=user_id).first()

        book_obj = Book.objects.filter(pk=book_id).first()

        if not user_obj or not book_obj:

            return redirect('buscador')

        copy_obj = Copy.objects.filter(book=book_obj).first()

        if not copy_obj:

            from django.db.models import Max

            max_copy_id = Copy.objects.aggregate(m=Max('copy_id'))['m'] or 0

            copy_obj = Copy.objects.create(copy_id=max_copy_id + 1, book=book_obj, available=False)

        Rating.objects.update_or_create(

            user=user_obj, copy=copy_obj,

            defaults={'rating': rating_val}

        )

    except: pass

    return redirect('/buscador/?valorado=1')





def resumen_ia_view(request):

    import random

    titulo = request.GET.get('titulo', '')

    autor = request.GET.get('autor', '')

    genero = request.GET.get('genero', '')

    anio = request.GET.get('anio', '')

    nota = request.GET.get('nota', '')

    votos = request.GET.get('votos', '')



    ruta_sinopsis = 'data/sinopsis.csv'

    if os.path.exists(ruta_sinopsis):

        try:

            df_sinopsis = pd.read_csv(ruta_sinopsis)

            match = df_sinopsis[df_sinopsis['title'].str.lower() == titulo.lower()]

            if not match.empty:

                texto = str(match.iloc[0]['sinopsis']).strip()

                tiene_castellano = bool(re.search(r'[áéíóúñüÁÉÍÓÚÑÜ]', texto[:300]))

                if texto and texto not in ('nan', 'None') and tiene_castellano:

                    return JsonResponse({'resumen': texto})

        except: pass



    partes = []



    aperturas = [

        f"'{titulo}' es una obra de {autor} que ha logrado conectar con lectores de perfiles muy distintos.",

        f"Con '{titulo}', {autor} consigue algo difícil: crear una experiencia que permanece en la memoria del lector.",

        f"Pocas obras del catálogo generan el tipo de fidelidad lectora que ha conseguido '{titulo}', de {autor}.",

        f"'{titulo}' representa uno de los títulos más singulares que {autor} ha puesto en circulación.",

        f"La propuesta literaria de {autor} en '{titulo}' destaca por su coherencia y su capacidad de sorprender.",

    ]

    partes.append(random.choice(aperturas))



    if genero and anio and anio not in ('0', ''):

        contextos = [

            f"Publicada en {anio}, esta obra de {genero.lower()} explora con madurez los temas que definen el género.",

            f"Desde {anio}, este título de {genero.lower()} mantiene una presencia destacada entre los lectores más exigentes.",

            f"En el terreno del {genero.lower()}, pocas obras publicadas en {anio} han tenido un recorrido tan sostenido.",

        ]

        partes.append(random.choice(contextos))

    elif genero:

        opciones = [

            f"Inscrita en el {genero.lower()}, la obra trabaja con soltura los recursos propios del género sin caer en lo predecible.",

            f"El {genero.lower()} encuentra en este libro una de sus expresiones más cuidadas.",

        ]

        partes.append(random.choice(opciones))

    elif anio and anio not in ('0', ''):

        partes.append(random.choice([

            f"Publicada en {anio}, la obra conserva una vigencia que pocos títulos de su época pueden reclamar.",

            f"Aunque data de {anio}, su lectura resulta igual de pertinente hoy que en el momento de su publicación.",

        ]))



    try:

        nota_f = float(nota)

        votos_i = int(votos) if votos else 0

        if nota_f >= 4.2:

            valoraciones = [

                f"Con una valoración media de {nota_f:.1f} sobre 5 entre {votos_i:,} lectores, figura entre las obras mejor recibidas del catálogo.",

                f"Sus {votos_i:,} valoraciones con una media de {nota_f:.1f} sobre 5 la convierten en una de las referencias más fiables del fondo.",

            ]

        elif nota_f >= 3.5:

            valoraciones = [

                f"Acumula {votos_i:,} valoraciones con una media de {nota_f:.1f} sobre 5, reflejo de una acogida consistentemente positiva.",

                f"La nota media de {nota_f:.1f} entre {votos_i:,} lectores habla de un libro que cumple con creces lo que promete.",

            ]

        else:

            valoraciones = [

                f"Con {votos_i:,} valoraciones registradas, genera lecturas e interpretaciones muy diversas.",

                f"Un título que no deja indiferente: {votos_i:,} valoraciones dan fe de la conversación que ha generado.",

            ]

        partes.append(random.choice(valoraciones))

    except: pass



    cierres = [

        "Una lectura que, una vez empezada, resulta difícil de abandonar.",

        "Ideal para quien busca algo más que entretenimiento en sus lecturas.",

        "Sin duda, un título que justifica el tiempo que se le dedica.",

        "De esas obras que siguen resonando mucho después de cerrar la última página.",

        "Una propuesta que equilibra accesibilidad y profundidad de manera poco frecuente.",

        "Muy recomendable para lectores que valoran tanto la forma como el fondo.",

    ]

    partes.append(random.choice(cierres))



    return JsonResponse({'resumen': ' '.join(partes)})

def dashboard_analitico(request):
    active_run = AprioriRun.objects.filter(is_active=True).first() or AprioriRun.objects.last()
    
    mensaje_config = None
    error_config = None

    # Procesar modificación de parámetros del algoritmo desde el Front-End
    if request.method == 'POST' and request.POST.get('action') == 'modificar_algoritmo':
        support_raw = request.POST.get('min_support', '').strip().replace(',', '.')
        conf_raw = request.POST.get('min_confidence', '').strip().replace(',', '.')
        lift_raw = request.POST.get('min_lift', '').strip().replace(',', '.')
        rating_raw = request.POST.get('min_rating', '').strip()

        try:
            val_supp = float(support_raw)
            val_conf = float(conf_raw)
            val_lift = float(lift_raw)
            val_rating = int(rating_raw)

            # Si el usuario introduce porcentajes (ej. 30 en vez de 0.30)
            if val_supp > 1.0: val_supp = val_supp / 100.0
            if val_conf > 1.0: val_conf = val_conf / 100.0

            if not (0.001 <= val_supp <= 1.0):
                raise ValueError("El soporte mínimo debe estar entre 0.001 (0.1%) y 1.0 (100%).")
            if not (0.01 <= val_conf <= 1.0):
                raise ValueError("La confianza mínima debe estar entre 0.01 (1%) y 1.0 (100%).")
            if val_lift < 0:
                raise ValueError("El Lift umbral no puede ser un número negativo.")
            if not (1 <= val_rating <= 5):
                raise ValueError("La valoración mínima de corte debe ser un número entero entre 1 y 5.")

            if active_run:
                active_run.min_support = val_supp
                active_run.min_confidence = val_conf
                active_run.min_lift = val_lift
                active_run.min_rating = val_rating
                active_run.save()
                mensaje_config = f"Parámetros actualizados con éxito: Soporte ≥ {val_supp:.3f}, Confianza ≥ {val_conf*100:.1f}%, Lift ≥ {val_lift:.2f}, Valoración ≥ {val_rating}★."
        except ValueError as ve:
            error_config = f"Error en los parámetros: {ve}"
        except Exception as e:
            error_config = f"Parámetro no válido: Asegúrate de ingresar números válidos sin símbolos extraños. ({e})"

    context = {
        'run': active_run,
        'top_rules': [],
        'stats': {},
        'inspect_query': '',
        'inspected_results': [],
        'mensaje_config': mensaje_config,
        'error_config': error_config,
    }
    
    if active_run:
        # Consulta de reglas filtradas por los umbrales configurados
        reglas_qs = AssociationRule.objects.filter(
            run=active_run,
            support__gte=active_run.min_support,
            confidence__gte=active_run.min_confidence,
            lift__gte=active_run.min_lift
        )

        top_rules = list(reglas_qs.select_related('source_book').order_by('-lift')[:10])

        targets = AssociationRuleTarget.objects.filter(rule__in=top_rules).select_related('book')
        targets_map = {}
        for t in targets:
            targets_map.setdefault(t.rule_id, []).append(t.book)

        for r in top_rules:
            r.consequent_libros = targets_map.get(r.id, [])

        context['top_rules'] = top_rules

        context['stats'] = {
            'total_reglas': reglas_qs.count(),
            'avg_confidence': (reglas_qs.aggregate(Avg('confidence'))['confidence__avg'] or 0) * 100,
            'avg_support': (reglas_qs.aggregate(Avg('support'))['support__avg'] or 0) * 100,
            'max_lift': reglas_qs.aggregate(Max('lift'))['lift__max'] or 0,
            'total_cobertura': reglas_qs.values('source_book_id').distinct().count()
        }

        inspect_query = request.GET.get('q_inspect', '').strip()
        context['inspect_query'] = inspect_query

        if inspect_query:
            palabras = inspect_query.replace('-', ' ').split()
            filtro_q = Q()
            for palabra in palabras:
                filtro_q &= (
                    Q(source_book__title__icontains=palabra) |
                    Q(source_book__authors__name__icontains=palabra)
                )

            matching_rules_qs = reglas_qs.filter(filtro_q).distinct().select_related('source_book').order_by('-lift')
            
            seen_rule_ids = set()
            matching_rules = []
            for r in matching_rules_qs:
                if r.id not in seen_rule_ids:
                    seen_rule_ids.add(r.id)
                    matching_rules.append(r)
                if len(matching_rules) >= 5:
                    break

            if matching_rules:
                inspect_targets = AssociationRuleTarget.objects.filter(rule__in=matching_rules).select_related('book')
                inspect_map = {}
                for t in inspect_targets:
                    inspect_map.setdefault(t.rule_id, []).append(t.book.title)

                inspected_results = []
                for rule in matching_rules:
                    consecuentes = inspect_map.get(rule.id, [])
                    inspected_results.append({
                        'source': rule.source_book.title,
                        'targets': consecuentes,
                        'support_pct': round(rule.support * 100, 2),
                        'confidence_pct': round(rule.confidence * 100, 1),
                        'lift': round(rule.lift, 2),
                        'explicacion': (
                            f"De los lectores que valoraron positivamente '{rule.source_book.title}', "
                            f"un {round(rule.confidence * 100, 1)}% también disfrutó de {', '.join(consecuentes)}. "
                            f"El Lift de {round(rule.lift, 2)} demuestra que esta asociación es {round(rule.lift, 1)} veces "
                            f"más fuerte que una coincidencia por puro azar."
                        )
                    })
                context['inspected_results'] = inspected_results

    return render(request, 'app/dashboard_personalizado.html', context)

def mi_biblioteca_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    df_base = cargar_datos_completos()

    # Mapeo de géneros y año de publicación desde el catálogo consolidado
    genre_map = {}
    year_map = {}
    if not df_base.empty:
        genre_map = df_base.set_index('book_id')['genre_list'].to_dict()
        year_map = df_base.set_index('book_id')['original_publication_year'].to_dict()

    user_obj = LibraryUser.objects.filter(user_id=user_id).first()
    ratings_qs = Rating.objects.filter(user__user_id=user_id).select_related('copy__book').prefetch_related('copy__book__authors')

    # Filtros de búsqueda
    q = request.GET.get('q', '').strip()
    if q:
        ratings_qs = ratings_qs.filter(
            Q(copy__book__title__icontains=q) |
            Q(copy__book__authors__name__icontains=q)
        ).distinct()

    rating_filter = request.GET.get('rating', '')
    if rating_filter.isdigit():
        ratings_qs = ratings_qs.filter(rating=int(rating_filter))

    genre_filter = request.GET.get('genre', '')
    if genre_filter and not df_base.empty:
        matching_bids = df_base[df_base['genre_list'].apply(lambda gl: genre_filter in gl)]['book_id'].tolist()
        ratings_qs = ratings_qs.filter(copy__book__book_id__in=matching_bids)

    decade_filter = request.GET.get('decade', '')
    if decade_filter:
        if decade_filter == 'classic':
            ratings_qs = ratings_qs.filter(copy__book__publication_year__lt=1980)
        elif decade_filter.isdigit():
            start_year = int(decade_filter)
            ratings_qs = ratings_qs.filter(
                copy__book__publication_year__gte=start_year,
                copy__book__publication_year__lte=start_year + 9
            )

    # Ordenación
    sort_by = request.GET.get('sort', '-rating')
    if sort_by == 'rating_asc':
        ratings_qs = ratings_qs.order_by('rating', 'copy__book__title')
    elif sort_by == 'year_desc':
        ratings_qs = ratings_qs.order_by('-copy__book__publication_year')
    elif sort_by == 'year_old':
        ratings_qs = ratings_qs.order_by('copy__book__publication_year')
    elif sort_by == 'title':
        ratings_qs = ratings_qs.order_by('copy__book__title')
    else:
        ratings_qs = ratings_qs.order_by('-rating', '-created_at')

    # Inyectar géneros y años consolidados en cada objeto de valoración
    ratings_list = list(ratings_qs)
    for r in ratings_list:
        b_id = r.copy.book.book_id
        r.card_genres = [g for g in genre_map.get(b_id, []) if g != 'Desconocido']
        r.card_year = r.copy.book.publication_year or year_map.get(b_id) or 'N/A'

    # Listado completo de géneros disponibles para el selector
    generos_disponibles = []
    if not df_base.empty:
        generos_disponibles = sorted(list(set(g for sub in df_base['genre_list'] for g in sub if g and g != 'Desconocido')))

    context = {
        'user_active': user_id,
        'user_obj': user_obj,
        'ratings': ratings_list,
        'total_valorados': Rating.objects.filter(user__user_id=user_id).count(),
        'generos': generos_disponibles,
        'q': q,
        'rating_filter': rating_filter,
        'genre_filter': genre_filter,
        'decade_filter': decade_filter,
        'sort_by': sort_by,
    }
    return render(request, 'mi_biblioteca.html', context)

def eliminar_valoracion_view(request, rating_id):
    if request.method == 'POST':
        user_id = request.session.get('user_id')
        if user_id:
            try:
                # Se filtra por id y por el usuario en sesión para garantizar seguridad
                Rating.objects.filter(id=rating_id, user__user_id=user_id).delete()
            except:
                pass
    return redirect('mi_biblioteca')