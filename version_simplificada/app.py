"""
Aplicación para procesamiento de facturas con autenticación
Versión simplificada y funcional
"""
from flask import Flask, render_template, jsonify, send_from_directory, request, url_for, send_file, redirect, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
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
    from pdf2image import convert_from_path
    PDF_PREVIEW_ENABLED = True
    
    # Diagnóstico de poppler al iniciar
    import shutil
    if shutil.which('pdftoppm'):
        print("✅ Poppler detectado correctamente")
    else:
        print("⚠️ Poppler no encontrado en PATH")
        # Buscar en rutas comunes
        common_paths = ['/usr/bin/pdftoppm', '/usr/local/bin/pdftoppm', '/bin/pdftoppm']
        for path in common_paths:
            if os.path.exists(path):
                print(f"✅ Poppler encontrado en: {path}")
                break
        else:
            print("❌ Poppler no encontrado en rutas comunes")
            
except ImportError:
    PDF_PREVIEW_ENABLED = False
    print("Advertencia: pdf2image no disponible. Las vistas previas de PDF estarán limitadas.")

# Configuración de Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_super_secreta_para_facturas_2025_desarrollo')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB límite de subida de archivos
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

# Configuración de base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facturas_users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensiones
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder.'
login_manager.login_message_category = 'info'

# Modelo de Usuario
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_user():
    """Hacer current_user disponible en todos los templates"""
    return dict(current_user=current_user)

@app.context_processor
def utility_processor():
    """Agregar funciones útiles a los templates"""
    def now():
        return datetime.now()
    return dict(now=now)

def create_default_users():
    """Crear los 3 usuarios por defecto si no existen"""
    # Obtener contraseñas desde variables de entorno o usar defaults para desarrollo
    users_data = [
        {
            'username': 'Dani', 
            'email': 'admin@carroblesabogados.com', 
            'password': os.environ.get('DANI_PASSWORD', 'DefaultDani123!')
        },
        {
            'username': 'Patricia', 
            'email': 'gestion@carroblesabogados.com', 
            'password': os.environ.get('PATRICIA_PASSWORD', 'DefaultPatricia123!')
        },
        {
            'username': 'Javier', 
            'email': 'direccion@carroblesabogados.com', 
            'password': os.environ.get('JAVIER_PASSWORD', 'DefaultJavier123!')
        }
    ]
    
    for user_data in users_data:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=bcrypt.generate_password_hash(user_data['password']).decode('utf-8')
            )
            db.session.add(user)
    
    db.session.commit()
    print("✅ Usuarios por defecto creados/verificados")

# Datos de facturas (simulado)
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

# Utilidades de detección
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
        t += ' ' + filename
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
        if k.upper() in texto.upper():
            return k
    return None

def detectar_direccion(texto):
    if not texto:
        return None
    
    # Buscar "Dir. Suministro:" específicamente para facturas de agua
    m_suministro = re.search(r'Dir\.?\s*Suministro[:\s]*([^,\-/\n\r]+)', texto, re.IGNORECASE)
    if m_suministro:
        direccion = m_suministro.group(1).strip()
        # Limpiar la dirección y quitar espacios extra
        direccion = re.sub(r'\s+', ' ', direccion)
        return direccion
    
    # Buscar direcciones en mappings primero
    for v in MAPEO_CUENTAS_CONTABLES.values():
        dirref = v.get('direccion_referencia', '')
        if dirref and dirref.upper() in texto.upper():
            return dirref
    
    # Buscar "AVDA. RECONQUISTA" completo hasta separadores
    m_avda = re.search(r'AVDA\.?\s*RECONQUISTA\s*\d+[^,\-/\n\r]*', texto, re.IGNORECASE)
    if m_avda:
        direccion = m_avda.group(0).strip()
        # Quitar caracteres al final que puedan ser problemáticos
        direccion = re.sub(r'[,\-/\s]+$', '', direccion)
        return direccion
    
    # Buscar variantes de RECONQUISTA sin AVDA
    tex = texto.upper()
    if 'RECONQUISTA' in tex:
        m = re.search(r'RECONQUISTA\s*\d+[^,\-/\n\r]*', tex)
        if m:
            direccion = m.group(0).strip()
            direccion = re.sub(r'[,\-/\s]+$', '', direccion)
            return direccion
    
    # fallback genérico
    m2 = re.search(r'CL(?:ALE )?\.?\s*[A-Z0-9\s]+\d+[^,\-/\n\r]*', tex)
    if m2:
        direccion = m2.group(0).strip()
        direccion = re.sub(r'[,\-/\s]+$', '', direccion)
        return direccion
    return None

def detectar_importe_total(texto):
    if not texto:
        return None

    def parse_numero(s):
        s = s.strip()
        # si tiene punto y coma europeos: punto = miles, coma = decimales
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s and not '.' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None

    texto_u = texto.upper()
    patrones = [
        r'TOTAL[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})',
        r'TOTAL A FACTURAR[:\s]*([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})'
    ]
    for patron in patrones:
        m = re.search(patron, texto_u)
        if m:
            val = parse_numero(m.group(1))
            if val:
                return val
    
    matches = re.findall(r'([0-9]{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*€', texto)
    vals = [parse_numero(s) for s in matches if parse_numero(s) is not None]
    if vals:
        return max(vals)
    
    m2 = re.search(r'(\d+[\.,]\d{2})', texto)
    if m2:
        val = parse_numero(m2.group(1))
        if val:
            return val
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
        r'(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{4})'
    ]
    
    texto_u = texto.upper()
    for patron in patrones_fecha:
        m = re.search(patron, texto_u)
        if m:
            return m.group(1)
    
    return None

def detectar_periodo_facturacion(texto):
    if not texto:
        return None
    texto_u = texto.upper()
    
    # 1. Buscar "Periodo de Medida:" específico para facturas de luz
    m_medida = re.search(r'PERIODO\s*DE\s*MEDIDA\s*:\s*(.*?)(?:\n|$)', texto_u)
    if m_medida:
        periodo_texto = m_medida.group(1).strip()
        # Limpiar texto extra pero mantener fechas completas
        periodo_limpio = re.sub(r'\s+', ' ', periodo_texto)
        return periodo_limpio
    
    # 2. Buscar "Periodo Facturado:" seguido del periodo
    m_facturado = re.search(r'PERIODO\s*FACTURADO[:\s]*((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[^0-9]*\d{4}(?:\s*[-–—]\s*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[^0-9]*\d{4})?)', texto_u)
    if m_facturado:
        return m_facturado.group(1)
    
    # 3. Buscar formatos como "FEB-MAR 2024" o "DIC 2024 - ENE 2025"
    m_meses = re.search(r'((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*(?:[-–—]\s*)?(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)?\s*\d{4}(?:\s*[-–—]\s*(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)?\s*\d{4})?)', texto_u)
    if m_meses:
        return m_meses.group(1)
    
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
        m_cod = re.search(r'COD\s*ABAST[:\.]?\s*(\d{1,6})', texto_u)
    if m_cod:
        cod = m_cod.group(1)

    m_pol = re.search(r'P\.?OLI?Z?A?[:\.]?\s*(\d{1,10})', texto_u)
    if not m_pol:
        m_pol = re.search(r'POLIZA[:\.]?\s*(\d{1,10})', texto_u)
    if m_pol:
        pol = m_pol.group(1)

    return (cod, pol)

def detectar_contador(texto):
    """Busca un identificador de contador del estilo D09NA077422 u otros alfanuméricos."""
    if not texto:
        return None
    
    # Buscar patrón específico: "Contador: XXXXXXXXX"
    m = re.search(r'Contador:\s*([A-Z0-9\-]{5,30})', texto)
    if m:
        return m.group(1)
    
    # Buscar la palabra 'CONTADOR' seguida de un token (mayúsculas)
    m2 = re.search(r'CONTADOR[:\s]*([A-Z0-9\-]{5,30})', texto.upper())
    if m2:
        return m2.group(1)
    
    # fallback: buscar tokens que parecieran número de contador (letras+digitos)
    m3 = re.search(r'([A-Z]{1,3}[0-9A-Z]{6,20})', texto.upper())
    if m3:
        return m3.group(1)
    return None

def detectar_comunidad_factura(texto, tipo_gasto):
    """Detecta la comunidad según el tipo de factura"""
    if not texto:
        return None
    
    # Para facturas de agua: buscar después de "Dir. Suministro:"
    if tipo_gasto and tipo_gasto.lower() == 'agua':
        m_dir_suministro = re.search(r'Dir\.?\s*Suministro[:\s]*([^\n\r]+)', texto, re.IGNORECASE)
        if m_dir_suministro:
            comunidad = m_dir_suministro.group(1).strip()
            
            # Tratamiento especial para agua: limpiar más agresivamente
            # Eliminar "COM PROP" y similares
            comunidad = re.sub(r'COM\s*PROP[^\w]*', '', comunidad, flags=re.IGNORECASE)
            comunidad = re.sub(r'COMUNIDAD\s+DE\s+PROPIETARIOS[^\w]*', '', comunidad, flags=re.IGNORECASE)
            
            # Para agua: cortar antes de TOLEDO y limpiar ciudades/códigos postales
            comunidad = re.sub(r',?\s*TOLEDO.*$', '', comunidad, flags=re.IGNORECASE)
            comunidad = re.sub(r',?\s*\d{5}.*$', '', comunidad)  # Eliminar códigos postales y lo que sigue
            
            # Limpiar guiones, comas y espacios al final
            comunidad = re.sub(r'[\s,\-]+$', '', comunidad)
            comunidad = re.sub(r'\s+', ' ', comunidad).strip()
            
            # Si queda algo válido, devolverlo
            return comunidad if comunidad and len(comunidad) > 3 else None
    
    # Para facturas de electricidad/luz: buscar después de "Nombre/Razón social:"
    elif tipo_gasto and tipo_gasto.lower() in ['electricidad', 'luz']:
        m_nombre_razon = re.search(r'Nombre[/\s]*Razón\s+social[:\s]*([^\n\r]+)', texto, re.IGNORECASE)
        if m_nombre_razon:
            comunidad = m_nombre_razon.group(1).strip()
            # Limpiar y eliminar "COM PROP" y similares
            comunidad = re.sub(r'COM\s*PROP[^\w]*', '', comunidad, flags=re.IGNORECASE)
            comunidad = re.sub(r'COMUNIDAD\s+DE\s+PROPIETARIOS[^\w]*', '', comunidad, flags=re.IGNORECASE)
            # Limpiar guiones y comas al final, y espacios múltiples
            comunidad = re.sub(r'[\s,\-]+$', '', comunidad)
            comunidad = re.sub(r'\s+', ' ', comunidad).strip()
            return comunidad if comunidad else None
    
    return None

def asignar_cuenta_contable_con_tipos(cups_o_contador, direccion, tipo_gasto):
    # 1. Buscar por CUPS/contador primero
    if cups_o_contador and cups_o_contador in MAPEO_CUENTAS_CONTABLES:
        entry = MAPEO_CUENTAS_CONTABLES[cups_o_contador]
        return entry.get('comunidad', 'No detectada'), entry.get('cuenta', '628')
    
    # 2. Buscar por dirección específica
    if direccion:
        for entry in MAPEO_CUENTAS_CONTABLES.values():
            if entry.get('direccion_referencia', '').upper() in direccion.upper():
                return entry.get('comunidad', 'No detectada'), entry.get('cuenta', '628')
    
    # 3. Fallback por tipo
    if tipo_gasto == 'Agua':
        return 'COMUNIDAD AGUA', '6281111'
    if tipo_gasto == 'Luz':
        return 'COMUNIDAD LUZ', '6282222'
    return 'COMUNIDAD GENERAL', '628'

def generar_nombre_archivo(fecha, proveedor, importe, numero_factura=None):
    """Genera un nombre de archivo basado en los datos de la factura"""
    try:
        # Limpiar el nombre del proveedor
        proveedor_limpio = re.sub(r'[<>:"/\\|?*]', '', proveedor)
        proveedor_limpio = proveedor_limpio.strip()[:30]
        
        # Formatear el importe
        importe_str = f"{importe:.2f}".replace('.', ',')
        
        # Generar nombre
        if numero_factura:
            nombre = f"{fecha}_{proveedor_limpio}_{importe_str}€_F{numero_factura}.pdf"
        else:
            nombre = f"{fecha}_{proveedor_limpio}_{importe_str}€.pdf"
        
        return nombre
    except Exception as e:
        return f"factura_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

def procesar_pdf_texto(file_path):
    """Procesa un PDF y extrae toda la información"""
    texto = ""
    
    # Intentar extraer texto con PyPDF2 si está disponible
    if PYPDF2_ENABLED:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    texto += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error extrayendo texto PDF: {e}")
    
    if not texto.strip():
        # Si no se pudo extraer texto, usar datos simulados
        texto = """FACTURA EJEMPLO
        Proveedor: EMPRESA EJEMPLO S.L.
        Fecha: 15/01/2025
        TOTAL: 125,50 €
        DIRECCIÓN: C/ RECONQUISTA 14 A
        CONTADOR: Q22EA038022
        """
    
    # Procesar información
    tipo_gasto = detectar_tipo_gasto(texto)
    cups_contador = detectar_cups_o_contador(texto)
    direccion = detectar_direccion(texto)
    importe = detectar_importe_total(texto)
    fecha_factura = detectar_fecha_factura(texto)
    periodo = detectar_periodo_facturacion(texto)
    cod_abast, poliza = detectar_poliza_y_cod_abast(texto)
    contador = detectar_contador(texto)
    
    # Si no hay CUPS pero sí contador, usar el contador como identificador principal
    # Para mostrar, priorizar contador si es más corto y legible
    cups_mostrar = cups_contador
    if contador and (not cups_contador or len(contador) < len(cups_contador)):
        cups_mostrar = contador
    elif contador and cups_contador and len(cups_contador) > 15:
        # Si CUPS es muy largo, mostrar el contador
        cups_mostrar = contador
    
    if not cups_contador and contador:
        cups_contador = contador
    
    # Detectar comunidad específica según el tipo de factura
    comunidad_especifica = detectar_comunidad_factura(texto, tipo_gasto)
    
    # Asignar cuenta contable (fallback si no se detecta comunidad específica)
    comunidad_fallback, cuenta_contable = asignar_cuenta_contable_con_tipos(cups_contador, direccion, tipo_gasto)
    
    # Usar comunidad específica si se detectó, sino usar el fallback
    comunidad_final = comunidad_especifica or comunidad_fallback
    
    return {
        'texto_completo': texto,
        'tipo_gasto': tipo_gasto,
        'cups_contador': cups_mostrar or 'No detectado',  # Lo que se muestra en la tabla
        'cups_original': cups_contador,  # El original para procesos
        'direccion': direccion or 'No detectada',
        'importe': importe or 0.00,
        'fecha_factura': fecha_factura or 'No detectada',
        'periodo_facturacion': periodo or 'No detectado',
        'cod_abast': cod_abast,
        'poliza': poliza,
        'contador': contador,
        'comunidad': comunidad_final,
        'cuenta_contable': cuenta_contable
    }

# Datos de cuentas contables
CUENTAS_CONTABLES = {
    "410": "Acreedores por prestaciones de servicios",
    "4100": "Proveedores",
    "4109": "Proveedores, facturas pendientes de recibir o formalizar",
    "411": "Acreedores, efectos comerciales a pagar",
    "413": "Acreedores, operaciones de factoring",
    "419": "Acreedores por operaciones en común",
    "431": "Deudores",
    "4310": "Clientes",
    "4319": "Clientes, facturas pendientes de formalizar",
    "432": "Clientes, efectos comerciales a cobrar",
    "433": "Clientes, operaciones de factoring",
    "434": "Clientes de dudoso cobro",
    "436": "Clientes de dudoso cobro",
    "440": "Deudores",
    "4400": "Deudores varios",
    "441": "Deudores, efectos comerciales a cobrar",
    "460": "Anticipos de remuneraciones",
    "465": "Remuneraciones pendientes de pago",
    "4709": "Hacienda Pública, IVA repercutido",
    "4721": "Hacienda Pública, IVA soportado",
    "473": "Hacienda Pública, retenciones y pagos a cuenta",
    "475": "Hacienda Pública, acreedor por conceptos fiscales",
    "4750": "Hacienda Pública, acreedor por IVA",
    "4751": "Hacienda Pública, acreedor por retenciones practicadas",
    "476": "Organismos de la Seguridad Social, acreedores",
    "600": "Compras de mercaderías",
    "601": "Compras de materias primas",
    "602": "Compras de otros aprovisionamientos",
    "606": "Descuentos sobre compras por pronto pago",
    "607": "Trabajos realizados por otras empresas",
    "608": "Devoluciones de compras y operaciones similares",
    "609": "Rappels por compras",
    "621": "Arrendamientos y cánones",
    "622": "Reparaciones y conservación",
    "623": "Servicios de profesionales independientes",
    "624": "Transportes",
    "625": "Primas de seguros",
    "626": "Servicios bancarios y similares",
    "627": "Publicidad, propaganda y relaciones públicas",
    "628": "Suministros",
    "629": "Otros servicios",
    "630": "Impuesto sobre beneficios",
    "631": "Otros tributos",
    "640": "Sueldos y salarios",
    "641": "Indemnizaciones",
    "642": "Seguridad Social a cargo de la empresa",
    "649": "Otros gastos sociales",
    "650": "Pérdidas de créditos comerciales incobrables",
    "651": "Resultados de operaciones en común",
    "659": "Otras pérdidas en gestión corriente",
    "662": "Intereses de deudas",
    "663": "Pérdidas por valoración de instrumentos financieros por su valor razonable",
    "665": "Intereses por descuento de efectos y operaciones de factoring",
    "666": "Pérdidas en participaciones y valores representativos de deuda",
    "667": "Pérdidas de créditos no comerciales",
    "668": "Diferencias negativas de cambio",
    "669": "Otros gastos financieros",
    "678": "Gastos excepcionales",
    "680": "Amortización del inmovilizado intangible",
    "681": "Amortización del inmovilizado material",
    "682": "Amortización de las inversiones inmobiliarias",
    "700": "Ventas de mercaderías",
    "701": "Ventas de productos terminados",
    "702": "Ventas de productos semiterminados",
    "703": "Ventas de subproductos y residuos",
    "704": "Ventas de envases y embalajes",
    "705": "Prestaciones de servicios",
    "706": "Descuentos sobre ventas por pronto pago",
    "708": "Devoluciones de ventas y operaciones similares",
    "709": "Rappels sobre ventas"
}

# ========================================
# MIDDLEWARES Y FUNCIONES AUXILIARES
# ========================================

@app.after_request
def add_security_headers(response):
    """Agregar headers de seguridad para evitar indexación"""
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ========================================
# RUTAS ANTI-INDEXACIÓN
# ========================================

@app.route('/robots.txt')
def robots():
    """Robots.txt para bloquear indexación"""
    response = app.response_class(
        response="""User-agent: *
Disallow: /
Crawl-delay: 86400

# Sitio privado - No indexar
# Private site - Do not index""",
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

# ========================================
# RUTA DE PRUEBA
# ========================================

@app.route('/test')
def test():
    """Ruta de prueba simple"""
    return "<h1>✅ Flask está funcionando</h1><p><a href='/login'>Ir al login</a></p>"

# ========================================
# RUTAS DE AUTENTICACIÓN
# ========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Por favor, completa todos los campos.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if user.is_active:
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))

# ========================================
# RUTAS PRINCIPALES
# ========================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con las facturas"""
    return render_template('dashboard.html', facturas=FACTURAS_DATA)

@app.route('/api/facturas')
@login_required
def api_facturas():
    """API para obtener las facturas en formato JSON"""
    return jsonify(FACTURAS_DATA)

@app.route('/api/cuentas')
@login_required
def api_cuentas():
    """API para obtener las cuentas contables en formato JSON"""
    return jsonify(CUENTAS_CONTABLES)

@app.route('/clear_memory', methods=['POST'])
@login_required
def clear_memory():
    """Limpiar la memoria de facturas procesadas"""
    global FACTURAS_DATA
    FACTURAS_DATA = []
    return jsonify({'success': True, 'message': 'Memoria limpiada correctamente'})

# ========================================
# RUTAS DE UPLOAD
# ========================================

@app.route('/upload', methods=['POST'])
@login_required
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

        # LOGICA DE PRIORIDAD DE ASIGNACION (1 Comunidad específica, 2 Dirección, 3 Póliza/Cód Abast., 4 Contador, 5 Periodo)
        comunidad_asig = None
        cuenta_asig = None

        # 1) Intentar detectar comunidad específica según tipo de factura
        comunidad_especifica = detectar_comunidad_factura(pdf_text, tipo)
        if comunidad_especifica:
            comunidad_asig = comunidad_especifica

        # 2) Intentar por dirección (normalizando)
        if not comunidad_asig and direccion:
            # Normalizar y buscar en mapas por coincidencia cercana
            dkey = _normalize_dir_key(direccion)
            for (t, d), datos in DIRECCIONES_POR_TIPO.items():
                if t == tipo and _normalize_dir_key(d) == dkey:
                    comunidad_asig = datos.get('comunidad')
                    cuenta_asig = datos.get('cuenta')
                    break

        # 3) Intentar por póliza o código de abastecimiento en mappings secretos
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

        # 4) Intentar por contador
        if not comunidad_asig and contador:
            if contador in MAPEO_CUENTAS_CONTABLES:
                info = MAPEO_CUENTAS_CONTABLES[contador]
                comunidad_asig = info.get('comunidad')
                cuenta_asig = info.get('cuenta')

        # 5) Fallback a asignaciones por tipo si aún no asignado
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
            importe_formateado = f"{estado_val.replace('.', ',')} EUR"
        else:
            estado_val = None
            estado = "N/A"
            importe_formateado = "N/A"

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
            texto_copia.append(f"{estado_val.replace('.', ',')}EUR")
        
        titulo_final = ' '.join([p for p in texto_copia if p])

        nueva_factura = {
            "id": filename,
            "nombre": filename,
            "archivo_procesado": nombre_renombrado,
            "cups": contador or cups or 'No detectado',  # Priorizar contador sobre CUPS
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

# ========================================
# RUTAS DE ACCIONES
# ========================================

@app.route('/copiar_movimiento/<id_factura>')
@login_required
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
@login_required
def toggle_procesado(id_factura):
    """Marcar/desmarcar factura como procesada"""
    try:
        # Buscar la factura por ID
        for f in FACTURAS_DATA:
            if str(f.get('id')) == str(id_factura):
                f['processed'] = not f.get('processed', False)
                return jsonify({
                    'success': True,
                    'processed': f['processed'],
                    'message': 'Estado actualizado correctamente'
                })
        
        return jsonify({'error': 'Factura no encontrada'}), 404
        
    except Exception as e:
        return jsonify({'error': f'Error al actualizar estado: {str(e)}'}), 500

@app.route('/diagnostico')
@login_required
def diagnostico():
    """Diagnóstico del sistema para verificar dependencias"""
    import shutil
    import subprocess
    
    diagnostico_info = {
        "pypdf2": PYPDF2_ENABLED,
        "pil": PIL_ENABLED,
        "pdf2image": PDF_PREVIEW_ENABLED,
        "poppler_en_path": bool(shutil.which('pdftoppm')),
        "poppler_version": None,
        "rutas_poppler": []
    }
    
    # Verificar versión de poppler
    if shutil.which('pdftoppm'):
        try:
            result = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True, timeout=5)
            diagnostico_info["poppler_version"] = result.stderr.strip() if result.stderr else result.stdout.strip()
        except Exception as e:
            diagnostico_info["poppler_error"] = str(e)
    
    # Buscar poppler en rutas comunes
    common_paths = ['/usr/bin/pdftoppm', '/usr/local/bin/pdftoppm', '/bin/pdftoppm']
    for path in common_paths:
        if os.path.exists(path):
            diagnostico_info["rutas_poppler"].append(path)
    
    return jsonify(diagnostico_info)

@app.route('/pdf_preview/<path:filename>')
@login_required
def pdf_preview(filename):
    """Genera y devuelve una vista previa de una página de un archivo PDF"""
    try:
        page = request.args.get('page', 1, type=int)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Archivo no encontrado"}), 404
        
        # Obtener número total de páginas de forma más robusta
        total_pages = 1
        if PYPDF2_ENABLED:
            try:
                with open(filepath, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    total_pages = len(pdf_reader.pages)
            except Exception as e:
                print(f"Error al obtener páginas con PyPDF2: {e}")
        
        # Si no hay pdf2image, devolver placeholder
        if not PDF_PREVIEW_ENABLED:
            return jsonify({
                "success": True, 
                "imageData": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAwIiBoZWlnaHQ9IjEwMDAiIHZpZXdCb3g9IjAgMCA4MDAgMTAwMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwMCIgaGVpZ2h0PSIxMDAwIiBmaWxsPSIjRjNGNEY2Ii8+Cjx0ZXh0IHg9IjQwMCIgeT0iNTAwIiBmaWxsPSIjMzc0MTUxIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIyMCI+VmlzdGEgcHJldmlhIG5vIGRpc3BvbmlibGU8L3RleHQ+Cjx0ZXh0IHg9IjQwMCIgeT0iNTQwIiBmaWxsPSIjNjM3Mzg1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCI+SW5zdGFsZSBwZGYyaW1hZ2UgcGFyYSB2ZXIgUERGczwvdGV4dD4KPC9zdmc+",
                "currentPage": 1,
                "totalPages": total_pages,
                "limitedPreview": True,
                "message": "Para ver la vista previa del PDF, instala: pip install pdf2image"
            })
        
        # Intentar convertir con pdf2image con configuración específica
        try:
            # Detectar poppler automáticamente
            import subprocess
            import shutil
            
            poppler_path = None
            
            # Verificar si pdftoppm está disponible en PATH
            if shutil.which('pdftoppm'):
                print("Poppler encontrado en PATH")
            else:
                # Intentar rutas comunes en contenedores Linux
                common_paths = [
                    '/usr/bin',
                    '/usr/local/bin',
                    '/bin'
                ]
                for path in common_paths:
                    if os.path.exists(os.path.join(path, 'pdftoppm')):
                        poppler_path = path
                        print(f"Poppler encontrado en: {poppler_path}")
                        break
            
            # Configurar variables de entorno si es necesario
            env = os.environ.copy()
            if poppler_path:
                env['PATH'] = f"{poppler_path}:{env.get('PATH', '')}"
            
            images = convert_from_path(
                filepath, 
                first_page=page, 
                last_page=page, 
                dpi=150,
                poppler_path=poppler_path,
                timeout=30,
                thread_count=1  # Usar solo un thread para evitar problemas
            )
            
            if not images:
                raise Exception("No se pudo convertir la página del PDF")
            
            # Convertir a base64
            img_io = BytesIO()
            images[0].save(img_io, 'JPEG', quality=85)
            img_io.seek(0)
            
            encoded = base64.b64encode(img_io.getvalue()).decode('utf-8')
            
            return jsonify({
                "success": True, 
                "imageData": f"data:image/jpeg;base64,{encoded}",
                "currentPage": page,
                "totalPages": total_pages
            })
            
        except Exception as e:
            print(f"Error con pdf2image: {str(e)}")
            
            # Fallback: generar imagen con texto extraído
            if PIL_ENABLED:
                try:
                    img = Image.new('RGB', (800, 1000), color='white')
                    draw = ImageDraw.Draw(img)
                    
                    # Intentar cargar fuente, si no usar default
                    try:
                        font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 24)
                        font_text = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 16)
                    except:
                        try:
                            font_title = ImageFont.load_default()
                            font_text = ImageFont.load_default()
                        except:
                            font_title = font_text = None
                    
                    # Título
                    draw.text((50, 50), f"Vista previa - {filename}", fill='black', font=font_title)
                    draw.text((50, 80), f"Página {page} de {total_pages}", fill='gray', font=font_text)
                    
                    # Extraer y mostrar texto si es posible
                    y_pos = 120
                    if PYPDF2_ENABLED and page <= total_pages:
                        try:
                            with open(filepath, 'rb') as pdf_file:
                                pdf_reader = PyPDF2.PdfReader(pdf_file)
                                if len(pdf_reader.pages) >= page:
                                    extracted_text = pdf_reader.pages[page-1].extract_text()
                                    if extracted_text:
                                        lines = extracted_text.split('\n')[:25]  # Primeras 25 líneas
                                        for line in lines:
                                            if y_pos > 950:  # No exceder el límite
                                                break
                                            # Truncar líneas muy largas
                                            line = line[:80] + '...' if len(line) > 80 else line
                                            draw.text((50, y_pos), line, fill='black', font=font_text)
                                            y_pos += 25
                        except Exception as text_error:
                            draw.text((50, y_pos), f"Error al extraer texto: {str(text_error)}", fill='red', font=font_text)
                    
                    # Guardar imagen
                    img_io = BytesIO()
                    img.save(img_io, 'JPEG', quality=85)
                    img_io.seek(0)
                    
                    encoded = base64.b64encode(img_io.getvalue()).decode('utf-8')
                    
                    return jsonify({
                        "success": True, 
                        "imageData": f"data:image/jpeg;base64,{encoded}",
                        "currentPage": page,
                        "totalPages": total_pages,
                        "limitedPreview": True,
                        "message": f"Vista previa de texto (pdf2image falló: {str(e)})"
                    })
                    
                except Exception as pil_error:
                    print(f"Error con PIL fallback: {str(pil_error)}")
            
            # Último fallback: SVG simple
            return jsonify({
                "success": True, 
                "imageData": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAwIiBoZWlnaHQ9IjEwMDAiIHZpZXdCb3g9IjAgMCA4MDAgMTAwMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwMCIgaGVpZ2h0PSIxMDAwIiBmaWxsPSIjRjNGNEY2Ii8+Cjx0ZXh0IHg9IjQwMCIgeT0iNDgwIiBmaWxsPSIjMzc0MTUxIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIyMCI+RXJyb3IgZW4gdmlzdGEgcHJldmlhPC90ZXh0Pgo8dGV4dCB4PSI0MDAiIHk9IjUyMCIgZmlsbD0iIzYzNzM4NSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9InNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiPlBvcHBsZXIgbm8gZGlzcG9uaWJsZTwvdGV4dD4KPHR5eHQgeD0iNDAwIiB5PSI1NjAiIGZpbGw9IiM2MzczODUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmb250LXNpemU9IjE0Ij5Vc2UgZWwgZW5sYWNlIGRlIGRlc2NhcmdhPC90ZXh0Pgo8L3N2Zz4K",
                "currentPage": page,
                "totalPages": total_pages,
                "limitedPreview": True,
                "message": f"Error con poppler: {str(e)}"
            })
        
    except Exception as e:
        print(f"Error general en pdf_preview: {str(e)}")
        return jsonify({
            "success": False, 
            "error": f"Error al cargar la vista previa: {str(e)}"
        }), 500

# ========================================
# RUTAS DE DESCARGA
# ========================================

@app.route('/descargar/<path:nombre_factura>')
@login_required
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
        return f"Archivo original no encontrado: {archivo_original}", 404
    
    try:
        # Limpiar el nombre para la descarga
        nombre_limpio = re.sub(r'[<>:"/\\|?*]', '_', nombre_decodificado)
        
        return send_file(
            ruta_original,
            as_attachment=True,
            download_name=nombre_limpio,
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"Error al descargar el archivo: {str(e)}", 500

@app.route('/descargar_factura/<nombre_factura>')
@login_required
def descargar_factura(nombre_factura):
    """Descarga un archivo PDF"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], nombre_factura)
    
    # Si el archivo existe, lo enviamos
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=nombre_factura)
    
    # Si no existe, devolvemos error
    return "Archivo no encontrado", 404

# ========================================
# FUNCIONES AUXILIARES Y UTILIDADES
# ========================================

def generar_nombre_archivo(fecha, proveedor, importe, numero_factura=None):
    """Genera un nombre de archivo basado en los datos de la factura"""
    try:
        # Limpiar el nombre del proveedor
        proveedor_limpio = re.sub(r'[<>:"/\\|?*]', '', proveedor)
        proveedor_limpio = proveedor_limpio.strip()[:30]  # Limitar longitud
        
        # Formatear el importe
        importe_str = f"{importe:.2f}".replace('.', ',')
        
        # Crear el nombre del archivo
        if numero_factura:
            nombre = f"{fecha}_{proveedor_limpio}_€{importe_str}_F{numero_factura}.pdf"
        else:
            nombre = f"{fecha}_{proveedor_limpio}_€{importe_str}.pdf"
        
        return nombre
    except Exception as e:
        # Si hay error, usar nombre genérico
        return f"{fecha}_factura_{random.randint(1000, 9999)}.pdf"

# ========================================
# INICIALIZACIÓN
# ========================================

if __name__ == '__main__':
    # Crear las tablas de la base de datos
    with app.app_context():
        try:
            db.create_all()
            create_default_users()
            print("🚀 Base de datos inicializada correctamente")
        except Exception as e:
            print(f"❌ Error al inicializar base de datos: {e}")
    
    # Asegurarse que existan las carpetas necesarias
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Configuración del servidor
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("🚀 Iniciando servidor de facturas...")
    print(f"🌐 Aplicación lista en el puerto {port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
