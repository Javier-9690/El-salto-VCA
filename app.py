"""
Comparador de Habitaciones - El Salto vs Hotelería
Flask app con PostgreSQL para persistir el mapa de habitaciones y los reportes.
"""

import os
import io
import re
import csv
import uuid
import json
import gzip
import traceback
import psycopg2
import psycopg2.extras
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB


# ─────────────────────────────────────────────
#  Tablas de lookup El Salto
# ─────────────────────────────────────────────

TABLA_HORARIO = {
    -1: ('Nunca',                    'No válida'),
     0: ('Siempre',                  'No válida'),
     1: ('Calendar general',         'No válida'),
     2: ('Turno 4x3 Lu',             '4x3'),
     3: ('Turno 4x3 Ma',             '4x3'),
     4: ('Turno 5x2',                '5x2'),
     5: ('Turno 6x1',                'Otros'),
     6: ('Turno 7x7 dia',            '7x7 Día'),
     7: ('Turno 14x14 día',          '14x14 Día'),
     8: ('Turno 10x10 día',          '10x10 Día'),
     9: ('Turno 7x7 (Dia-Noche)',    '7x7 Rotativo'),
    10: ('Turno 14X14 (Dia-Noche)',  '14x14 Rotativo'),
    11: ('Turno 10x10 (Dia-Noche)',  '10x10 Rotativo'),
    12: ('Turno 7X7 (Noche)',        '7x7 Rotativo'),
    13: ('Turno 14x14 (Noche)',      '14x14 Rotativo'),
}

TABLA_CALENDARIO = {
     0: ('Calendar general',                          'No válido'),
     1: ('Turno 4x3 Lu',                              '4x3'),
     2: ('Turno 4x3 Ma',                              '4x3'),
     3: ('Turno 5x2',                                 '5x2'),
     4: ('Turno 6x1',                                 'Otro'),
     5: ('Turno 7x7 Ma - A',                          '7x7 día'),
     6: ('Turno 7x7 Ma - B',                          '7x7 día'),
     7: ('Turno 7x7 Mi - A',                          '7x7 día'),
     8: ('Turno 7x7 Mi - B',                          '7x7 día'),
     9: ('Turno 7x7 Ju - A',                          '7x7 día'),
    10: ('Turno 7x7 Ju - B',                          '7x7 día'),
    11: ('Turno 14x14 - B (CD GEOTEC)',               '14x14 día'),
    12: ('Turno 14x14 - A (AB GEOTEC)',               '14x14 día'),
    13: ('Turno 14x14 Mi - A',                        '14x14 día'),
    14: ('Turno 14x14 Mi - B',                        '14x14 día'),
    15: ('Turno 14x14 Ju - A',                        '14x14 día'),
    16: ('Turno 14x14 Ju - B',                        '14x14 día'),
    17: ('Turno 10x10 Aramark T1',                    '10x10 día'),
    18: ('Turno 10x10 Aramark T2',                    '10x10 día'),
    19: ('Turno 10x10 Sodexo T1',                     '10x10 día'),
    20: ('Turno 10x10 Sodexo T2',                     '10x10 día'),
    21: ('Turno 7x7 Ma (Dia-Noche) A',               'Rotativo'),
    22: ('Turno 7x7 Ma (Dia-Noche) B',               'Rotativo'),
    23: ('Turno 7x7 Mi (Dia-Noche) A',               'Rotativo'),
    24: ('Turno 7x7 Mi (Dia-Noche) B',               'Rotativo'),
    25: ('Turno 7x7 Ju (Dia-Noche) A',               'Rotativo'),
    26: ('Turno 7x7 Ju (Dia-Noche) B',               'Rotativo'),
    27: ('Turno 14X14 Ma (Dia-Noche) A',             'Rotativo'),
    28: ('Turno 14X14 Ma (Dia-Noche) B',             'Rotativo'),
    29: ('Turno 14X14 Mi (Dia-Noche) A',             'Rotativo'),
    30: ('Turno 14X14 Mi (Dia-Noche) B',             'Rotativo'),
    31: ('Turno 14X14 Ju (Dia-Noche) A',             'Rotativo'),
    32: ('Turno 14X14 Ju (Dia-Noche) B',             'Rotativo'),
    33: ('Turno 10x10 Aramark T1 (Dia-Noche)',       'Rotativo'),
    34: ('Turno 10x10 Aramark T2 (Dia-Noche)',       'Rotativo'),
    35: ('Turno 10x10 Sodexo T1 (Dia-Noche)',        'Rotativo'),
    36: ('Turno 10x10 Sodexo T2 (Dia-Noche)',        'Rotativo'),
    37: ('Turno 14x14- B (Turno 2 Eleccon)',         '14x14 día'),
    38: ('Turno 14x14- A (Turno 1 Eleccon)',         '14x14 día'),
    39: ('Turno 14x14 Mi - A  (Turno A Asap)',       '14x14 día'),
    40: ('Turno 14x14 Mi - B (Turno B Asap)',        '14x14 día'),
    41: ('Turno 14x14 Ju- A (Turno A Asap)',         '14x14 día'),
    42: ('Turno 14x14 Ju - B ( Turno B Asap)',       '14x14 día'),
    43: ('Turno 14x14 Mi - A (Turno A el Sauce)',    '14x14 día'),
    44: ('Turno 14x14 Mi - B (Turno B el Sauce)',    '14x14 día'),
    45: ('Turno 14x14 Vi - A (Turno C el Sauce)',    '14x14 día'),
    46: ('Turno 14x14 Vi - B (Turno D el Sauce)',    '14x14 día'),
    47: ('Turno 14x14 - B (Turno B QK)',             '14x14 día'),
    48: ('Turno 14x14 - A (Turno A QK)',             '14x14 día'),
    49: ('Turno 7x7 Ma (noche-día) A',               'Rotativo'),
    50: ('Turno 7x7 Ma (noche-día) B',               'Rotativo'),
    51: ('Turno 7x7 Mi (noche-día) A',               'Rotativo'),
    52: ('Turno 7x7 Mi (noche-día) B',               'Rotativo'),
    53: ('Turno 7x7 Ju (noche-día) A',               'Rotativo'),
    54: ('Turno 7x7 Ju (noche-día) B',               'Rotativo'),
    55: ('Turno 14x14 Ma (noche-día) B',             'Rotativo'),
}

TABLA_KEY_STATUS = {
    0: 'Llave no asignada',
    1: 'Actualización no requerida',
    2: 'Actualización requerida',
    3: 'Reedición requerida',
    4: 'Llave expirada',
}


# ─────────────────────────────────────────────
#  Base de datos PostgreSQL
# ─────────────────────────────────────────────

def get_db():
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise RuntimeError("Variable DATABASE_URL no configurada.")
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(url, sslmode='require')


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracion (
                    clave       TEXT PRIMARY KEY,
                    valor       TEXT,
                    updated_at  TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS comparaciones (
                    token       TEXT PRIMARY KEY,
                    excel_data  BYTEA NOT NULL,
                    created_at  TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                DELETE FROM comparaciones
                WHERE created_at < NOW() - INTERVAL '7 days';
            """)
        conn.commit()


def guardar_mapa_db(df):
    data = df.to_json(orient='records', force_ascii=False)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO configuracion (clave, valor, updated_at)
                VALUES ('mapa', %s, NOW())
                ON CONFLICT (clave) DO UPDATE
                    SET valor = EXCLUDED.valor,
                        updated_at = NOW();
            """, (data,))
        conn.commit()


def cargar_mapa_db():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT valor, updated_at FROM configuracion WHERE clave = 'mapa';"
                )
                row = cur.fetchone()
                if row and row[0]:
                    df = pd.DataFrame(json.loads(row[0]))
                    df = df.fillna('').astype(str)
                    return df, row[1]
    except Exception:
        pass
    return None, None


def _make_json_safe(obj):
    """Convierte recursivamente a tipos nativos serializables en JSON."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj)
    if obj is None:
        return None
    return str(obj)


def guardar_resultados_db(token, results):
    """Guarda los resultados como JSON comprimido (gzip) — sin generar Excel."""
    payload = json.dumps(_make_json_safe(results), ensure_ascii=False).encode('utf-8')
    compressed = gzip.compress(payload, compresslevel=6)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO comparaciones (token, excel_data, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (token) DO UPDATE
                    SET excel_data = EXCLUDED.excel_data,
                        created_at = NOW();
            """, (token, psycopg2.Binary(compressed)))
        conn.commit()


def cargar_resultados_db(token):
    """Carga y descomprime los resultados; genera Excel en el momento de descarga."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT excel_data FROM comparaciones WHERE token = %s;",
                    (token,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    decompressed = gzip.decompress(bytes(row[0]))
                    return json.loads(decompressed.decode('utf-8'))
    except Exception:
        pass
    return None


try:
    init_db()
except Exception as e:
    print(f"[WARN] No se pudo inicializar la BD: {e}")


# ─────────────────────────────────────────────
#  Utilidades generales
# ─────────────────────────────────────────────

def limpiar(val):
    if pd.isna(val):
        return ''
    return str(val).strip()


def norm_rut(val):
    if pd.isna(val):
        return ''
    return str(val).strip().upper().replace('.', '').replace(' ', '')


def quitar_tildes(texto):
    reemplazos = {
        'Á':'A','É':'E','Í':'I','Ó':'O','Ú':'U','Ü':'U','Ñ':'N',
        'á':'a','é':'e','í':'i','ó':'o','ú':'u','ü':'u','ñ':'n',
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto


def normalizar_col(texto):
    return quitar_tildes(str(texto).strip().upper().replace('\n', ' ').replace('  ', ' '))


def buscar_col(df, nombres):
    mapa = {normalizar_col(c): c for c in df.columns}
    for nombre in nombres:
        if normalizar_col(nombre) in mapa:
            return mapa[normalizar_col(nombre)]
    return None


def leer_excel(data_bytes):
    magic  = data_bytes[:4]
    engine = 'openpyxl' if magic[:2] == b'PK' else 'xlrd'
    df_raw = pd.read_excel(io.BytesIO(data_bytes), dtype=str,
                           engine=engine, header=None).fillna('')
    header_row = 0
    for i in range(min(5, len(df_raw))):
        celdas = [c for c in df_raw.iloc[i]
                  if str(c).strip() and len(str(c).strip()) <= 40]
        if len(celdas) >= 3:
            header_row = i
            break
    df = pd.read_excel(io.BytesIO(data_bytes), dtype=str,
                       engine=engine, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna('')
    df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
    return df


def _es_csv(data_bytes):
    """Devuelve True si el archivo es CSV (no xlsx ni xls)."""
    return not (data_bytes[:2] == b'PK' or data_bytes[:2] == b'\xd0\xcf')


# ─────────────────────────────────────────────
#  Utilidades específicas CSV El Salto
# ─────────────────────────────────────────────

def parse_door_list(val):
    """
    Extrae (nombre_puerta_principal, tabla_horario_id, lista_todas_puertas) del formato:
    {{"VCA-M26-P1-L2601-2",6,,}}  o  {{"PUERTA-A",6,,},{"PUERTA-B",0,,}}
    Retorna la primera puerta como principal; todas en lista.
    """
    val = str(val).strip()
    if not val or val in ('', '{}', '{{}}', '{{,}}'):
        return '', -1, []
    matches = re.findall(r'"([^"]+)",\s*(-?\d+)', val)
    if matches:
        all_doors = [m[0].strip() for m in matches]
        door_name, horario_id_str = matches[0]
        return door_name.strip(), int(horario_id_str), all_doors
    m = re.search(r'"([^"]+)"', val)
    if m:
        return m.group(1).strip(), -1, [m.group(1).strip()]
    return '', -1, []


def leer_csv_salto(data_bytes):
    """
    Lee el CSV de exportación del sistema El Salto y devuelve un
    DataFrame normalizado con todas las columnas enriquecidas.
    """
    content = None
    for enc in ('latin-1', 'cp1252', 'utf-8', 'utf-8-sig'):
        try:
            content = data_bytes.decode(enc)
            break
        except Exception:
            continue
    if content is None:
        raise ValueError("No se pudo leer el CSV: encoding desconocido.")

    reader = csv.DictReader(io.StringIO(content), delimiter=';', quotechar='"')
    rows = list(reader)

    records = []
    for r in rows:
        ext_id     = r.get('ExtID', '').strip().strip('"')
        first_name = r.get('FirstName', '').strip().strip('"')
        cal_str    = r.get('CalendarID', '').strip().strip('"')
        key_str    = r.get('CurrentKeyStatus', '').strip().strip('"')
        door_raw   = r.get('ExtDoorIDList', '').strip()

        # CalendarID → Calendario
        try:
            cal_id = int(cal_str) if cal_str else 0
        except ValueError:
            cal_id = 0
        cal_nombre, cal_tipo = TABLA_CALENDARIO.get(
            cal_id, (f'ID {cal_id} (Desconocido)', 'Desconocido'))

        # CurrentKeyStatus → Estado Llave
        try:
            key_status = int(key_str) if key_str else 0
        except ValueError:
            key_status = 0
        estado_llave = TABLA_KEY_STATUS.get(key_status, f'Estado {key_status}')

        # ExtDoorIDList → Puerta + Tabla Horario + todas las puertas
        door_name, horario_id, all_doors = parse_door_list(door_raw)
        hor_nombre, hor_clasif = TABLA_HORARIO.get(
            horario_id, (f'ID {horario_id} (Desconocido)', 'Desconocido'))

        records.append({
            'ExtID':               ext_id,
            'FullName':            first_name,
            'NameDoorList':        door_name,
            'TodasLasPuertas':     ' | '.join(all_doors),
            'CantidadPuertas':     len(all_doors),
            'TablaHorarioID':      horario_id,
            'TablaHorario':        hor_nombre,
            'ClasifTablaHorario':  hor_clasif,
            'CalendarID':          cal_id,
            'Calendario':          cal_nombre,
            'TipoCalendario':      cal_tipo,
            'EstadoLlave':         estado_llave,
        })

    df = pd.DataFrame(records).fillna('')
    return df


# ─────────────────────────────────────────────
#  Procesamiento principal
# ─────────────────────────────────────────────

def _calcular_resumen_ejecutivo(df_sal, df_hot, df_map,
                                sal_idx, hot_idx, comunes,
                                hot_hab, hot_mod,
                                map_nm, map_hab, map_camp):
    """
    Calcula el resumen ejecutivo por campamento — versión vectorizada (pandas).
    Retorna una lista de dicts, uno por campamento + fila TOTAL si hay más de uno.
    """
    invalid_cal  = frozenset(('No válido', 'No válida', 'Desconocido', ''))
    invalid_hor  = frozenset(('No válida', 'Desconocido', ''))
    needs_update = frozenset(('Actualización requerida', 'Reedición requerida', 'Llave expirada'))
    hot_ruts_set = frozenset(hot_idx.keys())
    comunes_set  = frozenset(comunes)

    def pct(n, d):
        return round(n / d * 100) if d else 0

    # ── Mapas campamento (sólo el mapa es pequeño, iterrows OK) ──
    hab_to_camp  = {}
    door_to_camp = {}
    if map_hab and map_camp:
        for _, f in df_map.iterrows():
            h = limpiar(f.get(map_hab, '')).upper()
            c = limpiar(f.get(map_camp, ''))
            if h and c:
                hab_to_camp[h] = c
    if map_nm and map_camp:
        for _, f in df_map.iterrows():
            n = limpiar(f.get(map_nm, '')).upper()
            c = limpiar(f.get(map_camp, ''))
            if n and c:
                door_to_camp[n] = c

    # ── Series de campamento (vectorizado, sin iterrows sobre CSV) ─
    if door_to_camp:
        sal_camp_s = (df_sal['NameDoorList'].fillna('').str.upper()
                      .map(door_to_camp).fillna('Sin mapa'))
    else:
        sal_camp_s = pd.Series('VCA', index=df_sal.index)

    if hab_to_camp and hot_hab:
        hot_camp_s = (df_hot[hot_hab].fillna('').str.upper()
                      .map(hab_to_camp).fillna('Sin mapa'))
    else:
        hot_camp_s = pd.Series('VCA', index=df_hot.index)

    # ── Boolean Series sobre df_sal (una sola pasada, vectorizado) ─
    sal_tiene_hab = df_sal['NameDoorList'].fillna('') != ''
    sal_tiene_cal = ~df_sal['TipoCalendario'].fillna('').isin(invalid_cal)
    sal_tiene_hor = ~df_sal['ClasifTablaHorario'].fillna('').isin(invalid_hor)
    sal_en_hot    = df_sal['_RUT'].isin(hot_ruts_set)
    sal_en_comun  = df_sal['_RUT'].isin(comunes_set)
    sal_act       = df_sal['EstadoLlave'].fillna('').isin(needs_update)
    sal_con_todo  = sal_tiene_hab & sal_tiene_cal & sal_tiene_hor

    # ── Determinar campamentos (incluye 'Sin mapa' al final) ─────
    named_camps = sorted(
        set(list(hab_to_camp.values()) + list(door_to_camp.values())) - {''} - {'Sin mapa'}
    ) or ['VCA']
    all_camps = named_camps + ['Sin mapa']

    filas = []
    for camp in all_camps:
        sal_mask = sal_camp_s == camp
        hot_mask = hot_camp_s == camp

        # SALTO side — todo vectorizado
        sal_total   = int(sal_mask.sum())
        sal_con_hab = int((sal_mask & sal_tiene_hab).sum())
        sal_con_cal = int((sal_mask & sal_tiene_cal).sum())
        sal_con_hor = int((sal_mask & sal_tiene_hor).sum())
        visitas     = int((sal_mask & ~sal_en_hot).sum())

        # HOTELERÍA side
        hot_total     = int(hot_mask.sum())
        hot_camp_ruts = frozenset(df_hot.loc[hot_mask, '_RUT'])
        hot_comunes_n = len(hot_camp_ruts & comunes_set)

        # Métricas sobre comunes de este campamento (vectorizado)
        com_mask     = sal_mask & sal_en_comun & df_sal['_RUT'].isin(hot_camp_ruts)
        hot_con_cal  = int((com_mask & sal_tiene_cal).sum())
        hot_con_hor  = int((com_mask & sal_tiene_hor).sum())
        hot_con_todo = int((com_mask & sal_con_todo).sum())
        hot_act      = int((com_mask & sal_act).sum())

        filas.append({
            'Campamento':            camp,
            # SALTO
            'SAL_Total':             sal_total,
            'SAL_Con Hab':           sal_con_hab,
            'SAL_Con Calendario':    sal_con_cal,
            'SAL_Con Tabla Horario': sal_con_hor,
            'SAL_Visitas':           visitas,
            # HOTELERÍA
            'HOT_Total':             hot_total,
            'HOT_Con Hab en Salto':  hot_comunes_n,
            'HOT_pct_Hab':           pct(hot_comunes_n, hot_total),
            'HOT_Con Calendario':    hot_con_cal,
            'HOT_pct_Cal':           pct(hot_con_cal,   hot_total),
            'HOT_Con Tabla Horario': hot_con_hor,
            'HOT_pct_Hor':           pct(hot_con_hor,   hot_total),
            'HOT_Con Todo':          hot_con_todo,
            'HOT_pct_Todo':          pct(hot_con_todo,  hot_total),
            'HOT_Act Tarjetas':      hot_act,
            'HOT_pct_Act':           pct(hot_act,       hot_total),
        })

    # ── Fila TOTAL (si hay más de un campamento) ──────────────────
    if len(filas) > 1:
        num_keys = [k for k in filas[0] if k != 'Campamento' and 'pct' not in k]
        total = {'Campamento': 'TOTAL'}
        for k in num_keys:
            total[k] = sum(f[k] for f in filas)
        total['HOT_pct_Hab']  = pct(total['HOT_Con Hab en Salto'],  total['HOT_Total'])
        total['HOT_pct_Cal']  = pct(total['HOT_Con Calendario'],    total['HOT_Total'])
        total['HOT_pct_Hor']  = pct(total['HOT_Con Tabla Horario'], total['HOT_Total'])
        total['HOT_pct_Todo'] = pct(total['HOT_Con Todo'],          total['HOT_Total'])
        total['HOT_pct_Act']  = pct(total['HOT_Act Tarjetas'],      total['HOT_Total'])
        filas.append(total)

    return filas


def procesar(mapa_bytes_o_df, salto_bytes, hotel_bytes):
    # ── Mapa ──────────────────────────────────────────────────────
    if isinstance(mapa_bytes_o_df, pd.DataFrame):
        df_map = mapa_bytes_o_df
    else:
        df_map = leer_excel(mapa_bytes_o_df)

    # ── El Salto: detectar CSV o Excel ────────────────────────────
    es_csv_salto = _es_csv(salto_bytes)
    if es_csv_salto:
        df_sal = leer_csv_salto(salto_bytes)
    else:
        df_sal = leer_excel(salto_bytes)

    # ── Hotelería ─────────────────────────────────────────────────
    df_hot = leer_excel(hotel_bytes)

    for df in [df_map, df_sal, df_hot]:
        df.columns = [str(c).strip() for c in df.columns]
        df.fillna('', inplace=True)

    # ── Columnas Mapa ──────────────────────────────────────────────
    map_hab  = buscar_col(df_map, ['HABITACIÓN', 'HABITACION', 'HAB'])
    map_nm   = buscar_col(df_map, ['NM SALTO', 'NM_SALTO', 'NMSALTO'])
    map_camp = buscar_col(df_map, ['CAMPAMENTO'])
    map_mod  = buscar_col(df_map, ['MÓDULO', 'MODULO'])
    map_piso = buscar_col(df_map, ['PISO'])

    # ── Columnas El Salto ──────────────────────────────────────────
    if es_csv_salto:
        sal_ext  = 'ExtID'
        sal_door = 'NameDoorList'
        sal_name = 'FullName'
    else:
        sal_ext  = buscar_col(df_sal, ['ExtID', 'EXTID', 'EXT ID'])
        sal_door = buscar_col(df_sal, ['NameDoorList', 'NAMEDOORLIST', 'NAME DOOR LIST'])
        sal_name = buscar_col(df_sal, ['FullName', 'FULLNAME', 'FULL NAME'])

    # ── Columnas Hotelería ─────────────────────────────────────────
    hot_hab   = buscar_col(df_hot, ['HABITACIÓN', 'HABITACION', 'HAB',
                                     'N° HAB', 'N°HAB', 'NRO HAB',
                                     'NUMERO HABITACION', 'NUMERO HABITACIÓN'])
    hot_rut   = buscar_col(df_hot, ['RUT', 'RUT TRABAJADOR', 'RUT_TRABAJADOR',
                                     'RUTTRABAJADOR', 'RUT PERSONA', 'DNI'])
    hot_nom   = buscar_col(df_hot, ['NOMBRE', 'NOMBRE COMPLETO', 'NOMBRES'])
    hot_emp   = buscar_col(df_hot, ['EMPRESA'])
    hot_mod   = buscar_col(df_hot, ['MÓDULO', 'MODULO'])
    hot_cont  = buscar_col(df_hot, ['N°CONTRATO', 'N CONTRATO', 'NCONTRATO',
                                     'NUMERO CONTRATO', 'N° CONTRATO'])
    hot_ger   = buscar_col(df_hot, ['GERENCIA'])
    hot_turno = buscar_col(df_hot, ['SISTEMA TURNO', 'SISTEMATURNO', 'TURNO',
                                     'SISTEMA\nTURNO', 'SISTEMA_TURNO'])

    faltantes = []
    if not map_hab:  faltantes.append("HABITACIÓN  →  Mapa de habitaciones")
    if not map_nm:   faltantes.append("NM SALTO    →  Mapa de habitaciones")
    if not sal_door: faltantes.append("NameDoorList / ExtDoorIDList  →  Base El Salto")
    if not hot_hab:  faltantes.append("HABITACIÓN  →  Base de datos Hotelería")
    if not hot_rut:  faltantes.append("RUT         →  Base de datos Hotelería")
    if faltantes:
        raise ValueError(
            "Columnas no encontradas:\n" + "\n".join(faltantes) +
            f"\n\n── Columnas detectadas en Hotelería ──\n{list(df_hot.columns)}" +
            f"\n\n── Columnas detectadas en El Salto ──\n{list(df_sal.columns)}" +
            f"\n\n── Columnas detectadas en Mapa ──\n{list(df_map.columns)}"
        )

    # ── Mapeo bidireccional de habitaciones ───────────────────────
    h2n, n2h = {}, {}
    for _, fila in df_map.iterrows():
        h = limpiar(fila.get(map_hab, '')).upper()
        n = limpiar(fila.get(map_nm,  '')).upper()
        if h and n:
            h2n[h] = n
            n2h[n] = limpiar(fila.get(map_hab, ''))

    # ── Normalizar ────────────────────────────────────────────────
    df_hot['_RUT']    = df_hot[hot_rut].apply(norm_rut)
    df_sal['_RUT']    = df_sal[sal_ext].apply(norm_rut)
    df_hot['_HAB']    = df_hot[hot_hab].apply(lambda x: limpiar(x).upper())
    df_sal['_DOOR']   = df_sal[sal_door].apply(lambda x: limpiar(x).upper())
    df_hot['_NM_EQ']  = df_hot['_HAB'].map(h2n)
    df_sal['_HAB_EQ'] = df_sal['_DOOR'].map(n2h)

    # ── Detectar RUTs duplicados antes de deduplicar ─────────────
    def _get_duplicados(df, col_rut, col_nombre, col_extra=None):
        """Retorna lista de dicts con los RUTs que aparecen más de una vez."""
        dup_mask = df[col_rut].duplicated(keep=False) & (df[col_rut] != '')
        dup_df   = df[dup_mask].copy()
        if dup_df.empty:
            return []
        result = []
        for rut, grupo in dup_df.groupby(col_rut):
            for _, row in grupo.iterrows():
                rec = {'RUT': rut, 'Nombre': limpiar(row.get(col_nombre, ''))}
                if col_extra:
                    for label, col in col_extra.items():
                        rec[label] = limpiar(row.get(col, '')) if col else ''
                result.append(rec)
        return result

    ruts_dup_hot = _get_duplicados(
        df_hot[df_hot['_RUT'] != ''], '_RUT', hot_nom,
        {'HAB': hot_hab, 'Empresa': hot_emp, 'Módulo': hot_mod}
    ) if hot_nom else []

    ruts_dup_sal = _get_duplicados(
        df_sal[df_sal['_RUT'] != ''], '_RUT', sal_name or 'FullName',
        {'HAB El Salto': sal_door}
    ) if es_csv_salto else []

    # ── Índices por RUT (keep='last' = mismo comportamiento que dict comp.) ─
    _hot_nonempty = df_hot[df_hot['_RUT'] != ''].drop_duplicates(subset='_RUT', keep='last')
    hot_idx = _hot_nonempty.set_index('_RUT').to_dict('index')

    _sal_nonempty = df_sal[df_sal['_RUT'] != ''].drop_duplicates(subset='_RUT', keep='last')
    sal_idx = _sal_nonempty.set_index('_RUT').to_dict('index')

    comunes    = sorted(set(hot_idx) & set(sal_idx))
    solo_hot_k = sorted(set(hot_idx) - set(sal_idx))
    solo_sal_k = sorted(set(sal_idx) - set(hot_idx))

    # ── Helper para columnas extra del CSV ────────────────────────
    def extra_sal(row):
        if not es_csv_salto:
            return {}
        return {
            'Calendario':         limpiar(row.get('Calendario', '')),
            'Tipo Calendario':    limpiar(row.get('TipoCalendario', '')),
            'Tabla Horario':      limpiar(row.get('TablaHorario', '')),
            'Clasif. Horario':    limpiar(row.get('ClasifTablaHorario', '')),
            'Estado Llave':       limpiar(row.get('EstadoLlave', '')),
        }

    # ── Comparación por RUT ───────────────────────────────────────
    discrepancias, coincidencias = [], []
    for rut in comunes:
        h = hot_idx[rut]; s = sal_idx[rut]
        nm_eq    = limpiar(h.get('_NM_EQ',  ''))
        door     = limpiar(s['_DOOR'])
        hab_eq   = limpiar(s.get('_HAB_EQ', ''))
        coincide = bool(nm_eq) and nm_eq.upper() == door.upper()
        rec = {
            'RUT':               rut,
            'Nombre Hotelería':  limpiar(h.get(hot_nom, '')) if hot_nom else '',
            'Nombre El Salto':   limpiar(s.get(sal_name, '')) if sal_name else '',
            'HAB Hotelería':     limpiar(h.get(hot_hab, '')),
            'HAB El Salto':      limpiar(s.get(sal_door, '')),
            'Equiv Hotel→Salto': nm_eq,
            'Equiv Salto→Hotel': hab_eq,
            'Empresa':           limpiar(h.get(hot_emp, ''))  if hot_emp  else '',
            'Módulo':            limpiar(h.get(hot_mod, ''))  if hot_mod  else '',
            'Gerencia':          limpiar(h.get(hot_ger, ''))  if hot_ger  else '',
            **extra_sal(s),
        }
        (coincidencias if coincide else discrepancias).append(rec)

    solo_hotel = [{
        'RUT':        rut,
        'Nombre':     limpiar(hot_idx[rut].get(hot_nom,  '')) if hot_nom  else '',
        'HABITACIÓN': limpiar(hot_idx[rut].get(hot_hab,  '')),
        'Empresa':    limpiar(hot_idx[rut].get(hot_emp,  '')) if hot_emp  else '',
        'Módulo':     limpiar(hot_idx[rut].get(hot_mod,  '')) if hot_mod  else '',
        'N°Contrato': limpiar(hot_idx[rut].get(hot_cont, '')) if hot_cont else '',
        'Gerencia':   limpiar(hot_idx[rut].get(hot_ger,  '')) if hot_ger  else '',
        'Turno':      limpiar(hot_idx[rut].get(hot_turno,'')) if hot_turno else '',
    } for rut in solo_hot_k]

    solo_salto = [{
        'RUT/ExtID':       rut,
        'Nombre':          limpiar(sal_idx[rut].get(sal_name, '')) if sal_name else '',
        'HAB El Salto':    limpiar(sal_idx[rut].get(sal_door, '')),
        'HAB Equivalente': limpiar(sal_idx[rut].get('_HAB_EQ', '')),
        **extra_sal(sal_idx[rut]),
    } for rut in solo_sal_k]

    # ── Sin mapa (vectorizado) ────────────────────────────────────
    hab_sin_mapa = sorted(
        df_hot.loc[df_hot['_NM_EQ'].fillna('') == '', hot_hab]
              .apply(limpiar).replace('', pd.NA).dropna().unique().tolist()
    )
    door_sin_mapa = sorted(
        df_sal.loc[df_sal['_HAB_EQ'].fillna('') == '', sal_door]
              .apply(limpiar).replace('', pd.NA).dropna().unique().tolist()
    )

    # ── Usuarios con más de una habitación (El Salto) ────────────
    multi_hab = []
    if es_csv_salto and 'CantidadPuertas' in df_sal.columns:
        hot_ruts_for_multi = frozenset(hot_idx.keys())
        df_multi = df_sal[df_sal['CantidadPuertas'] > 1].copy()
        for rut, row in df_multi.set_index('_RUT').to_dict('index').items():
            en_hot = rut in hot_ruts_for_multi
            h      = hot_idx[rut] if en_hot else {}
            multi_hab.append({
                'RUT/ExtID':      rut,
                'Nombre':         limpiar(row.get('FullName', '')),
                'En Hotelería':   'Sí' if en_hot else 'No (visita)',
                'HAB Hotelería':  limpiar(h.get(hot_hab, '')) if (en_hot and hot_hab) else '',
                'N° Puertas':     int(row.get('CantidadPuertas', 0)),
                'Todas las HAB':  limpiar(row.get('TodasLasPuertas', '')),
                'Empresa':        limpiar(h.get(hot_emp, '')) if (en_hot and hot_emp) else '',
                'Módulo':         limpiar(h.get(hot_mod, '')) if (en_hot and hot_mod) else '',
                'Calendario':     limpiar(row.get('Calendario', '')),
                'Tipo Calendario':limpiar(row.get('TipoCalendario', '')),
                'Estado Llave':   limpiar(row.get('EstadoLlave', '')),
            })

    # ── Sin Calendario / Sin Tabla Horario ───────────────────────
    # sin_calendario / sin_tabla_horario → solo usuarios en AMBAS bases (Hotelería)
    # sal_sin_calendario / sal_sin_tabla_horario → TODOS los usuarios de El Salto
    sin_calendario       = []
    sin_tabla_horario    = []
    sal_sin_calendario   = []
    sal_sin_tabla_horario = []

    invalid_cal_set = frozenset(('No válido', 'No válida', 'Desconocido', ''))
    invalid_hor_set = frozenset(('No válida', 'Desconocido', ''))

    if es_csv_salto:
        hot_ruts_set  = frozenset(hot_idx.keys())
        comunes_set   = frozenset(comunes)

        for rut, row in sal_idx.items():
            en_hot = rut in hot_ruts_set
            h      = hot_idx[rut] if en_hot else {}

            # Registro enriquecido con datos de Hotelería cuando están disponibles
            rec_sal = {
                'RUT/ExtID':       rut,
                'Nombre':          limpiar(row.get('FullName', '')),
                'En Hotelería':    'Sí' if en_hot else 'No (visita)',
                'HAB El Salto':    limpiar(row.get('NameDoorList', '')),
                'Calendario':      limpiar(row.get('Calendario', '')),
                'Tipo Calendario': limpiar(row.get('TipoCalendario', '')),
                'Tabla Horario':   limpiar(row.get('TablaHorario', '')),
                'Clasif. Horario': limpiar(row.get('ClasifTablaHorario', '')),
                'Estado Llave':    limpiar(row.get('EstadoLlave', '')),
            }
            cal_invalido = limpiar(row.get('TipoCalendario', '')) in invalid_cal_set
            hor_invalido = limpiar(row.get('ClasifTablaHorario', '')) in invalid_hor_set

            if cal_invalido:
                sal_sin_calendario.append(rec_sal)
            if hor_invalido:
                sal_sin_tabla_horario.append(rec_sal)

            # Solo comunes → listas originales con datos Hotelería completos
            if rut in comunes_set:
                rec_hot = {
                    'RUT/ExtID':       rut,
                    'Nombre':          limpiar(row.get('FullName', '')),
                    'HAB Hotelería':   limpiar(h.get(hot_hab, '')) if hot_hab else '',
                    'HAB El Salto':    limpiar(row.get('NameDoorList', '')),
                    'Empresa':         limpiar(h.get(hot_emp, ''))  if hot_emp  else '',
                    'Módulo':          limpiar(h.get(hot_mod, ''))  if hot_mod  else '',
                    'Calendario':      limpiar(row.get('Calendario', '')),
                    'Tipo Calendario': limpiar(row.get('TipoCalendario', '')),
                    'Tabla Horario':   limpiar(row.get('TablaHorario', '')),
                    'Clasif. Horario': limpiar(row.get('ClasifTablaHorario', '')),
                    'Estado Llave':    limpiar(row.get('EstadoLlave', '')),
                }
                if cal_invalido:
                    sin_calendario.append(rec_hot)
                if hor_invalido:
                    sin_tabla_horario.append(rec_hot)

    # ── Métricas de cumplimiento ──────────────────────────────────
    total_comunes = len(comunes)
    pct_concordancia = round(len(coincidencias) / total_comunes * 100, 1) if total_comunes else 0.0
    pct_cobertura    = round(total_comunes / len(hot_idx) * 100, 1) if hot_idx else 0.0

    total_habs_hotel = int(
        df_hot[hot_hab].apply(limpiar).replace('', pd.NA).dropna().nunique()
    )
    habs_con_mapa = total_habs_hotel - len(hab_sin_mapa)
    pct_mapa = round(habs_con_mapa / total_habs_hotel * 100, 1) if total_habs_hotel else 0.0
    # guardamos para mostrar en dashboard
    _habs_con_mapa    = habs_con_mapa
    _total_habs_hotel = total_habs_hotel

    if es_csv_salto and total_comunes:
        pct_calendario = round((total_comunes - len(sin_calendario)) / total_comunes * 100, 1)
        pct_horario    = round((total_comunes - len(sin_tabla_horario)) / total_comunes * 100, 1)
    else:
        pct_calendario = None
        pct_horario    = None

    # ── Resumen Ejecutivo por Campamento ─────────────────────────
    resumen_ejecutivo = None
    if es_csv_salto:
        resumen_ejecutivo = _calcular_resumen_ejecutivo(
            df_sal, df_hot, df_map,
            sal_idx, hot_idx, comunes,
            hot_hab, hot_mod,
            map_nm, map_hab, map_camp
        )

    return {
        'discrepancias':     discrepancias,
        'coincidencias':     coincidencias,
        'solo_hotel':        solo_hotel,
        'solo_salto':        solo_salto,
        'hab_sin_mapa':      hab_sin_mapa,
        'door_sin_mapa':     door_sin_mapa,
        'sin_calendario':        sin_calendario,
        'sin_tabla_horario':     sin_tabla_horario,
        'sal_sin_calendario':    sal_sin_calendario,
        'sal_sin_tabla_horario': sal_sin_tabla_horario,
        'multi_hab':             multi_hab,
        'es_csv_salto':          es_csv_salto,
        'resumen_ejecutivo': resumen_ejecutivo,
        'ruts_dup_hot':      ruts_dup_hot,
        'ruts_dup_sal':      ruts_dup_sal,
        'stats': {
            'total_hotel':       len(df_hot),
            'total_salto':       len(df_sal),
            'total_mapa':        len(df_map),
            'total_comunes':     total_comunes,
            'coincidencias':     len(coincidencias),
            'discrepancias':     len(discrepancias),
            'solo_hotel':        len(solo_hotel),
            'solo_salto':        len(solo_salto),
            'hab_sin_mapa':      len(hab_sin_mapa),
            'door_sin_mapa':     len(door_sin_mapa),
            'ruts_dup_hot':           len(ruts_dup_hot),
            'ruts_dup_sal':           len(ruts_dup_sal),
            'sal_sin_calendario':     len(sal_sin_calendario),
            'sal_sin_tabla_horario':  len(sal_sin_tabla_horario),
            'multi_hab':              len(multi_hab),
            'sin_calendario':    len(sin_calendario),
            'sin_tabla_horario': len(sin_tabla_horario),
            # Porcentajes de cumplimiento
            'pct_concordancia':   pct_concordancia,
            'pct_cobertura':      pct_cobertura,
            'pct_mapa':           pct_mapa,
            'pct_calendario':     pct_calendario,
            'pct_horario':        pct_horario,
            # Para sublabels del dashboard
            'habs_con_mapa':      _habs_con_mapa,
            'total_habs_hotel':   _total_habs_hotel,
        },
    }


# ─────────────────────────────────────────────
#  Generación de Excel de resultados
# ─────────────────────────────────────────────

ROJO     = PatternFill("solid", fgColor="FFB3B3")
VERDE    = PatternFill("solid", fgColor="B3FFB3")
NARANJA  = PatternFill("solid", fgColor="FFE5B3")
AZUL     = PatternFill("solid", fgColor="B3D9FF")
MORADO   = PatternFill("solid", fgColor="E8D5FF")
AMARILLO = PatternFill("solid", fgColor="FFF9C4")
GRIS     = PatternFill("solid", fgColor="E0E0E0")
HEADER   = PatternFill("solid", fgColor="1F3864")
FHEADER  = Font(bold=True, color="FFFFFF", size=11)
FCELL    = Font(size=10)
ALIGN_C  = Alignment(horizontal='center', vertical='center', wrap_text=True)
ALIGN_L  = Alignment(horizontal='left',   vertical='center', wrap_text=True)


def _woc(ws, value, fill=None, font=None, align=None):
    """Crea un WriteOnlyCell con estilo opcional."""
    from openpyxl.cell.cell import WriteOnlyCell
    c = WriteOnlyCell(ws, value=value)
    if fill:  c.fill  = fill
    if font:  c.font  = font
    if align: c.alignment = align
    return c


def _escribir_hoja(ws, datos, fill_fila=None):
    """Escribe datos en modo write-only (streaming) — sin cargar todo en RAM."""
    if not datos:
        ws.append([_woc(ws, "Sin registros", fill=GRIS)])
        return
    headers = list(datos[0].keys())
    # Anchos automáticos basados en el nombre del header
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(len(str(h)) + 4, 12), 45)
    ws.row_dimensions[1].height = 30
    # Cabecera
    ws.append([_woc(ws, h, fill=HEADER, font=FHEADER, align=ALIGN_C) for h in headers])
    # Datos (fila a fila, sin mantener en memoria)
    for fila in datos:
        ws.append([
            _woc(ws, fila.get(h, ''), fill=fill_fila, font=FCELL, align=ALIGN_L)
            for h in headers
        ])


def generar_excel(results):
    """Genera el Excel en modo write_only (streaming) — rápido y bajo en RAM."""
    wb = Workbook(write_only=True)

    # ── Resumen Ejecutivo + Glosario (primeras hojas) ─────────────
    if results.get('resumen_ejecutivo'):
        ws_res = wb.create_sheet("Resumen Ejecutivo")
        _escribir_resumen_excel(ws_res, results['resumen_ejecutivo'])
        ws_glo = wb.create_sheet("Glosario")
        _escribir_glosario_excel(ws_glo)

    # ── Hojas de datos ────────────────────────────────────────────
    ws1 = wb.create_sheet("Discrepancias RUT")
    _escribir_hoja(ws1, results['discrepancias'], ROJO)

    ws2 = wb.create_sheet("Solo en Hotelería")
    _escribir_hoja(ws2, results['solo_hotel'], NARANJA)

    ws3 = wb.create_sheet("Solo en El Salto")
    _escribir_hoja(ws3, results['solo_salto'], AZUL)

    ws4 = wb.create_sheet("Coincidencias")
    _escribir_hoja(ws4, results['coincidencias'], VERDE)

    if results.get('sin_calendario'):
        ws5 = wb.create_sheet("Sin Cal. (Hotelería)")
        _escribir_hoja(ws5, results['sin_calendario'], MORADO)

    if results.get('sin_tabla_horario'):
        ws6 = wb.create_sheet("Sin Hor. (Hotelería)")
        _escribir_hoja(ws6, results['sin_tabla_horario'], AMARILLO)

    if results.get('sal_sin_calendario'):
        ws7 = wb.create_sheet("Sin Cal. (El Salto)")
        _escribir_hoja(ws7, results['sal_sin_calendario'], MORADO)

    if results.get('sal_sin_tabla_horario'):
        ws8 = wb.create_sheet("Sin Hor. (El Salto)")
        _escribir_hoja(ws8, results['sal_sin_tabla_horario'], AMARILLO)

    if results.get('multi_hab'):
        ws9 = wb.create_sheet("Multi Habitación")
        _escribir_hoja(ws9, results['multi_hab'], NARANJA)

    for titulo, lista in [("Sin mapa (Hotelería)", results.get('hab_sin_mapa', [])),
                          ("Sin mapa (El Salto)",  results.get('door_sin_mapa', []))]:
        ws = wb.create_sheet(titulo)
        ws.column_dimensions['A'].width = 42
        ws.append([_woc(ws, "Habitaciones sin equivalente", fill=HEADER, font=FHEADER)])
        for item in lista:
            ws.append([_woc(ws, item)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _escribir_resumen_excel(ws, filas):
    """Resumen Ejecutivo en modo write-only (sin merge_cells)."""
    F_SALTO  = PatternFill("solid", fgColor="2F6496")
    F_HOT    = PatternFill("solid", fgColor="C55A11")
    F_TODO   = PatternFill("solid", fgColor="922B21")
    F_ACT    = PatternFill("solid", fgColor="7F7F7F")
    F_VIS    = PatternFill("solid", fgColor="1F5C99")
    F_CAMP   = PatternFill("solid", fgColor="1A1A2E")
    F_TOTAL  = PatternFill("solid", fgColor="EDEDED")
    F_DATA_S = PatternFill("solid", fgColor="D6E4F0")
    F_DATA_H = PatternFill("solid", fgColor="FDEBD0")
    F_DATA_T = PatternFill("solid", fgColor="FADBD8")
    F_DATA_A = PatternFill("solid", fgColor="EAECEE")
    F_PCT    = PatternFill("solid", fgColor="FDFEFE")

    BOLD_W = Font(bold=True, color="FFFFFF", size=10)
    NORM   = Font(size=10)
    NORM_B = Font(bold=True, size=10)
    AC = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # Anchos y alturas
    widths = [18, 12, 14, 16, 16, 14, 12, 18, 10, 16, 12, 16, 14, 16, 10, 14, 12]
    for col_idx, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = w
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 40
    ws.freeze_panes = 'B3'

    # Fila 1: bandas de sección (sin merge — primera celda lleva el texto)
    sec_fills = [F_CAMP, F_SALTO, F_SALTO, F_SALTO, F_SALTO, F_VIS,
                 F_HOT, F_HOT, F_HOT, F_HOT, F_HOT, F_HOT, F_HOT, F_TODO, F_TODO, F_ACT, F_ACT]
    sec_texts = ["Campamento", "SALTO", "", "", "", "",
                 "BBDD Hotelería", "", "", "", "", "", "", "", "", "", ""]
    ws.append([_woc(ws, t, fill=f, font=BOLD_W, align=AC)
               for t, f in zip(sec_texts, sec_fills)])

    # Fila 2: encabezados de columna
    hdr_defs = [
        ("Campamento", F_CAMP), ("Total\nUsuarios", F_SALTO),
        ("Con 1 Hab.\nAsignada", F_SALTO), ("Con Calendario\nAsignado", F_SALTO),
        ("Con Tabla\nHorario Asignada", F_SALTO), ("Sobrantes\n(Visitas)", F_VIS),
        ("Total\nUsuarios", F_HOT), ("Con Solo 1 Hab.\nAsig. en Salto", F_HOT),
        ("% Asig.\nHab.", F_HOT), ("Con Calendario\nAsignado", F_HOT),
        ("% Asig.\nCalendario", F_HOT), ("Con Tabla\nHorario Asignada", F_HOT),
        ("% Asig.\nTabla Horario", F_HOT), ("Con Hab., Cal.\ny Tabla Hor.", F_TODO),
        ("% Avance\nReal", F_TODO), ("Total Act.\nTarjetas", F_ACT),
        ("% Act.\nTarjetas", F_ACT),
    ]
    ws.append([_woc(ws, txt, fill=fill, font=BOLD_W, align=AC) for txt, fill in hdr_defs])

    # Filas de datos
    for i, fila in enumerate(filas, start=3):
        es_total = fila.get('Campamento') == 'TOTAL'
        rf = NORM_B if es_total else NORM
        vis = fila.get('SAL_Visitas', 0)
        vis_str = f"{int(vis):,}\n(visitas)".replace(',', '.') if not es_total else str(vis)
        data = [
            (fila.get('Campamento',''),          F_TOTAL if es_total else F_CAMP,   BOLD_W),
            (fila.get('SAL_Total',''),            F_TOTAL if es_total else F_DATA_S, rf),
            (fila.get('SAL_Con Hab',''),          F_TOTAL if es_total else F_DATA_S, rf),
            (fila.get('SAL_Con Calendario',''),   F_TOTAL if es_total else F_DATA_S, rf),
            (fila.get('SAL_Con Tabla Horario',''),F_TOTAL if es_total else F_DATA_S, rf),
            (vis_str,                             F_TOTAL if es_total else F_VIS,    BOLD_W),
            (fila.get('HOT_Total',''),            F_TOTAL if es_total else F_DATA_H, rf),
            (fila.get('HOT_Con Hab en Salto',''), F_TOTAL if es_total else F_DATA_H, rf),
            (f"{fila.get('HOT_pct_Hab',0)}%",    F_TOTAL if es_total else F_PCT,    rf),
            (fila.get('HOT_Con Calendario',''),   F_TOTAL if es_total else F_DATA_H, rf),
            (f"{fila.get('HOT_pct_Cal',0)}%",     F_TOTAL if es_total else F_PCT,    rf),
            (fila.get('HOT_Con Tabla Horario',''),F_TOTAL if es_total else F_DATA_H, rf),
            (f"{fila.get('HOT_pct_Hor',0)}%",    F_TOTAL if es_total else F_PCT,    rf),
            (fila.get('HOT_Con Todo',''),         F_TOTAL if es_total else F_DATA_T, rf),
            (f"{fila.get('HOT_pct_Todo',0)}%",   F_TOTAL if es_total else F_DATA_T, rf),
            (fila.get('HOT_Act Tarjetas',''),     F_TOTAL if es_total else F_DATA_A, rf),
            (f"{fila.get('HOT_pct_Act',0)}%",    F_TOTAL if es_total else F_DATA_A, rf),
        ]
        ws.row_dimensions[i].height = 26
        ws.append([_woc(ws, val, fill=fill, font=fnt, align=AC) for val, fill, fnt in data])


def _escribir_glosario_excel(ws):
    """Hoja explicativa de cada métrica del Resumen Ejecutivo — write_only compatible."""

    # ── Paleta ────────────────────────────────────────────────────
    F_TITULO  = PatternFill("solid", fgColor="1A1A2E")   # casi negro
    F_SALTO   = PatternFill("solid", fgColor="2F6496")   # azul SALTO
    F_HOT     = PatternFill("solid", fgColor="C55A11")   # naranja HOT
    F_TODO    = PatternFill("solid", fgColor="922B21")   # rojo Con Todo
    F_ACT     = PatternFill("solid", fgColor="7F7F7F")   # gris Tarjetas
    F_HEADER  = PatternFill("solid", fgColor="D9D9D9")   # gris claro encabezados
    F_EVEN    = PatternFill("solid", fgColor="F7F9FB")   # fila par
    F_ODD     = PatternFill("solid", fgColor="FFFFFF")   # fila impar
    F_NOTA    = PatternFill("solid", fgColor="FFF9C4")   # amarillo suave

    BOLD_W = Font(bold=True, color="FFFFFF", size=11)
    BOLD_B = Font(bold=True, color="1A1A1A", size=11)
    NORM   = Font(size=10,  color="1A1A1A")
    SMALL  = Font(size=9,   color="555555", italic=True)
    NOTA_F = Font(size=9,   color="5D4037", italic=True)
    AC = Alignment(horizontal='center', vertical='center', wrap_text=True)
    AL = Alignment(horizontal='left',   vertical='center', wrap_text=True)

    # ── Anchos ────────────────────────────────────────────────────
    ws.column_dimensions['A'].width = 6    # #
    ws.column_dimensions['B'].width = 28   # Métrica
    ws.column_dimensions['C'].width = 60   # Descripción
    ws.column_dimensions['D'].width = 30   # Fuente
    ws.column_dimensions['E'].width = 24   # Fórmula

    ws.freeze_panes = 'B5'

    # Helper: fila que ocupa las 5 columnas (simula merge sin API incompatible)
    def _full_row(text, fill, font, align=AL):
        return [
            _woc(ws, text, fill=fill, font=font, align=align),
            _woc(ws, '',   fill=fill, font=font, align=align),
            _woc(ws, '',   fill=fill, font=font, align=align),
            _woc(ws, '',   fill=fill, font=font, align=align),
            _woc(ws, '',   fill=fill, font=font, align=align),
        ]

    # ── Fila 1: Título ────────────────────────────────────────────
    ws.append(_full_row("GLOSARIO — Resumen Ejecutivo de Asignaciones", F_TITULO, BOLD_W, AC))

    # ── Fila 2: Subtítulo ─────────────────────────────────────────
    ws.append(_full_row(
        "Descripción de cada indicador que aparece en la hoja «Resumen Ejecutivo». "
        "Las columnas de porcentaje (%) se calculan sobre el universo de usuarios "
        "presentes en BBDD Hotelería que tienen un registro coincidente en El Salto (usuarios comunes).",
        F_EVEN, SMALL, AL
    ))

    # ── Fila 3: Espacio ───────────────────────────────────────────
    ws.append(_full_row('', F_ODD, NORM))

    # ── Fila 4: Encabezados de columna ────────────────────────────
    headers = ["#", "Métrica", "Descripción", "Fuente de datos", "Fórmula / Criterio"]
    ws.append([_woc(ws, h, fill=F_HEADER, font=BOLD_B, align=AC) for h in headers])

    # ── Métricas ──────────────────────────────────────────────────
    # Formato: (nº, nombre, descripción, fuente, fórmula, color_sección)
    metricas = [
        # ── SECCIÓN SALTO ──────────────────────────────────────────
        (None, "── SECCIÓN: SALTO (Control de Acceso) ──", "", "", "", F_SALTO),

        (1, "Total Usuarios (SALTO)",
         "Cantidad total de personas registradas en el sistema de control de acceso El Salto "
         "que pertenecen al campamento indicado, sin importar su estado.",
         "El Salto (exportacionusuarios.csv)",
         "COUNT(RUT por campamento según mapa NM SALTO → CAMPAMENTO)", None),

        (2, "Con 1 Hab. Asignada (SALTO)",
         "Usuarios de El Salto que tienen al menos una puerta/habitación asignada "
         "(campo ExtDoorIDList / NameDoorList no vacío).",
         "El Salto (exportacionusuarios.csv)",
         "COUNT donde NameDoorList ≠ vacío", None),

        (3, "Con Calendario Asignado (SALTO)",
         "Usuarios de El Salto cuyo tipo de calendario es válido. "
         "Se excluyen los valores: 'No válido', 'No válida', 'Desconocido' y vacío.",
         "El Salto (exportacionusuarios.csv)",
         "COUNT donde TipoCalendario ∉ {'No válido','No válida','Desconocido',''}", None),

        (4, "Con Tabla Horario Asignada (SALTO)",
         "Usuarios de El Salto con tabla de horario válida. "
         "Se excluyen: 'No válida', 'Desconocido' y vacío.",
         "El Salto (exportacionusuarios.csv)",
         "COUNT donde ClasifTablaHorario ∉ {'No válida','Desconocido',''}", None),

        (5, "Sobrantes (Visitas)",
         "Personas registradas en El Salto pero que NO aparecen en la BBDD Hotelería. "
         "Corresponden a visitas, contratistas temporales u otros usuarios no alojados. "
         "Se muestran entre paréntesis como '(visitas)' para distinguirlos de residentes.",
         "El Salto (exportacionusuarios.csv) — ausentes en Hotelería",
         "COUNT(RUT en SALTO) − COUNT(RUT en SALTO ∩ Hotelería)", None),

        # ── SECCIÓN HOTELERÍA ──────────────────────────────────────
        (None, "── SECCIÓN: BBDD Hotelería ──", "", "", "", F_HOT),

        (6, "Total Usuarios (Hotelería)",
         "Cantidad de personas registradas en la base de datos del sistema Hotelería "
         "para el campamento correspondiente.",
         "BBDD Hotelería (Excel)",
         "COUNT(RUT por campamento según mapa HAB → CAMPAMENTO)", None),

        (7, "Con Solo 1 Hab. Asig. en Salto",
         "De los usuarios comunes (presentes en ambos sistemas), cuántos tienen "
         "exactamente una habitación asignada en El Salto.",
         "Cruce SALTO ∩ Hotelería",
         "COUNT(comunes) donde NameDoorList ≠ vacío", None),

        (8, "% Asig. Hab.",
         "Porcentaje de usuarios de Hotelería que tienen habitación asignada en El Salto. "
         "Indica la cobertura de asignación de acceso físico.",
         "Cálculo",
         "(Con 1 Hab. Asig. en Salto / Total Usuarios Hotelería) × 100", None),

        (9, "Con Calendario Asignado (Hotelería)",
         "De los usuarios comunes, cuántos tienen un calendario válido en El Salto. "
         "El calendario define los horarios de acceso permitidos.",
         "Cruce SALTO ∩ Hotelería",
         "COUNT(comunes) donde TipoCalendario es válido", None),

        (10, "% Asig. Calendario",
         "Porcentaje de usuarios de Hotelería con calendario de acceso válido en El Salto.",
         "Cálculo",
         "(Con Calendario Asignado / Total Usuarios Hotelería) × 100", None),

        (11, "Con Tabla Horario Asignada (Hotelería)",
         "De los usuarios comunes, cuántos tienen una tabla de horario válida en El Salto. "
         "La tabla de horario define los bloques de tiempo en que se permite el acceso.",
         "Cruce SALTO ∩ Hotelería",
         "COUNT(comunes) donde ClasifTablaHorario es válida", None),

        (12, "% Asig. Tabla Horario",
         "Porcentaje de usuarios de Hotelería con tabla de horario válida en El Salto.",
         "Cálculo",
         "(Con Tabla Horario Asignada / Total Usuarios Hotelería) × 100", None),

        # ── SECCIÓN CON TODO ───────────────────────────────────────
        (None, "── SECCIÓN: Con Todo (Configuración Completa) ──", "", "", "", F_TODO),

        (13, "Con Hab., Cal. y Tabla Hor. (Con Todo)",
         "Usuarios comunes que cumplen simultáneamente las tres condiciones: "
         "tienen habitación asignada, calendario válido Y tabla de horario válida. "
         "Este es el indicador de configuración completa y correcta en El Salto.",
         "Cruce SALTO ∩ Hotelería",
         "COUNT(comunes) donde Hab. ≠ vacío AND Cal. válido AND Tabla Hor. válida", None),

        (14, "% Avance Real",
         "Porcentaje de usuarios de Hotelería con configuración completa (Con Todo). "
         "Es el indicador clave de avance en la configuración del sistema de acceso.",
         "Cálculo",
         "(Con Todo / Total Usuarios Hotelería) × 100", None),

        # ── SECCIÓN TARJETAS ───────────────────────────────────────
        (None, "── SECCIÓN: Actualización de Tarjetas ──", "", "", "", F_ACT),

        (15, "Total Act. Tarjetas",
         "Cantidad de usuarios en El Salto cuya tarjeta requiere ser actualizada. "
         "Incluye los estados: 'Actualización requerida', 'Reedición requerida' y 'Llave expirada'.",
         "El Salto (exportacionusuarios.csv) — campo EstadoLlave",
         "COUNT donde EstadoLlave ∈ {'Actualización requerida','Reedición requerida','Llave expirada'}", None),

        (16, "% Act. Tarjetas",
         "Porcentaje de usuarios del campamento en El Salto cuya tarjeta necesita actualización. "
         "Un valor alto indica que hay muchas tarjetas pendientes de configurar en los lectores.",
         "Cálculo",
         "(Total Act. Tarjetas / Total Usuarios SALTO por campamento) × 100", None),
    ]

    for i, entry in enumerate(metricas):
        num, nombre, desc, fuente, formula, color_sec = entry
        is_header = num is None
        bg = color_sec if is_header else (F_EVEN if i % 2 == 0 else F_ODD)

        if is_header:
            ws.append(_full_row(nombre, color_sec, BOLD_W, AL))
        else:
            ws.append([
                _woc(ws, num,     fill=bg, font=NORM,   align=AL),
                _woc(ws, nombre,  fill=bg, font=BOLD_B, align=AL),
                _woc(ws, desc,    fill=bg, font=NORM,   align=AL),
                _woc(ws, fuente,  fill=bg, font=NORM,   align=AL),
                _woc(ws, formula, fill=bg, font=NORM,   align=AL),
            ])

    # ── Espacio + Nota al pie ─────────────────────────────────────
    ws.append(_full_row('', F_ODD, NORM))
    ws.append(_full_row(
        "NOTA: Los usuarios 'comunes' son aquellos cuyo RUT aparece en AMBOS sistemas (El Salto y Hotelería). "
        "Los porcentajes de las columnas HOT se calculan sobre el total de usuarios de Hotelería del campamento, "
        "no sobre los comunes, para reflejar la cobertura real del sistema.",
        F_NOTA, NOTA_F, AL
    ))


# ─────────────────────────────────────────────
#  Plantillas vacías descargables
# ─────────────────────────────────────────────

PLANTILLAS = {
    'mapa': {
        'nombre':  'plantilla_mapa_habitaciones.xlsx',
        'columnas':['HABITACIÓN', 'CAMPAMENTO', 'MÓDULO', 'PISO', 'NM SALTO'],
        'ejemplo': [
            ['HAB-101', 'CAMPAMENTO A', 'MÓDULO 1', '1', 'SALTO-101'],
            ['HAB-102', 'CAMPAMENTO A', 'MÓDULO 1', '1', 'SALTO-102'],
        ],
    },
    'hotel': {
        'nombre':  'plantilla_base_hoteleria.xlsx',
        'columnas':['HABITACIÓN','MÓDULO','RUT','NOMBRE','EMPRESA',
                    'N°CONTRATO','GERENCIA','SISTEMA TURNO'],
        'ejemplo': [
            ['HAB-101','MÓDULO 1','12345678-9','Juan Pérez',
             'Empresa A','CONT-001','GERENCIA 1','A'],
            ['HAB-205','MÓDULO 2','98765432-1','María González',
             'Empresa B','CONT-002','GERENCIA 2','B'],
        ],
    },
}


def generar_plantilla(tipo):
    info = PLANTILLAS[tipo]
    wb   = Workbook()
    ws   = wb.active
    ws.title = "Datos"
    HDR_FILL = PatternFill("solid", fgColor="1F3864")
    EJ_FILL  = PatternFill("solid", fgColor="DCE6F1")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
    EJ_FONT  = Font(italic=True, color="555555", size=10)

    for col, nombre in enumerate(info['columnas'], 1):
        c = ws.cell(1, col, nombre)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 22

    for i, fila in enumerate(info['ejemplo'], 2):
        for col, val in enumerate(fila, 1):
            c = ws.cell(i, col, val)
            c.fill = EJ_FILL; c.font = EJ_FONT
            c.alignment = Alignment(horizontal='left', vertical='center')

    for col_idx, nombre in enumerate(info['columnas'], 1):
        ancho = max(len(nombre), max(
            len(str(f[col_idx-1])) for f in info['ejemplo'])) + 4
        ws.column_dimensions[get_column_letter(col_idx)].width = min(ancho, 40)
    ws.freeze_panes = 'A2'

    wi = wb.create_sheet("INSTRUCCIONES")
    wi['A1'] = "No cambies los nombres de las columnas. Las filas de ejemplo (azul) pueden borrarse."
    wi['A1'].font = Font(bold=True, color="C00000", size=10)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
#  Rutas Flask
# ─────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    df_mapa, mapa_fecha = cargar_mapa_db()
    mapa_cargado = df_mapa is not None
    return render_template('index.html',
                           mapa_cargado=mapa_cargado,
                           mapa_fecha=mapa_fecha)


@app.route('/guardar-mapa', methods=['POST'])
def guardar_mapa_ruta():
    if 'mapa' not in request.files or not request.files['mapa'].filename:
        return redirect(url_for('index'))
    try:
        df = leer_excel(request.files['mapa'].read())
        guardar_mapa_db(df)
        return render_template('index.html',
                               mapa_cargado=True,
                               mapa_fecha='justo ahora',
                               ok_mapa='Mapa de habitaciones guardado correctamente.')
    except Exception as e:
        df_mapa, mapa_fecha = cargar_mapa_db()
        return render_template('index.html',
                               mapa_cargado=df_mapa is not None,
                               mapa_fecha=mapa_fecha,
                               error=f'Error al guardar el mapa: {e}')


@app.route('/borrar-mapa', methods=['POST'])
def borrar_mapa_ruta():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM configuracion WHERE clave = 'mapa';")
            conn.commit()
    except Exception:
        pass
    return redirect(url_for('index'))


@app.route('/procesar', methods=['POST'])
def procesar_ruta():
    for campo in ['salto', 'hotel']:
        if campo not in request.files or not request.files[campo].filename:
            return render_template('index.html',
                                   error='Debes subir los archivos de El Salto y Hotelería.',
                                   **_mapa_ctx())
    try:
        salto_b = request.files['salto'].read()
        hotel_b = request.files['hotel'].read()

        if 'mapa' in request.files and request.files['mapa'].filename:
            mapa_src = request.files['mapa'].read()
            guardar_mapa_db(leer_excel(mapa_src))
        else:
            df_mapa, _ = cargar_mapa_db()
            if df_mapa is None:
                return render_template('index.html',
                                       error='No hay un Mapa de habitaciones guardado. '
                                             'Súbelo en la sección superior o adjúntalo aquí.',
                                       **_mapa_ctx())
            mapa_src = df_mapa

        results = procesar(mapa_src, salto_b, hotel_b)
        token   = str(uuid.uuid4())
        # Guarda solo los resultados (JSON comprimido) — Excel se genera al descargar
        guardar_resultados_db(token, results)

        return render_template('results.html', results=results, token=token)

    except Exception as e:
        return render_template('index.html',
                               error=f'Error al procesar los archivos: {e}\n\n{traceback.format_exc()}',
                               **_mapa_ctx())


def _mapa_ctx():
    df_mapa, mapa_fecha = cargar_mapa_db()
    return {'mapa_cargado': df_mapa is not None, 'mapa_fecha': mapa_fecha}


@app.route('/descargar/<token>')
def descargar(token):
    results = cargar_resultados_db(token)
    if not results:
        return render_template('index.html',
                               error='El reporte expiró (7 días). Procesa los archivos nuevamente.',
                               **_mapa_ctx())
    # Excel se genera aquí, en un request separado — sin presión de timeout en el proceso
    excel_b = generar_excel(results)
    return send_file(
        io.BytesIO(excel_b),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='reporte_diferencias.xlsx'
    )


@app.route('/plantilla/<tipo>')
def descargar_plantilla(tipo):
    if tipo not in PLANTILLAS:
        return "Plantilla no encontrada.", 404
    return send_file(
        generar_plantilla(tipo),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=PLANTILLAS[tipo]['nombre']
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
