"""
Comparador de Habitaciones - El Salto vs Hotelería
Flask app para detectar discrepancias entre sistemas de control de acceso y hotelería.
"""

import os
import io
import uuid
import pandas as pd
from flask import Flask, render_template, request, send_file
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

# Almacén en memoria (funciona para despliegue de un solo worker en Render)
_store = {}


# ─────────────────────────────────────────────
#  Utilidades
# ─────────────────────────────────────────────

def limpiar(val):
    """Convierte a string y elimina espacios."""
    if pd.isna(val):
        return ''
    return str(val).strip()


def norm_rut(val):
    """Normaliza RUT: elimina puntos, espacios; uppercase."""
    if pd.isna(val):
        return ''
    return str(val).strip().upper().replace('.', '').replace(' ', '')


def quitar_tildes(texto):
    """Elimina tildes y caracteres especiales para comparación flexible."""
    reemplazos = {
        'Á':'A','É':'E','Í':'I','Ó':'O','Ú':'U','Ü':'U','Ñ':'N',
        'á':'a','é':'e','í':'i','ó':'o','ú':'u','ü':'u','ñ':'n',
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto


def normalizar_col(texto):
    """Normaliza un nombre de columna para comparación: sin tildes, upper, sin espacios extra."""
    return quitar_tildes(str(texto).strip().upper().replace('\n', ' ').replace('  ', ' '))


def buscar_col(df, nombres):
    """Busca una columna de forma flexible: sin tildes, case-insensitive."""
    mapa = {normalizar_col(c): c for c in df.columns}
    for nombre in nombres:
        clave = normalizar_col(nombre)
        if clave in mapa:
            return mapa[clave]
    return None


# ─────────────────────────────────────────────
#  Procesamiento principal
# ─────────────────────────────────────────────

def leer_excel(data_bytes):
    """
    Lee .xls o .xlsx automáticamente.
    Busca la fila correcta de encabezados probando las primeras 5 filas:
    la fila de encabezados es la primera que tiene más de 2 celdas con texto corto.
    """
    magic  = data_bytes[:4]
    engine = 'openpyxl' if magic[:2] == b'PK' else 'xlrd'

    # Leer sin encabezado para inspeccionar
    df_raw = pd.read_excel(io.BytesIO(data_bytes), dtype=str,
                           engine=engine, header=None)
    df_raw = df_raw.fillna('')

    # Encontrar la fila de encabezados: primera fila donde la mayoría de celdas
    # son textos cortos (≤ 40 chars) y no vacíos
    header_row = 0
    for i in range(min(5, len(df_raw))):
        fila = df_raw.iloc[i]
        celdas_validas = [c for c in fila if str(c).strip() and len(str(c).strip()) <= 40]
        if len(celdas_validas) >= 3:
            header_row = i
            break

    df = pd.read_excel(io.BytesIO(data_bytes), dtype=str,
                       engine=engine, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna('')
    # Eliminar filas completamente vacías
    df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
    return df


def procesar(mapa_bytes, salto_bytes, hotel_bytes):
    """Lee los tres archivos Excel y devuelve un dict con todos los resultados."""

    df_map  = leer_excel(mapa_bytes)
    df_sal  = leer_excel(salto_bytes)
    df_hot  = leer_excel(hotel_bytes)

    # Limpiar nombres de columnas
    for df in [df_map, df_sal, df_hot]:
        df.columns = [str(c).strip() for c in df.columns]
        df.fillna('', inplace=True)

    # ── Columnas Mapa de habitaciones ──────────────────────────────
    map_hab  = buscar_col(df_map, ['HABITACIÓN', 'HABITACION', 'HAB'])
    map_nm   = buscar_col(df_map, ['NM SALTO', 'NM_SALTO', 'NMSALTO', 'NM SALTO '])
    map_camp = buscar_col(df_map, ['CAMPAMENTO'])
    map_mod  = buscar_col(df_map, ['MÓDULO', 'MODULO'])
    map_piso = buscar_col(df_map, ['PISO'])

    # ── Columnas El Salto ──────────────────────────────────────────
    sal_ext  = buscar_col(df_sal, ['ExtID', 'EXTID', 'ext_id', 'EXT ID'])
    sal_door = buscar_col(df_sal, ['NameDoorList', 'NAMEDOORLIST', 'name_door_list', 'NAME DOOR LIST'])
    sal_name = buscar_col(df_sal, ['FullName', 'FULLNAME', 'full_name', 'FULL NAME'])
    sal_door_qty = buscar_col(df_sal, ['DoorQty', 'DOORQTY', 'door_qty'])
    sal_zone_qty = buscar_col(df_sal, ['ZoneQty', 'ZONEQTY', 'zone_qty'])

    # ── Columnas Hotelería ─────────────────────────────────────────
    hot_hab   = buscar_col(df_hot, ['HABITACIÓN', 'HABITACION', 'HAB'])
    hot_rut   = buscar_col(df_hot, ['RUT'])
    hot_nom   = buscar_col(df_hot, ['NOMBRE'])
    hot_emp   = buscar_col(df_hot, ['EMPRESA'])
    hot_mod   = buscar_col(df_hot, ['MÓDULO', 'MODULO'])
    hot_cont  = buscar_col(df_hot, ['N°CONTRATO', 'N CONTRATO', 'NCONTRATO', 'N°CONTRATO'])
    hot_ger   = buscar_col(df_hot, ['GERENCIA'])
    hot_turno = buscar_col(df_hot, ['SISTEMA\nTURNO', 'SISTEMA TURNO', 'SISTEMATURNO', 'TURNO', 'SISTEMA_TURNO'])

    # Validar columnas obligatorias
    faltantes = []
    if not map_hab:  faltantes.append("HABITACIÓN  →  Mapa de habitaciones")
    if not map_nm:   faltantes.append("NM SALTO    →  Mapa de habitaciones")
    if not sal_door: faltantes.append("NameDoorList →  Base de datos El Salto")
    if not hot_hab:  faltantes.append("HABITACIÓN  →  Base de datos Hotelería")
    if not hot_rut:  faltantes.append("RUT         →  Base de datos Hotelería")
    if faltantes:
        raise ValueError("Columnas no encontradas:\n" + "\n".join(faltantes))

    # ── Construir mapeo bidireccional de habitaciones ──────────────
    h2n = {}   # HABITACIÓN.upper() → NM SALTO.upper()
    n2h = {}   # NM SALTO.upper()   → HABITACIÓN (original)

    for _, fila in df_map.iterrows():
        h = limpiar(fila.get(map_hab, '')).upper()
        n = limpiar(fila.get(map_nm,  '')).upper()
        if h and n:
            h2n[h] = n
            n2h[n] = limpiar(fila.get(map_hab, ''))

    # ── Normalizar identificadores y habitaciones ──────────────────
    df_hot['_RUT']     = df_hot[hot_rut].apply(norm_rut)
    df_sal['_RUT']     = df_sal[sal_ext].apply(norm_rut) if sal_ext else ''
    df_hot['_HAB']     = df_hot[hot_hab].apply(lambda x: limpiar(x).upper())
    df_sal['_DOOR']    = df_sal[sal_door].apply(lambda x: limpiar(x).upper())
    df_hot['_NM_EQ']   = df_hot['_HAB'].map(h2n)      # equivalente en El Salto
    df_sal['_HAB_EQ']  = df_sal['_DOOR'].map(n2h)     # equivalente en Hotelería

    # ── Índices por RUT ────────────────────────────────────────────
    # Si hay duplicados de RUT, se conserva el primero
    hot_idx = {}
    for _, fila in df_hot.iterrows():
        rut = fila['_RUT']
        if rut and rut not in hot_idx:
            hot_idx[rut] = fila

    sal_idx = {}
    for _, fila in df_sal.iterrows():
        rut = fila['_RUT']
        if rut and rut not in sal_idx:
            sal_idx[rut] = fila

    comunes    = sorted(set(hot_idx) & set(sal_idx))
    solo_hot_k = sorted(set(hot_idx) - set(sal_idx))
    solo_sal_k = sorted(set(sal_idx) - set(hot_idx))

    # ── Comparar personas en ambos sistemas ───────────────────────
    discrepancias = []
    coincidencias = []

    for rut in comunes:
        h = hot_idx[rut]
        s = sal_idx[rut]

        nm_eq   = limpiar(h.get('_NM_EQ',  ''))
        door    = limpiar(s['_DOOR'])
        hab_eq  = limpiar(s.get('_HAB_EQ', ''))

        # Coincide si el equivalente de hotelería == la puerta en El Salto
        coincide = bool(nm_eq) and nm_eq.upper() == door.upper()

        rec = {
            'RUT':                  rut,
            'Nombre Hotelería':     limpiar(h.get(hot_nom, '')) if hot_nom else '',
            'Nombre El Salto':      limpiar(s.get(sal_name, '')) if sal_name else '',
            'HAB Hotelería':        limpiar(h.get(hot_hab, '')),
            'HAB El Salto':         limpiar(s.get(sal_door, '')),
            'Equiv Hotel→Salto':    nm_eq,
            'Equiv Salto→Hotel':    hab_eq,
            'Empresa':              limpiar(h.get(hot_emp,  '')) if hot_emp  else '',
            'Módulo':               limpiar(h.get(hot_mod,  '')) if hot_mod  else '',
            'Gerencia':             limpiar(h.get(hot_ger,  '')) if hot_ger  else '',
        }

        if coincide:
            coincidencias.append(rec)
        else:
            discrepancias.append(rec)

    # ── Solo en Hotelería ──────────────────────────────────────────
    solo_hotel = []
    for rut in solo_hot_k:
        h = hot_idx[rut]
        solo_hotel.append({
            'RUT':         rut,
            'Nombre':      limpiar(h.get(hot_nom,  '')) if hot_nom  else '',
            'HABITACIÓN':  limpiar(h.get(hot_hab,  '')),
            'Empresa':     limpiar(h.get(hot_emp,  '')) if hot_emp  else '',
            'Módulo':      limpiar(h.get(hot_mod,  '')) if hot_mod  else '',
            'N°Contrato':  limpiar(h.get(hot_cont, '')) if hot_cont else '',
            'Gerencia':    limpiar(h.get(hot_ger,  '')) if hot_ger  else '',
            'Turno':       limpiar(h.get(hot_turno,'')) if hot_turno else '',
        })

    # ── Solo en El Salto ───────────────────────────────────────────
    solo_salto = []
    for rut in solo_sal_k:
        s = sal_idx[rut]
        solo_salto.append({
            'RUT/ExtID':        rut,
            'Nombre':           limpiar(s.get(sal_name, '')) if sal_name else '',
            'HAB El Salto':     limpiar(s.get(sal_door, '')),
            'HAB Equivalente':  limpiar(s.get('_HAB_EQ', '')),
        })

    # ── Habitaciones sin mapeo ─────────────────────────────────────
    hab_sin_mapa = sorted({
        limpiar(r.get(hot_hab, ''))
        for _, r in df_hot.iterrows()
        if not r.get('_NM_EQ') and limpiar(r.get(hot_hab, ''))
    })

    door_sin_mapa = sorted({
        limpiar(r.get(sal_door, ''))
        for _, r in df_sal.iterrows()
        if not r.get('_HAB_EQ') and limpiar(r.get(sal_door, ''))
    })

    return {
        'discrepancias':  discrepancias,
        'coincidencias':  coincidencias,
        'solo_hotel':     solo_hotel,
        'solo_salto':     solo_salto,
        'hab_sin_mapa':   hab_sin_mapa,
        'door_sin_mapa':  door_sin_mapa,
        'stats': {
            'total_hotel':      len(df_hot),
            'total_salto':      len(df_sal),
            'total_mapa':       len(df_map),
            'coincidencias':    len(coincidencias),
            'discrepancias':    len(discrepancias),
            'solo_hotel':       len(solo_hotel),
            'solo_salto':       len(solo_salto),
            'hab_sin_mapa':     len(hab_sin_mapa),
            'door_sin_mapa':    len(door_sin_mapa),
        },
    }


# ─────────────────────────────────────────────
#  Generación de Excel
# ─────────────────────────────────────────────

ROJO    = PatternFill("solid", fgColor="FFB3B3")
VERDE   = PatternFill("solid", fgColor="B3FFB3")
NARANJA = PatternFill("solid", fgColor="FFE5B3")
AZUL    = PatternFill("solid", fgColor="B3D9FF")
GRIS    = PatternFill("solid", fgColor="E0E0E0")
HEADER  = PatternFill("solid", fgColor="1F3864")
FHEADER = Font(bold=True, color="FFFFFF", size=11)
FCELL   = Font(size=10)
ALIGN_C = Alignment(horizontal='center', vertical='center', wrap_text=True)
ALIGN_L = Alignment(horizontal='left',   vertical='center', wrap_text=True)


def _ajustar_cols(ws):
    for col in ws.columns:
        ancho = max((len(str(c.value or '')) for c in col), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(ancho + 4, 45)
    ws.row_dimensions[1].height = 30


def _escribir_hoja(ws, datos, fill_fila=None):
    if not datos:
        ws.append(["Sin registros"])
        ws['A1'].fill = GRIS
        return

    headers = list(datos[0].keys())
    ws.append(headers)
    for celda in ws[1]:
        celda.fill = HEADER
        celda.font = FHEADER
        celda.alignment = ALIGN_C

    for fila in datos:
        ws.append([fila.get(h, '') for h in headers])
        if fill_fila:
            for c in ws[ws.max_row]:
                c.fill = fill_fila
                c.font = FCELL
                c.alignment = ALIGN_L

    _ajustar_cols(ws)


def generar_excel(results):
    wb = Workbook()

    # Hoja 1 – Discrepancias
    ws1 = wb.active
    ws1.title = "Discrepancias RUT"
    _escribir_hoja(ws1, results['discrepancias'], ROJO)

    # Hoja 2 – Solo en Hotelería
    ws2 = wb.create_sheet("Solo en Hotelería")
    _escribir_hoja(ws2, results['solo_hotel'], NARANJA)

    # Hoja 3 – Solo en El Salto
    ws3 = wb.create_sheet("Solo en El Salto")
    _escribir_hoja(ws3, results['solo_salto'], AZUL)

    # Hoja 4 – Coincidencias
    ws4 = wb.create_sheet("Coincidencias")
    _escribir_hoja(ws4, results['coincidencias'], VERDE)

    # Hoja 5 – HAB sin mapeo en Hotelería
    ws5 = wb.create_sheet("Sin mapa (Hotelería)")
    ws5.append(["HABITACIÓN sin equivalente en El Salto"])
    ws5['A1'].fill = HEADER
    ws5['A1'].font = FHEADER
    for h in results['hab_sin_mapa']:
        ws5.append([h])
    _ajustar_cols(ws5)

    # Hoja 6 – HAB sin mapeo en El Salto
    ws6 = wb.create_sheet("Sin mapa (El Salto)")
    ws6.append(["HAB El Salto sin equivalente en Hotelería"])
    ws6['A1'].fill = HEADER
    ws6['A1'].font = FHEADER
    for d in results['door_sin_mapa']:
        ws6.append([d])
    _ajustar_cols(ws6)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
#  Rutas Flask
# ─────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/procesar', methods=['POST'])
def procesar_ruta():
    archivos = ['mapa', 'salto', 'hotel']
    faltantes = [a for a in archivos if a not in request.files or not request.files[a].filename]
    if faltantes:
        return render_template('index.html', error='Debes subir los 3 archivos Excel.')

    try:
        mapa_b  = request.files['mapa'].read()
        salto_b = request.files['salto'].read()
        hotel_b = request.files['hotel'].read()

        results = procesar(mapa_b, salto_b, hotel_b)

        token = str(uuid.uuid4())
        _store[token] = results

        # Limpieza si hay demasiados tokens
        if len(_store) > 200:
            primer_key = next(iter(_store))
            del _store[primer_key]

        return render_template('results.html', results=results, token=token)

    except Exception as e:
        return render_template('index.html', error=f'Error al procesar los archivos: {e}')


@app.route('/descargar/<token>')
def descargar(token):
    if token not in _store:
        return "Sesión expirada. Sube los archivos nuevamente.", 404
    buf = generar_excel(_store[token])
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='reporte_diferencias.xlsx'
    )


# ─────────────────────────────────────────────
#  Descarga de plantillas vacías
# ─────────────────────────────────────────────

PLANTILLAS = {
    'mapa': {
        'nombre': 'plantilla_mapa_habitaciones.xlsx',
        'columnas': ['HABITACIÓN', 'CAMPAMENTO', 'MÓDULO', 'PISO', 'NM SALTO'],
        'ejemplo': [
            ['HAB-101', 'CAMPAMENTO A', 'MÓDULO 1', '1', 'SALTO-101'],
            ['HAB-102', 'CAMPAMENTO A', 'MÓDULO 1', '1', 'SALTO-102'],
        ],
        'descripcion': 'Mapa de equivalencias entre nombres de habitación en Hotelería (columna HABITACIÓN) y en El Salto (columna NM SALTO).'
    },
    'salto': {
        'nombre': 'plantilla_base_el_salto.xlsx',
        'columnas': ['FullName', 'ExtID', 'DoorQty', 'ZoneQty', 'NameDoorList'],
        'ejemplo': [
            ['Juan Pérez', '12345678-9', '1', '1', 'SALTO-101'],
            ['María González', '98765432-1', '1', '1', 'SALTO-205'],
        ],
        'descripcion': 'Base de datos del sistema El Salto. ExtID debe contener el RUT de la persona. NameDoorList es el nombre de la habitación según El Salto.'
    },
    'hotel': {
        'nombre': 'plantilla_base_hoteleria.xlsx',
        'columnas': ['HABITACIÓN', 'MÓDULO', 'RUT', 'NOMBRE', 'EMPRESA', 'N°CONTRATO', 'GERENCIA', 'SISTEMA TURNO'],
        'ejemplo': [
            ['HAB-101', 'MÓDULO 1', '12345678-9', 'Juan Pérez', 'Empresa A', 'CONT-001', 'GERENCIA 1', 'A'],
            ['HAB-205', 'MÓDULO 2', '98765432-1', 'María González', 'Empresa B', 'CONT-002', 'GERENCIA 2', 'B'],
        ],
        'descripcion': 'Base de datos de Hotelería con las asignaciones actuales de habitaciones.'
    },
}


def generar_plantilla(tipo):
    info = PLANTILLAS[tipo]
    wb = Workbook()

    # ── Hoja 1: DATOS (encabezados en fila 1, ejemplos en fila 2+) ──
    ws = wb.active
    ws.title = "Datos"

    AZUL_OSCURO  = PatternFill("solid", fgColor="1F3864")
    AZUL_EJEMPLO = PatternFill("solid", fgColor="DCE6F1")
    FONT_HDR = Font(bold=True, color="FFFFFF", size=11)
    FONT_EJ  = Font(italic=True, color="555555", size=10)

    # Encabezados en fila 1
    for col, nombre in enumerate(info['columnas'], 1):
        c = ws.cell(1, col, nombre)
        c.fill = AZUL_OSCURO
        c.font = FONT_HDR
        c.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 22

    # Filas de ejemplo en fila 2+
    for i, fila in enumerate(info['ejemplo'], 2):
        for col, val in enumerate(fila, 1):
            c = ws.cell(i, col, val)
            c.fill = AZUL_EJEMPLO
            c.font = FONT_EJ
            c.alignment = Alignment(horizontal='left', vertical='center')

    # Ajustar anchos
    for col_idx, nombre in enumerate(info['columnas'], 1):
        max_ancho = max(len(nombre), max(
            len(str(fila[col_idx - 1])) for fila in info['ejemplo']
        )) + 4
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_ancho, 40)

    ws.freeze_panes = 'A2'

    # ── Hoja 2: INSTRUCCIONES ────────────────────────────────────────
    wi = wb.create_sheet("INSTRUCCIONES")
    wi.column_dimensions['A'].width = 20
    wi.column_dimensions['B'].width = 60

    HDR_FILL = PatternFill("solid", fgColor="1F3864")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=11)

    wi.cell(1, 1, "Columna").fill = HDR_FILL
    wi.cell(1, 1).font = HDR_FONT
    wi.cell(1, 2, "Descripción").fill = HDR_FILL
    wi.cell(1, 2).font = HDR_FONT

    descripciones = {
        # Mapa
        'HABITACIÓN':   'Nombre de la habitación tal como aparece en el sistema de Hotelería.',
        'CAMPAMENTO':   'Nombre del campamento al que pertenece la habitación.',
        'MÓDULO':       'Módulo o sector dentro del campamento.',
        'PISO':         'Número de piso.',
        'NM SALTO':     'Nombre de la habitación tal como aparece en el sistema El Salto (NameDoorList).',
        # El Salto
        'FullName':     'Nombre completo de la persona en El Salto.',
        'ExtID':        'RUT de la persona (se usa para cruzar con Hotelería).',
        'DoorQty':      'Cantidad de puertas asignadas.',
        'ZoneQty':      'Cantidad de zonas asignadas.',
        'NameDoorList': 'Nombre de la habitación/puerta en El Salto.',
        # Hotelería
        'RUT':          'RUT de la persona (se usa para cruzar con El Salto).',
        'NOMBRE':       'Nombre completo de la persona.',
        'EMPRESA':      'Empresa a la que pertenece.',
        'N°CONTRATO':   'Número de contrato.',
        'GERENCIA':     'Gerencia o área.',
        'SISTEMA TURNO':'Sistema o turno de trabajo.',
    }

    for i, col in enumerate(info['columnas'], 2):
        wi.cell(i, 1, col).font = Font(bold=True, size=10)
        wi.cell(i, 1).alignment = Alignment(vertical='center')
        desc = descripciones.get(col, '')
        wi.cell(i, 2, desc).alignment = Alignment(wrap_text=True, vertical='center')
        wi.row_dimensions[i].height = 28

    wi.cell(len(info['columnas']) + 3, 1,
            "IMPORTANTE: No cambies los nombres de las columnas. "
            "Los ejemplos en la hoja Datos (fondo azul) pueden borrarse."
            ).font = Font(bold=True, color="C00000", size=10)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@app.route('/plantilla/<tipo>')
def descargar_plantilla(tipo):
    if tipo not in PLANTILLAS:
        return "Plantilla no encontrada.", 404
    buf = generar_plantilla(tipo)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=PLANTILLAS[tipo]['nombre']
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
