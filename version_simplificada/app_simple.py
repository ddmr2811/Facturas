"""
Aplicación simplificada para procesamiento de facturas - Versión sin dependencias externas
Esta aplicación simula el procesamiento de facturas con datos codificados directamente,
sin depender de librerías externas para procesamiento de PDFs.
"""
from flask import Flask, render_template, jsonify, send_file, request, url_for
import os
import json
import re
import random
import base64
from datetime import datetime, timedelta
import io
import shutil
import logging

# Logger mínimo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# fuzzy matching (opcional)
try:
    from fuzzywuzzy import fuzz
except Exception:
    fuzz = None


def detectar_tipo_gasto(texto):
    t = (texto or '').lower()
    if any(x in t for x in ['aqualia', 'agua']):
        return 'Agua'
    if any(x in t for x in ['electric', 'eléctr', 'eléctrico', 'energ', 'luz']):
        return 'Luz'
    if any(x in t for x in ['limpi', 'manten']):
        return 'Limpieza'
    return 'Otros'


def detectar_cups_o_contador(texto):
    if not texto:
        return 'No encontrado'
    # Buscar CUPS ESXXXXXXXX...
    m = re.search(r'(ES[0-9A-Z]{16,20})', texto, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Buscar contadores conocidos en secret mappings
    for k in MAPEO_CUENTAS_CONTABLES.keys():
        if k.upper() in texto.upper():
            return k
    # Buscador simple de códigos tipo 08TA167664
    m2 = re.search(r'([0-9A-Z]{6,12})', texto)
    if m2:
        token = m2.group(1).upper()
        if token in MAPEO_CUENTAS_CONTABLES:
            return token
    return 'No encontrado'


def detectar_direccion(texto):
    if not texto:
        return 'No encontrada'
    tex = texto.upper()
    # Buscar direcciones de secret mappings
    for v in MAPEO_CUENTAS_CONTABLES.values():
        dirref = v.get('direccion_referencia', '')
        if dirref and dirref.upper() in tex:
            return dirref
    # Búsqueda básica por patrones conocidos
    m = re.search(r'RECONQUISTA\s*\d+\s*[A-Z]?', tex)
    if m:
        return m.group(0)
    m2 = re.search(r'C[/\\]?\s*OSLO\s*\d+\s*[A-Z]?', tex)
    if m2:
        return m2.group(0)
    # última opción: buscar 'CL ' o 'CALLE'
    m3 = re.search(r'(CL\s+[A-Z0-9\s]+\d+)', tex)
    if m3:
        return m3.group(1)
    return 'No encontrada'


def detectar_importe_total(texto):
    if not texto:
        return None

    def parse_numero(s):
        s = s.strip()
        # si tiene punto y coma europeos: punto = miles, coma = decimales
        if ',' in s and '.' in s:
            # 1.234,56 -> remove dots, replace comma
            s2 = s.replace('.', '').replace(',', '.')
        elif ',' in s and not '.' in s:
            # 50,76 -> european decimal
            s2 = s.replace(',', '.')
        else:
            # 50.76 -> already dot decimal
            s2 = s
        try:
            return float(s2)
        except Exception:
            return None

    texto_u = texto.upper()
    # Priorizar patrones explícitos
    patrones_prioritarios = [
        r'TOTAL\s*A\s*FACTURAR[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€',
        r'TOTAL\s*A\s*PAGAR[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€',
        r'TOTAL\s*FACTURA[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€',
        r'TOTAL[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€'
    ]

    for patron in patrones_prioritarios:
        m = re.search(patron, texto_u, re.IGNORECASE)
        if m:
            s = m.group(1)
            val = parse_numero(s)
            if val is not None:
                logger.info(f"✅ Importe detectado por patrón prioritario: {val} € (raw: {s})")
                return val

    # Si no apareció en patrones, buscar cualquier cifra con € cerca
    matches = re.findall(r'([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€', texto)
    candidatos = []
    for s in matches:
        val = parse_numero(s)
        if val is not None and 0.5 <= val < 100000:
            candidatos.append(val)

    if candidatos:
        # Elegimos el valor más alto por heurística (total suele ser el mayor)
        val = max(candidatos)
        logger.info(f"✅ Importe detectado entre candidatos: {val} € (candidatos: {candidatos})")
        return val

    # Último recurso: buscar cualquier número con decimales
    matches2 = re.findall(r'(\d+[\.,]\d{2})', texto)
    vals = [parse_numero(s) for s in matches2 if parse_numero(s) is not None]
    if vals:
        val = max(vals)
        logger.info(f"✅ Importe detectado por fallback: {val} € (vals: {vals})")
        return val

    logger.warning('❌ No se detectó importe total válido')
    return None


def asignar_cuenta_contable_con_tipos(cups_o_contador, direccion, tipo_gasto):
    # Prioridad 1: por cups/contador
    if cups_o_contador and cups_o_contador != 'No encontrado' and cups_o_contador in MAPEO_CUENTAS_CONTABLES:
        entry = MAPEO_CUENTAS_CONTABLES[cups_o_contador]
        return entry.get('comunidad', 'No definida'), entry.get('cuenta', '0000000')
    # Prioridad 2: por tipo+direccion
    if direccion and direccion != 'No encontrada':
        key = (tipo_gasto, direccion.upper())
        for (t, d), datos in DIRECCIONES_POR_TIPO.items():
            if t == tipo_gasto and d.upper() == direccion.upper():
                return datos.get('comunidad'), datos.get('cuenta')
        # fuzzy fallback
        if fuzz:
            for (t, d), datos in DIRECCIONES_POR_TIPO.items():
                if t == tipo_gasto:
                    score = fuzz.ratio(direccion.upper(), d.upper())
                    if score > 85:
                        return datos.get('comunidad'), datos.get('cuenta')
    # Por defecto según tipo
    if tipo_gasto == 'Agua':
        return 'LOS JARDINES DE OLIAS', '6280000'
    return 'EDIFICIO ALCAZAR', '6281666'


def detectar_periodo_facturacion(texto):
    """Detecta un período en texto y devuelve una cadena legible o None."""
    if not texto:
        return None
    # Buscar pares de fechas en formato dd/mm/yyyy o dd-mm-yyyy o dd.mm.yyyy
    m = re.search(r'(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}).{0,30}?(?:al|a|to).{0,30}?(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})', texto, re.IGNORECASE)
    if m:
        d1 = m.group(1).replace('.', '/').replace('-', '/')
        d2 = m.group(2).replace('.', '/').replace('-', '/')
        return f"Periodo de medida: Del {d1} al {d2}"
    # Buscar formatos simples 'Del DD/MM/YYYY al DD/MM/YYYY'
    m2 = re.search(r'Del\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\s*(?:al|a)\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})', texto, re.IGNORECASE)
    if m2:
        d1 = m2.group(1).replace('.', '/').replace('-', '/')
        d2 = m2.group(2).replace('.', '/').replace('-', '/')
        return f"Periodo de medida: Del {d1} al {d2}"
    return None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_temporal_para_desarrollo'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB límite de subida de archivos
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Asegurarse de que el directorio de uploads exista
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Intentar detectar soporte para generar previews server-side (pdf2image + poppler)
PDF_SUPPORT = False
try:
    # pdf2image y Pillow
    from pdf2image import convert_from_path
    from PIL import Image
    # Comprobar que pdftoppm está en PATH
    if shutil.which('pdftoppm'):
        PDF_SUPPORT = True
    else:
        PDF_SUPPORT = False
except Exception:
    PDF_SUPPORT = False

app.config['PDF_SUPPORT'] = PDF_SUPPORT

# Añadir la función now para utilizarla en las plantillas
@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

# FACTURAS_DATA en memoria (inicialmente vacío). Se limpia en cada recarga para no persistir datos demo
FACTURAS_DATA = []

# Intentar cargar mappings secretos si existen (no versionados)
try:
    from secret_mappings import MAPEO_CUENTAS_CONTABLES as SECRET_MAPEO_CUENTAS, DIRECCIONES_POR_TIPO as SECRET_DIRECCIONES, CODIGOS_AGUA_DISPONIBLES as SECRET_CODIGOS_AGUA
except Exception:
    SECRET_MAPEO_CUENTAS = {}
    SECRET_DIRECCIONES = {}
    SECRET_CODIGOS_AGUA = {}

# Integrar los mappings secretos en las estructuras locales (si existen)
# Asegurar que las variables locales existen para poder actualizarlas
if 'MAPEO_CUENTAS_CONTABLES' not in globals():
    MAPEO_CUENTAS_CONTABLES = {}

if 'DIRECCIONES_POR_TIPO' not in globals():
    DIRECCIONES_POR_TIPO = {}

if 'CODIGOS_AGUA_DISPONIBLES' not in globals():
    CODIGOS_AGUA_DISPONIBLES = {}

if SECRET_MAPEO_CUENTAS:
    # Extender el mapeo existente si procede
    try:
        MAPEO_CUENTAS_CONTABLES.update(SECRET_MAPEO_CUENTAS)
    except NameError:
        MAPEO_CUENTAS_CONTABLES = SECRET_MAPEO_CUENTAS

if SECRET_DIRECCIONES:
    try:
        DIRECCIONES_POR_TIPO.update(SECRET_DIRECCIONES)
    except NameError:
        DIRECCIONES_POR_TIPO = SECRET_DIRECCIONES

if SECRET_CODIGOS_AGUA:
    try:
        CODIGOS_AGUA_DISPONIBLES.update(SECRET_CODIGOS_AGUA)
    except NameError:
        CODIGOS_AGUA_DISPONIBLES = SECRET_CODIGOS_AGUA

# Construir mapa inverso de direccion_referencia -> (comunidad, cuenta)
def _normalize_dir_key(s):
    if not s:
        return ''
    k = s.upper()
    k = re.sub(r'[\.,/\\#\-]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

REVERSE_DIR_MAP = {}
for cmap in MAPEO_CUENTAS_CONTABLES.values():
    d = cmap.get('direccion_referencia')
    if d:
        nk = _normalize_dir_key(d)
        REVERSE_DIR_MAP[nk] = (cmap.get('comunidad'), cmap.get('cuenta'))
        # Manejar variantes de Reconquista sin ceros: 'RECONQUISTA 0014 A' -> 'RECONQUISTA 14 A' y sin letra
        m = re.match(r'(RECONQUISTA)\s*0*([0-9]+)\s*([A-Z]?)', nk)
        if m:
            grupo = m.group(1) + ' ' + str(int(m.group(2)))
            if m.group(3):
                grupo += ' ' + m.group(3)
            REVERSE_DIR_MAP[grupo] = (cmap.get('comunidad'), cmap.get('cuenta'))


# Datos de cuentas contables y sus asignaciones
CUENTAS_CONTABLES = {
    "AGUA": {
        "descripcion": "AGUA, RECOGIDA (12.15 - M - S.C.) - BARCELONA",
        "direcciones": ["LOS JARDINES DE OLÍAS", "TORRE ALTA", "VISTA HERMOSA"],
        "numero_cuenta": "62320000"
    },
    "LUZ": {
        "descripcion": "RECOGIDA DET. AULA A.",
        "direcciones": ["RECOGIDA DET. A/V", "EDIFICIO CENTRAL"],
        "numero_cuenta": "63211111"
    },
    "LIMPIEZA": {
        "descripcion": "LIMPIEZA, MANTENIMIENTO (11.12 - A) - MADRID",
        "direcciones": ["LOS JARDINES DE OLÍAS", "PLAZA MAYOR"],
        "numero_cuenta": "62150000"
    }
}

@app.route('/')
def index():
    """Ruta principal que redirige al dashboard"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard principal con las facturas"""
    # Soportar limpieza de memoria temporal: /dashboard?clear=1
    if request.args.get('clear') == '1':
        global FACTURAS_DATA
        FACTURAS_DATA = []
        logger.info('FACTURAS_DATA limpiado por solicitud del usuario')
    return render_template('dashboard.html', facturas=FACTURAS_DATA)


@app.route('/clear_memory', methods=['POST'])
def clear_memory():
    """Endpoint para limpiar la memoria temporal de facturas"""
    global FACTURAS_DATA
    FACTURAS_DATA = []
    return jsonify({'ok': True})

@app.route('/api/facturas')
def api_facturas():
    """API para obtener las facturas en formato JSON"""
    return jsonify(FACTURAS_DATA)

@app.route('/api/cuentas')
def api_cuentas():
    """API para obtener las cuentas contables en formato JSON"""
    return jsonify(CUENTAS_CONTABLES)

@app.route('/pdf_preview/<path:filename>')
def pdf_preview(filename):
    """Si el PDF subido existe, devolvemos su URL para mostrarlo en un iframe; si no, devolvemos una imagen placeholder."""
    page = request.args.get('page', 1, type=int)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Si el PDF existe en uploads, intentamos generar preview server-side si está disponible
    if os.path.exists(filepath):
        # Si el entorno tiene pdf2image + poppler, convertir la primera página a PNG y devolver base64
        if app.config.get('PDF_SUPPORT'):
            try:
                pages = convert_from_path(filepath, first_page=1, last_page=1)
                if pages and len(pages) > 0:
                    buf = io.BytesIO()
                    pages[0].save(buf, format='PNG')
                    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                    return jsonify({
                        "success": True,
                        "imageData": f"data:image/png;base64,{b64}",
                        "currentPage": 1,
                        "totalPages": 1,
                        "limitedPreview": False,
                        "message": "Vista previa generada en el servidor"
                    })
            except Exception as e:
                # Si falla la conversión, caemos al fallback a iframe
                print('pdf2image preview error:', e)

        # Fallback: devolver URL para iframe
        pdf_url = url_for('serve_upload', filename=filename)
        return jsonify({
            "success": True,
            "pdf_url": pdf_url,
            "currentPage": 1,
            "totalPages": 1,
            "limitedPreview": False,
            "message": "Vista previa usando el PDF original (iframe)"
        })

    # Imagen base64 para simular una vista previa del PDF (rectángulo blanco)
    placeholder_base64 = "iVBORw0KGgoAAAANSUhEUgAAAlgAAAGQCAIAAAD9V4nDAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAGx0lEQVR4nO3dsW4TQRiG0d3FiRMJCpqUFNDRpKRL5XfglfMQeQgqXoGGjoKKBiElEpFi2eyQAimiIGIc4Mx8Oqfczq60+m9u9bvNuZ1ms7m6uloul81fmc/nQxcA8H/Z29ubTCa7u7vD4XA0Gk2n0/v7+/1+//j4eDQatW17cXGx2Wwmk8nZ2dnl5WXTNJvNpkZpmmbbtq21bdv/fANgrW3bdjgczmaz2Wx2cnIyn8+bpmmatrvZfn5+fnR0tFgsjo+PF4vFcrlsmqZ9fX1tmuby8vL6+rppmp2dnbu7u7e3t16vd3p6en5+3rZtdXBw8PLyMp1O39/fHx4ent5s91eDwcAOLMDPPj8/q2q1WnX33Vu3g263W1XX19dVNZ/Pq2owGMxms6o6PDysqm63W1V7e3t3d3dVdXBwUFVvb29VtVwuq6qqXl9fHx4e3t/fd7vdu7u7+/v72WxWVfP5vKq+vr6qajqdVtX7+3tVPT4+VtVsNnt6ehpMp9P2y3a43bZtd/rbt7qqTdN0DcqvO5iqbqYFONjeum/164+d7XrXD/86Z9cPu6fufvx6yGAw6J662e+vHVVVbbc7Xdvc3pNvBtiyrWBVffepX9Xr9apqsVhU1XK57O4Xu7u7nU6n1+tV1WAw6Ha7VfX5+VlVvV6vqj4+Pqrq9va21+u9vLxUVXdL3O/3q+rp6Wmz2XQ6naq6ubmpqs/Pz+7pbrcLcHx83FYIwJ/9tIPbsn2DtVgs+v3+dnezvYDabgG3W8HuDVb3Mut2u2/ftm1VfesuqqrdbvttB/vtEuvbDm77J6yk/Y0d3H8+BQD4c38Z+ZcH2qo6PT3t9XrL5XI8Hne73c+Pj/FwODw/P5/P56enp/P5/OLycrVaTSaTl5eX8Xj8+Ph4dHTUNM1isRiPx03TrNfrl5eXfr+/Xq9Ho9F6vR6Px+v1+sOvCAG+838WAKAQEQJAISIEgEJECACFiBAACvlrRABQiBUhABQiQgAoRIQAUIgIAaAQEQJAISIEgEJECACFiBAACvnbly4DwD9mRQgAhYgQAAoRIQAUIkIAKESEAFCICAGgEBECQCEiBIBCRAgAhYgQAAoRIQAUIkIAKESEAFCICAGgEBECQCEiBIBCRAgAhYgQAAoRIQAUIkIAKESEAFCICAGgEBECQCEiBIBCRAgAhYgQAA"

    # Simulamos 3 páginas para cada PDF
    total_pages = 3

    return jsonify({
        "success": True,
        "imageData": f"data:image/png;base64,{placeholder_base64}",
        "currentPage": min(page, total_pages),
        "totalPages": total_pages,
        "limitedPreview": True,
        "message": "Vista previa simulada - Modo demo sin dependencias"
    })


# Servir los archivos subidos (para que el iframe pueda cargarlos)
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return ('Archivo no encontrado', 404)


@app.route('/descargar_factura/<nombre_factura>')
def descargar_factura(nombre_factura):
    """Descarga un archivo PDF; acepta parámetro download_name para renombrado"""
    download_name = request.args.get('download_name')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], nombre_factura)

    # Si el archivo existe, lo enviamos
    if os.path.exists(filepath):
        if download_name:
            try:
                return send_file(filepath, as_attachment=True, download_name=download_name)
            except TypeError:
                # Compatibilidad con versiones antiguas de Flask que usan attachment_filename
                return send_file(filepath, as_attachment=True, attachment_filename=download_name)
        return send_file(filepath, as_attachment=True)

    # Si no existe, creamos un HTML simulado
    html = render_template('factura_descarga.html', nombre=nombre_factura)
    if download_name:
        return (html, 200, {'Content-Type': 'text/html', 'Content-Disposition': f'attachment; filename="{download_name}"'})
    return html


@app.route('/toggle_procesado/<factura_id>', methods=['POST'])
def toggle_procesado(factura_id):
    """Alterna la bandera 'processed' para una factura en memoria."""
    for f in FACTURAS_DATA:
        if f.get('id') == factura_id:
            f['processed'] = not f.get('processed', False)
            return jsonify({'ok': True, 'processed': f['processed']})
    return jsonify({'ok': False}), 404


@app.route('/copiar_movimiento/<id_factura>')
def copiar_movimiento(id_factura):
    """Genera movimiento y una línea formateada para copiar."""
    factura = next((f for f in FACTURAS_DATA if f.get("id") == id_factura), None)
    if factura:
        fecha_actual = datetime.now()
        fecha_valor = (fecha_actual - timedelta(days=random.randint(0, 15))).strftime("%d/%m/%Y")

        if factura.get("estado") and factura.get("estado") != "N/A":
            match = re.search(r'(\d+[.,]\d+)', factura["estado"])
            importe = match.group(0).replace(',', '.') + " €" if match else factura["estado"]
        else:
            importe = f"{random.randint(20, 500)}.{random.randint(0, 99):02d} €"

        ref_factura = f"F{fecha_actual.strftime('%y%m%d')}-{random.randint(1000, 9999)}"
        periodo = f"{(fecha_actual - timedelta(days=30)).strftime('%d/%m/%Y')} - {fecha_actual.strftime('%d/%m/%Y')}"

        movimiento = {
            "cuenta": factura.get("cuenta_contable"),
            "numero": factura.get("numero"),
            "importe": importe,
            "fecha": fecha_valor,
            "concepto": f"Gasto {factura.get('tipo')} - {factura.get('comunidad')} - Ref: {ref_factura}",
            "periodo": periodo,
            "referencia": ref_factura
        }

        # Formato solicitado por el usuario: "Luz Reconquista 0014 A Periodo ... 73,54 €"
        formatted = f"{factura.get('tipo')} {factura.get('comunidad')} {factura.get('numero')} Periodo de medida: {periodo} {importe}"

        return jsonify({"success": True, "movimiento": movimiento, "formatted": formatted})
    return jsonify({"success": False, "error": "Factura no encontrada"}), 404


# Ajustar upload_file para incluir 'processed' en la nueva factura
@app.route('/upload', methods=['POST'])
def upload_file():
    """Procesa la carga de uno o varios archivos"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No se envió ningún archivo"}), 400

    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({"success": False, "error": "No se seleccionaron archivos"}), 400

    # Crear la carpeta de uploads si no existe
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Limpiar datos previos en memoria al procesar nuevas subidas para no mantener demo/anteriores
    global FACTURAS_DATA
    FACTURAS_DATA = []

    processed_files = []

    for file in files:
        # Guardar el archivo
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Heurística mejorada: intentamos extraer texto del PDF si PyMuPDF (fitz) está disponible
        texto_extraido = ''
        try:
            import fitz
            try:
                with fitz.open(filepath) as doc:
                    texto_extraido = "\n".join(page.get_text("text") for page in doc)
            except Exception as e:
                logger.warning('fitz extraer texto fallo: %s', e)
                texto_extraido = ''
        except Exception:
            texto_extraido = ''

        # Si no se extrajo texto, usar el nombre del archivo como fuente
        fuente_texto = texto_extraido if texto_extraido else filename

        # Detectar tipo, cups/contador, direccion e importe
        tipo = detectar_tipo_gasto(fuente_texto)
        cups_o_contador = detectar_cups_o_contador(fuente_texto)
        direccion = detectar_direccion(fuente_texto)
        importe = detectar_importe_total(fuente_texto)

        # Intentar asignar comunidad y cuenta usando el sistema híbrido
        comunidad, numero = asignar_cuenta_contable_con_tipos(cups_o_contador, direccion, tipo)

        # Estado/importe textual
        estado = f"{importe:.2f} €" if importe else "N/A"


        # Generar un nombre de archivo procesado
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        archivo_procesado = f"{filename.split('.')[0]}_PROCESADO_{timestamp}.pdf"

        # Construir movimiento contable a partir de los datos extraídos
        periodo_detectado = detectar_periodo_facturacion(fuente_texto) or f"Periodo de medida: { (datetime.now() - timedelta(days=30)).strftime('%d/%m/%Y')} - {datetime.now().strftime('%d/%m/%Y')}"
        if importe:
            importe_str = f"{importe:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')
        else:
            importe_str = "N/A"

        movimiento_str = f"{tipo} {comunidad} {numero} {periodo_detectado} {importe_str}"

        # Crear una nueva factura con datos simulados pero algo realistas
        nueva_factura = {
            "id": filename,
            "nombre": filename,
            "archivo_procesado": archivo_procesado,
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "cuenta_contable": numero,
            "tipo": tipo,
            "precio": datetime.now().strftime("%d/%m/%Y"),
            "estado": estado,
            "comunidad": comunidad,
            "numero": numero,
            "movimiento_contable": movimiento_str,
            "acciones": "ver",
            "processed": False
        }

        # Agregamos la nueva factura a nuestra lista (en memoria)
        FACTURAS_DATA.append(nueva_factura)
        processed_files.append(nueva_factura)

    # Simulamos una pequeña demora para dar sensación de procesamiento
    import time
    time.sleep(1)

    return jsonify({
        "success": True,
        "facturas": processed_files,
        "total_procesadas": len(processed_files)
    })

if __name__ == '__main__':
    print("\n=== INICIANDO VERSIÓN SIMPLIFICADA SIN DEPENDENCIAS ===")
    print("Esta versión funciona sin necesidad de instalar PyPDF2, Pillow o pdf2image.")
    print("Ideal para demostraciones donde no se pueden instalar todas las dependencias.")
    print("La vista previa de PDFs se simula con una imagen genérica.\n")
    
    # Configuración del servidor
    app.run(host='0.0.0.0', port=5000, debug=True)
