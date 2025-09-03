"""
Aplicación simplificada para procesamiento de facturas - Versión sin base de datos
Esta aplicación simula el procesamiento de facturas con datos codificados directamente.
"""
from flask import Flask, render_template, jsonify, send_from_directory, request, url_for, send_file
import os
import json
import re
import random
import tempfile
import base64
from io import BytesIO
from datetime import datetime, timedelta

# Intentar importar las librerías opcionales
try:
    import PyPDF2
    PYPDF2_ENABLED = True
except ImportError:
    PYPDF2_ENABLED = False
    print("Advertencia: PyPDF2 no disponible. La extracción de texto de PDFs estará deshabilitada.")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_ENABLED = True
except ImportError:
    PIL_ENABLED = False
    print("Advertencia: Pillow no disponible. Las vistas previas estarán limitadas.")

try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF_PREVIEW_ENABLED = True
except ImportError:
    # Si no se puede importar pdf2image (poppler no instalado)
    PDF_PREVIEW_ENABLED = False
    print("Advertencia: pdf2image no disponible. Las vistas previas de PDF estarán limitadas.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_temporal_para_desarrollo'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB límite de subida de archivos
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Asegurarse de que el directorio de uploads exista
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Añadir la función now para utilizarla en las plantillas
@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

# ========================================
# PROTECCIÓN CONTRA INDEXACIÓN
# ========================================

@app.route('/robots.txt')
def robots_txt():
    """Bloquear indexación de buscadores"""
    response = app.response_class(
        response="""User-agent: *
Disallow: /
Crawl-delay: 86400

# Bloquear sitemap
Sitemap:
""",
        status=200,
        mimetype='text/plain'
    )
    return response

@app.route('/sitemap.xml')
def sitemap():
    """Sitemap vacío para evitar indexación"""
    response = app.response_class(
        response="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<!-- Sitemap intencionalmente vacío -->
</urlset>""",
        status=200,
        mimetype='application/xml'
    )
    return response

@app.after_request
def add_security_headers(response):
    """Añadir headers de seguridad y anti-indexación"""
    # Evitar indexación
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'
    # Headers de seguridad
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Cache control para contenido sensible
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Datos en memoria (vacío por defecto). Se llenarán al subir PDFs con datos reales extraídos.
FACTURAS_DATA = []

# Cargar mappings secretos si existen (no versionados)
try:
    from secret_mappings import MAPEO_CUENTAS_CONTABLES as SECRET_MAPEO_CUENTAS, DIRECCIONES_POR_TIPO as SECRET_DIRECCIONES, CODIGOS_AGUA_DISPONIBLES as SECRET_CODIGOS_AGUA
except Exception:
    SECRET_MAPEO_CUENTAS = {}
    SECRET_DIRECCIONES = {}
    SECRET_CODIGOS_AGUA = {}

# Integrar los mappings secretos en las estructuras locales (si existen)
if 'MAPEO_CUENTAS_CONTABLES' not in globals():
    MAPEO_CUENTAS_CONTABLES = {}

if 'DIRECCIONES_POR_TIPO' not in globals():
    DIRECCIONES_POR_TIPO = {}

if 'CODIGOS_AGUA_DISPONIBLES' not in globals():
    CODIGOS_AGUA_DISPONIBLES = {}

if SECRET_MAPEO_CUENTAS:
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

# Utilidades de detección (simplificadas y robustas)
def _normalize_dir_key(s):
    if not s:
        return ''
    k = s.upper()
    k = re.sub(r'[\.,/\\#\-]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

def detectar_tipo_gasto(texto, filename=None):
    t = (texto or '')
    if filename:
        t = t + '\n' + filename
    t = t.lower()
    if any(x in t for x in ['aqualia', 'agua']):
        return 'Agua'
    if any(x in t for x in ['electric', 'eléctr', 'eléctrico', 'energ', 'luz']):
        return 'Luz'
    if any(x in t for x in ['limpi', 'manten']):
        return 'Limpieza'
    return 'Otros'

def detectar_cups_o_contador(texto):
    if not texto:
        return None
    m = re.search(r'(ES[0-9A-Z]{16,20})', texto, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # buscar claves en los mappings secretos
    for k in MAPEO_CUENTAS_CONTABLES.keys():
        if k and k.upper() in texto.upper():
            return k
    return None

def detectar_direccion(texto):
    if not texto:
        return None
    tex = texto.upper()
    
    # Buscar direcciones en mappings primero
    for v in MAPEO_CUENTAS_CONTABLES.values():
        dirref = v.get('direccion_referencia', '')
        if dirref and dirref.upper() in tex:
            return dirref
    
    # Buscar variantes de RECONQUISTA
    if 'RECONQUISTA' in tex:
        # Buscar número y posibles sufijos
        m = re.search(r'RECONQUISTA\s*0*([0-9]+)(?:\s*[-\s]?([A-Z]{1,2}))?(?:\s*[-\s]?([A-Z]?))?', tex)
        if m:
            num = str(int(m.group(1)))
            # Construir la dirección base
            direccion_base = f'RECONQUISTA {num}'
            
            # Si encontramos la dirección específica en mappings, usarla
            for v in MAPEO_CUENTAS_CONTABLES.values():
                dirref = v.get('direccion_referencia', '')
                if dirref and dirref.upper().startswith(f'RECONQUISTA 00{num.zfill(2)}'):
                    return dirref
                if dirref and dirref.upper().startswith(f'RECONQUISTA {num}'):
                    return dirref
            
            # Si no encontramos en mappings, construir desde el texto
            suf = ''
            if m.group(2):  # Segundo sufijo como "PO"
                suf = f' {m.group(2)}'
            if m.group(3):  # Tercer sufijo como "C"
                suf += f' {m.group(3)}'
            
            return f'{direccion_base}{suf}'.strip()
    
    # fallback genérico
    m2 = re.search(r'CL(?:ALE )?\.?\s*[A-Z0-9\s]+\d+', tex)
    if m2:
        return m2.group(0)
    return None

def detectar_importe_total(texto):
    if not texto:
        return None

    def parse_numero(s):
        s = s.strip()
        if ',' in s and '.' in s:
            s2 = s.replace('.', '').replace(',', '.')
        elif ',' in s and not '.' in s:
            s2 = s.replace(',', '.')
        else:
            s2 = s
        try:
            return float(s2)
        except Exception:
            return None

    texto_u = texto.upper()
    patrones = [r'TOTAL[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})', r'TOTAL A FACTURAR[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})']
    for patron in patrones:
        m = re.search(patron, texto_u, re.IGNORECASE)
        if m:
            val = parse_numero(m.group(1))
            if val is not None:
                return val
    matches = re.findall(r'([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€', texto)
    vals = [parse_numero(s) for s in matches if parse_numero(s) is not None]
    if vals:
        return max(vals)
    m2 = re.search(r'(\d+[\.,]\d{2})', texto)
    if m2:
        return parse_numero(m2.group(1))
    return None

def detectar_fecha_factura(texto):
    """Detecta la fecha de emisión de la factura del PDF"""
    if not texto:
        return None
    
    # Buscar "Fecha emisión:", "Fecha factura:", etc.
    patrones_fecha = [
        r'FECHA\s*(?:DE\s*)?(?:EMISI[OÓ]N|FACTURA)[:\s]*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})',
        r'(?:EMITIDO|EMISIÓN)[:\s]*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})',
        r'FACTURA\s*(?:N[º°]?[:\s]*\d+\s*)?(?:DE\s*)?FECHA[:\s]*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})',
        r'(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{4})'  # Fallback: cualquier fecha con año completo
    ]
    
    texto_u = texto.upper()
    for patron in patrones_fecha:
        matches = re.findall(patron, texto_u)
        if matches:
            # Tomar la primera fecha encontrada y normalizarla
            fecha_str = matches[0]
            # Normalizar separadores a /
            fecha_norm = fecha_str.replace('-', '/').replace('.', '/')
            try:
                # Intentar parsear para validar que es una fecha válida
                from datetime import datetime
                # Intentar diferentes formatos
                for fmt in ['%d/%m/%Y', '%d/%m/%y']:
                    try:
                        fecha_obj = datetime.strptime(fecha_norm, fmt)
                        # Si el año es muy futuro o muy pasado, probablemente está mal
                        if 2020 <= fecha_obj.year <= 2030:
                            return fecha_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        continue
            except:
                pass
            # Si no se puede parsear, devolver tal como está
            return fecha_norm
    
    return None

def detectar_periodo_facturacion(texto):
    if not texto:
        return None
    texto_u = texto.upper()
    
    # 1. Buscar "Periodo Facturado:" seguido del periodo
    m_facturado = re.search(r'PERIODO\s*FACTURADO[:\s]*((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[^0-9]*\d{4}(?:\s*[-–—]\s*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[^0-9]*\d{4})?)', texto_u)
    if m_facturado:
        periodo = m_facturado.group(1).strip()
        # Limpiar y normalizar
        periodo = re.sub(r'\s+', ' ', periodo)
        periodo = periodo.replace('–', '-').replace('—', '-')
        return periodo
    
    # 2. Buscar formatos como "FEB-MAR 2024" o "DIC 2024 - ENE 2025"
    m_meses = re.search(r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*(?:[-–—]\s*)?(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)?\s*\d{4}(?:\s*[-–—]\s*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)?\s*\d{4})?)', texto_u)
    if m_meses:
        periodo = m_meses.group(1).strip()
        periodo = re.sub(r'\s+', ' ', periodo)
        periodo = periodo.replace('–', '-').replace('—', '-')
        return periodo
    
    # 3. Buscar formatos tipo: DIC 2024 - ENE 2025 (separados)
    m_separado = re.search(r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*\d{4})\s*(?:[-–—]|A|AL)\s*((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*\d{4})', texto_u)
    if m_separado:
        p1 = m_separado.group(1).strip()
        p2 = m_separado.group(2).strip()
        return f"{p1} - {p2}"
    
    # 4. Fallback: buscar rangos de fechas en formato dd/mm/yyyy
    m_fechas = re.search(r'(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}).{0,40}?(?:al|a|to).{0,40}?(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})', texto, re.IGNORECASE)
    if m_fechas:
        d1 = m_fechas.group(1).replace('.', '/').replace('-', '/')
        d2 = m_fechas.group(2).replace('.', '/').replace('-', '/')
        return f"{d1} - {d2}"
    
    return None


def detectar_poliza_y_cod_abast(texto):
    """Busca Cód. Abast. y Póliza en el texto. Devuelve (cod_abast, poliza) o (None, None)."""
    if not texto:
        return (None, None)
    texto_u = texto.upper()
    cod = None
    pol = None
    m_cod = re.search(r'C\.?\s*ABAST[:\.]?\s*(\d{1,6})', texto_u)
    if not m_cod:
        m_cod = re.search(r'COD(?:\.|IGO)?\s*ABAST(?:\.?:)?\s*(\d{1,6})', texto_u)
    if m_cod:
        cod = m_cod.group(1)

    m_pol = re.search(r'P\.?OLI?Z?A?[:\.]?\s*(\d{1,10})', texto_u)
    if not m_pol:
        # buscar 'Póliza: 52638' variaciones
        m_pol = re.search(r'POLIZA[:\s]*([0-9]{1,10})', texto_u)
    if m_pol:
        pol = m_pol.group(1)

    return (cod, pol)


def detectar_contador(texto):
    """Busca un identificador de contador del estilo Q22EA038022 u otros alfanuméricos."""
    if not texto:
        return None
    # buscar la palabra 'CONTADOR' seguida de un token
    m = re.search(r'CONTADOR[:\s]*([A-Z0-9\-]{5,30})', texto.upper())
    if m:
        return m.group(1)
    # fallback: buscar tokens que parecieran número de contador (letras+digitos)
    m2 = re.search(r'([A-Z]{1,3}[0-9A-Z]{6,20})', texto.upper())
    if m2:
        return m2.group(1)
    return None

def asignar_cuenta_contable_con_tipos(cups_o_contador, direccion, tipo_gasto):
    # 1. Buscar por CUPS/contador primero
    if cups_o_contador and cups_o_contador in MAPEO_CUENTAS_CONTABLES:
        entry = MAPEO_CUENTAS_CONTABLES[cups_o_contador]
        return entry.get('comunidad', 'No definida'), entry.get('cuenta', '0000000')
    
    # 2. Buscar por dirección específica
    if direccion:
        direccion_upper = direccion.upper()
        
        # Buscar coincidencia exacta en mappings
        for entry in MAPEO_CUENTAS_CONTABLES.values():
            dirref = entry.get('direccion_referencia', '')
            if dirref and dirref.upper() == direccion_upper:
                return entry.get('comunidad', 'No definida'), entry.get('cuenta', '0000000')
        
        # Buscar por DIRECCIONES_POR_TIPO
        key = (tipo_gasto, direccion_upper)
        for (t, d), datos in DIRECCIONES_POR_TIPO.items():
            if t == tipo_gasto and d.upper() == direccion_upper:
                return datos.get('comunidad'), datos.get('cuenta')
        
        # Buscar parcial en mappings (para variantes)
        for entry in MAPEO_CUENTAS_CONTABLES.values():
            dirref = entry.get('direccion_referencia', '')
            if dirref and 'RECONQUISTA' in dirref.upper() and 'RECONQUISTA' in direccion_upper:
                return entry.get('comunidad', 'No definida'), entry.get('cuenta', '0000000')
        
        # Si es una dirección de RECONQUISTA, asignar a RECONQUISTA XIV
        if 'RECONQUISTA' in direccion_upper and any(x in direccion_upper for x in ['14', 'CATORCE']):
            return 'RECONQUISTA XIV', '6281000'
    
    # 3. Fallback por tipo
    if tipo_gasto == 'Agua':
        return 'LOS JARDINES DE OLIAS', '62320000'
    if tipo_gasto == 'Luz':
        return 'RECOGIDA DET. A/V', '63211111'
    return 'COMUNIDAD GENERAL', '62900000'

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
@app.route('/dashboard')
def dashboard():
    """Dashboard principal con las facturas - Ahora es la página principal"""
    return render_template('dashboard.html', facturas=FACTURAS_DATA)

@app.route('/api/facturas')
def api_facturas():
    """API para obtener las facturas en formato JSON"""
    return jsonify(FACTURAS_DATA)

@app.route('/api/cuentas')
def api_cuentas():
    """API para obtener las cuentas contables en formato JSON"""
    return jsonify(CUENTAS_CONTABLES)

@app.route('/descargar/<path:nombre_factura>')
def descargar_html(nombre_factura):
    """Descarga el archivo original con el nombre renombrado o original"""
    from urllib.parse import unquote
    import re
    
    # Decodificar la URL para manejar caracteres especiales
    nombre_decodificado = unquote(nombre_factura)
    
    # Buscar la factura por su nombre renombrado o nombre original
    factura = next((f for f in FACTURAS_DATA if 
                   f.get("archivo_procesado") == nombre_decodificado or 
                   f.get("nombre") == nombre_decodificado), None)
    if not factura:
        return f"Factura no encontrada: {nombre_decodificado}", 404
    
    # Obtener el archivo original
    archivo_original = factura.get("nombre")
    if not archivo_original:
        return "Archivo original no encontrado", 404
    
    # Construir la ruta del archivo original
    ruta_original = os.path.join(app.config['UPLOAD_FOLDER'], archivo_original)
    if not os.path.exists(ruta_original):
        return "Archivo no encontrado en el sistema", 404
    
    # Determinar el nombre de descarga y limpiarlo
    if factura.get("archivo_procesado"):
        nombre_descarga = factura['archivo_procesado']
        # Agregar .pdf si no tiene extensión
        if not nombre_descarga.endswith('.pdf'):
            nombre_descarga += '.pdf'
    else:
        # Si no hay nombre procesado, usar el original
        nombre_descarga = archivo_original
    
    # Limpiar el nombre de archivo para evitar problemas con headers
    # Reemplazar caracteres problemáticos
    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nombre_descarga)
    nombre_limpio = nombre_limpio.replace('€', 'EUR')
    
    try:
        return send_file(
            ruta_original,
            as_attachment=True,
            download_name=nombre_limpio,
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"Error al descargar el archivo: {str(e)}", 500

@app.route('/copiar_movimiento/<id_factura>')
def copiar_movimiento(id_factura):
    """Devuelve solo el concepto para copiar al portapapeles"""
    # Buscar la factura correspondiente
    factura = next((f for f in FACTURAS_DATA if f["id"] == id_factura), None)
    if factura:
        # Solo devolver el concepto/movimiento contable
        concepto = factura.get('movimiento_contable') or ''
        return jsonify({"success": True, "concepto": concepto})
    return jsonify({"success": False, "error": "Factura no encontrada"}), 404

@app.route('/toggle_procesado/<id_factura>', methods=['POST'])
def toggle_procesado(id_factura):
    """Cambia el estado de procesado de una factura"""
    # Buscar la factura correspondiente
    factura = next((f for f in FACTURAS_DATA if f["id"] == id_factura), None)
    if factura:
        # Cambiar el estado
        factura["procesado"] = not factura.get("procesado", False)
        return jsonify({"success": True, "procesado": factura["procesado"]})
    return jsonify({"success": False, "error": "Factura no encontrada"}), 404

@app.route('/pdf_preview/<path:filename>')
def pdf_preview(filename):
    """Genera y devuelve una vista previa de una página de un archivo PDF"""
    page = request.args.get('page', 1, type=int)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": "Archivo no encontrado"}), 404
    
    # Si no hay librerías para procesar PDFs, devolver imagen de marcador de posición
    if not PYPDF2_ENABLED or not PIL_ENABLED:
        # Devolver imagen simulada base64 como marcador de posición
        placeholder_base64 = "iVBORw0KGgoAAAANSUhEUgAAAlgAAAGQCAYAAAByNR6YAAAACXBIWXMAAAsTAAALEwEAmpwYAAABNmlDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjarY6xSsNQFEDPi6LiUCsEcXB4kygotupgxqQtRRCs1SHJ1qShSmkSXl7VfoSjWwcXd7/AyVFwUPwC/0Bx6uAQIYODCJ7p3MPlcsGo2HWnYZRhEGvVbjrS9Xw5+8QMUwDQCbPUbrUOAOIkjvjB5ysC4HnTrjsN/sZ8mCoNTIDtbpSFICpA/0KnGsQYMIN+qkHcAaY6addAPAClXu4vQCnI/Q0oKdfzQXwAZs/1fDDmADPIfQUwdXSpAWpJOlJnvVMtq5ZlSbubBJE8HmU6GmRyPw4TlSaqo6MukP8HwGK+2G46cq1qWXvr/DOu58vc3o8QgFh6LFpBOFTn3yqMnd/n4sZ4GQ5vYXpStN0ruNmAheuirVahvAX34y/Axk/96FpPYgAAAAlwSFlzAAALEwAACxMBAJqcGAAACdBJREFUeJzt2DEBwCAQwLCCf89IAB9ISCTsHnT3DADAnN8BACCnYAEAhBQsAICQggUAEFKwAABCChYAQEjBAgAIKVgAACEFCwAgpGABAIQULACAkIIFABBSsAAAQgoWAEBIwQIACClYAAAhBQsAIKRgAQCEFCwAgJCCBQAQUrAAAEIKFgBASMECAAg9S/cLE48d6xYAAAAASUVORK5CYII="
        return jsonify({
            "success": True, 
            "imageData": f"data:image/png;base64,{placeholder_base64}",
            "currentPage": 1,
            "totalPages": 1,
            "limitedPreview": True,
            "message": "Para ver la vista previa del PDF, instala las dependencias necesarias: pip install PyPDF2 pillow pdf2image"
        })
    
    try:
        # Crear un marcador de posición básico que muestra información del archivo
        total_pages = 1  # Valor predeterminado
        
        # Intentar obtener el número de páginas si PyPDF2 está disponible
        if PYPDF2_ENABLED:
            try:
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    total_pages = len(pdf_reader.pages)
            except Exception as e:
                print(f"Error al leer el PDF: {str(e)}")
        
        # Generar vista previa
        if PDF_PREVIEW_ENABLED:
            # Convertir la página del PDF a imagen usando pdf2image
            images = convert_from_path(filepath, first_page=page, last_page=page)
            if images:
                img_io = BytesIO()
                images[0].save(img_io, 'JPEG', quality=85)
                img_io.seek(0)
                
                # Convertir la imagen a base64 para enviarla como JSON
                encoded = base64.b64encode(img_io.getvalue()).decode('utf-8')
                
                return jsonify({
                    "success": True, 
                    "imageData": f"data:image/jpeg;base64,{encoded}",
                    "currentPage": page,
                    "totalPages": total_pages
                })
        elif PIL_ENABLED:
            # Método alternativo si pdf2image no está disponible pero Pillow sí
            img = Image.new('RGB', (800, 1000), color='white')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 30)
            except IOError:
                font = ImageFont.load_default()
            
            # Obtener texto de la página si es posible
            page_text = f"Vista previa del archivo: {filename}\nPágina {page} de {total_pages}"
            
            if PYPDF2_ENABLED and page <= total_pages:
                try:
                    with open(filepath, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        extracted_text = pdf_reader.pages[page-1].extract_text()
                        if extracted_text:
                            # Mostrar las primeras líneas
                            lines = extracted_text.split('\n')[:15]
                            page_text += "\n\n" + '\n'.join(lines)
                except Exception as e:
                    page_text += f"\n\nError al extraer texto: {str(e)}"
            
            draw.text((50, 50), page_text, fill='black', font=font)
            
            img_io = BytesIO()
            img.save(img_io, 'JPEG', quality=85)
            img_io.seek(0)
            
            encoded = base64.b64encode(img_io.getvalue()).decode('utf-8')
            
            return jsonify({
                "success": True, 
                "imageData": f"data:image/jpeg;base64,{encoded}",
                "currentPage": page,
                "totalPages": total_pages,
                "limitedPreview": True
            })
        else:
            # No hay librerías disponibles para generar vista previa
            return jsonify({
                "success": True,
                "imageData": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAlgAAAGQCAYAAAByNR6YAAAACXBIWXMAAAsTAAALEwEAmpwYAAABNmlDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjarY6xSsNQFEDPi6LiUCsEcXB4kygotupgxqQtRRCs1SHJ1qShSmkSXl7VfoSjWwcXd7/AyVFwUPwC/0Bx6uAQIYODCJ7p3MPlcsGo2HWnYZRhEGvVbjrS9Xw5+8QMUwDQCbPUbrUOAOIkjvjB5ysC4HnTrjsN/sZ8mCoNTIDtbpSFICpA/0KnGsQYMIN+qkHcAaY6addAPAClXu4vQCnI/Q0oKdfzQXwAZs/1fDDmADPIfQUwdXSpAWpJOlJnvVMtq5ZlSbubBJE8HmU6GmRyPw4TlSaqo6MukP8HwGK+2G46cq1qWXvr/DOu58vc3o8QgFh6LFpBOFTn3yqMnd/n4sZ4GQ5vYXpStN0ruNmAheuirVahvAX34y/Axk/96FpPYgAAAAlwSFlzAAALEwAACxMBAJqcGAAACdBJREFUeJzt2DEBwCAQwLCCf89IAB9ISCTsHnT3DADAnN8BACCnYAEAhBQsAICQggUAEFKwAABCChYAQEjBAgAIKVgAACEFCwAgpGABAIQULACAkIIFABBSsAAAQgoWAEBIwQIACClYAAAhBQsAIKRgAQCEFCwAgJCCBQAQUrAAAEIKFgBASMECAAg9S/cLE48d6xYAAAAASUVORK5CYII=",
                "currentPage": page,
                "totalPages": total_pages,
                "limitedPreview": True,
                "message": "Vista previa no disponible. Instale las dependencias necesarias."
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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

    # Eliminar facturas anteriores al subir nuevas (según requisito)
    FACTURAS_DATA.clear()
    processed_files = []
    
    # Leer opciones de formulario: asumimos que si no vienen, el archivo es una factura
    pdf_optimizado = request.form.get('pdf_optimizado', 'on') == 'on'
    # por defecto tratamos como factura si el campo no viene
    pdf_factura = request.form.get('pdf_factura', 'on') == 'on'

    for file in files:
        # Guardar el archivo
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Analizar el nombre del archivo para determinar tipo
        filename_lower = filename.lower()

        # Extraer texto del PDF para análisis si PyPDF2 está disponible
        pdf_text = ""
        if PYPDF2_ENABLED:
            try:
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    for page_num in range(min(2, len(pdf_reader.pages))):  # Solo las primeras 2 páginas
                        pdf_text += pdf_reader.pages[page_num].extract_text() or ""
            except Exception as e:
                print(f"Error al extraer texto del PDF: {str(e)}")

        # Determinar campos usando extractores reutilizables
        tipo = detectar_tipo_gasto(pdf_text, filename)
        cups = detectar_cups_o_contador(pdf_text)
        direccion = detectar_direccion(pdf_text)
        importe_val = detectar_importe_total(pdf_text)
        periodo = detectar_periodo_facturacion(pdf_text)
        fecha_factura = detectar_fecha_factura(pdf_text)  # Nueva detección de fecha

        # Detectar póliza y código de abastecimiento y contador
        cod_abast, poliza = detectar_poliza_y_cod_abast(pdf_text)
        contador = detectar_contador(pdf_text)

        # LOGICA DE PRIORIDAD DE ASIGNACION (1 Dirección, 2 Póliza/Cód Abast., 3 Contador, 4 Periodo)
        comunidad_asig = None
        cuenta_asig = None

        # 1) Intentar por dirección (normalizando)
        if direccion:
            # Normalizar y buscar en mapas por coincidencia cercana
            dkey = _normalize_dir_key(direccion)
            for (t, d), datos in DIRECCIONES_POR_TIPO.items():
                if t == tipo and _normalize_dir_key(d) == dkey:
                    comunidad_asig = datos.get('comunidad')
                    cuenta_asig = datos.get('cuenta')
                    break

        # 2) Intentar por póliza o código de abastecimiento en mappings secretos
        if not comunidad_asig and (poliza or cod_abast):
            # buscar en MAPEO_CUENTAS_CONTABLES por campos internos
            for k, v in MAPEO_CUENTAS_CONTABLES.items():
                info = v or {}
                # revisar si poliza o cod_abast aparecen en cualquiera de los valores
                textvals = ' '.join([str(x).upper() for x in info.values() if x])
                if poliza and poliza.upper() in textvals:
                    comunidad_asig = info.get('comunidad')
                    cuenta_asig = info.get('cuenta')
                    break
                if cod_abast and str(cod_abast) in textvals:
                    comunidad_asig = info.get('comunidad')
                    cuenta_asig = info.get('cuenta')
                    break

        # 3) Intentar por contador
        if not comunidad_asig and contador:
            if contador in MAPEO_CUENTAS_CONTABLES:
                info = MAPEO_CUENTAS_CONTABLES[contador]
                comunidad_asig = info.get('comunidad')
                cuenta_asig = info.get('cuenta')

        # 4) Fallback a asignaciones por tipo si aún no asignado
        if not comunidad_asig:
            comunidad_asig, cuenta_asig = asignar_cuenta_contable_con_tipos(cups, direccion, tipo)

        # Normalizar valores para guardar
        comunidad = comunidad_asig or 'COMUNIDAD GENERAL'
        numero = cuenta_asig or '62900000'
        # Estado/importe: si detectamos importe, formatearlo (usar coma decimal)
        if importe_val is not None:
            # forzar dos decimales y usar coma
            estado_val = f"{importe_val:.2f}"
            estado = f"{estado_val.replace('.', ',')}"
            importe_formateado = f"{estado_val.replace('.', ',')} €"
        else:
            estado_val = None
            estado = "N/A"
            importe_formateado = "N/A"

        # Normalizar valores para guardar
        comunidad = comunidad_asig or 'COMUNIDAD GENERAL'
        numero = cuenta_asig or '62900000'

        # Construir chosen_location para el nombre renombrado
        chosen_location = None
        if direccion:
            chosen_location = direccion
        elif poliza or cod_abast:
            chosen_location = f"Póliza {poliza}" if poliza else f"Cód.Abast. {cod_abast}"
        elif contador:
            chosen_location = f"Contador {contador}"

        # Generar nombre renombrado con formato: Agua Reconquista 14 C 08-04-2024 11,10EUR
        fecha_para_nombre = fecha_factura or datetime.now().strftime("%d/%m/%Y")
        # Reemplazar barras por guiones para compatibilidad con sistemas de archivos
        fecha_para_nombre = fecha_para_nombre.replace("/", "-")
        direccion_para_nombre = chosen_location or comunidad or "Sin Direccion"
        importe_para_nombre = f"{estado_val.replace('.', ',')}EUR" if estado_val else "0EUR"
        
        nombre_renombrado = f"{tipo} {direccion_para_nombre} {fecha_para_nombre} {importe_para_nombre}"

        # Determinar estado de validación
        datos_criticos = [tipo, importe_val, comunidad_asig]
        datos_opcionales = [direccion, fecha_factura, periodo]
        
        criticos_completos = sum(1 for d in datos_criticos if d)
        opcionales_completos = sum(1 for d in datos_opcionales if d)
        
        if criticos_completos == len(datos_criticos) and opcionales_completos >= 2:
            estado_validacion = "success"  # Verde
        elif criticos_completos == len(datos_criticos):
            estado_validacion = "warning"  # Amarillo
        else:
            estado_validacion = "danger"   # Rojo

        # Construir texto simple para copia al portapapeles: "Agua RECONQUISTA 14 C Periodo Facturacion de ABR-MAY 2024 13,57€"
        texto_copia = []
        if tipo:
            texto_copia.append(tipo)
        if chosen_location:
            texto_copia.append(chosen_location.upper())
        if periodo:
            texto_copia.append(f"Periodo Facturacion de {periodo}")
        if estado_val:
            texto_copia.append(f"{estado_val.replace('.', ',')}€")
        
        titulo_final = ' '.join([p for p in texto_copia if p])

        nueva_factura = {
            "id": filename,
            "nombre": filename,
            "archivo_procesado": nombre_renombrado,
            "cups": cups,
            "direccion": direccion,
            "fecha": fecha_factura or datetime.now().strftime("%d/%m/%Y"),
            "tipo": tipo,
            "importe": importe_formateado,
            "estado": estado_validacion,
            "comunidad": comunidad,
            "cuenta": numero,
            "cuenta_contable": numero,
            "procesado": False,  # Campo para controlar si está procesado
            "movimiento_contable": titulo_final or f"Gasto {tipo} - {comunidad} - Importe: {estado} - Periodo: {periodo or 'N/D'}",
            "aprobacion": "Águila Avilés, Reconocimiento (15 días) - Fecha límite: hoy",
            "acciones": "ver"
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

@app.route('/descargar_factura/<nombre_factura>')
def descargar_factura(nombre_factura):
    """Descarga un archivo PDF"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], nombre_factura)
    
    # Si el archivo existe, lo enviamos
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=nombre_factura)
    
    # Si no existe, creamos un PDF simulado
    return render_template('factura_descarga.html', nombre=nombre_factura)

if __name__ == '__main__':
    # Asegurarse que exista la carpeta para las plantillas
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Configuración del servidor
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
