from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import hashlib
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
from dotenv import load_dotenv

from utils.ocr_processor import ProcesadorOCR
from utils.pdf_splitter import PDFSplitter
from utils.validator import ValidadorNotarial
from config import MAPEO_TIPOS, MAPEO_TIPOS_INVERSO

import requests

# Importar modelos de base de datos
from models import db, Usuario, Documento, Auditoria as AuditoriaDB

# Cargar variables de entorno
load_dotenv()

# Configurar logging con rotación
from logging.handlers import RotatingFileHandler

_log_dir = os.getenv('LOG_FOLDER', 'logs')
_log_path = os.path.join(_log_dir, 'app.log')

_handlers = [logging.StreamHandler()]
try:
    os.makedirs(_log_dir, exist_ok=True)
    _handlers.insert(0, RotatingFileHandler(_log_path, maxBytes=10*1024*1024, backupCount=5))
except OSError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=_handlers
)
logger = logging.getLogger('sistema_notarial')

app = Flask(__name__)

import platform

# Configuración desde variables de entorno
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key or app.secret_key in ('dev_key_123', 'change-this-secret-key-in-production-use-random-string'):
    import secrets
    app.secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY not set or using default — generated random key (sessions will invalidate on restart)")

# Configuración de base de datos (SQLite en Windows, PostgreSQL en Linux/Docker)
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    if platform.system() == 'Windows':
        DATABASE_URL = 'sqlite:///sistema_notarial.db'
    else:
        DATABASE_URL = 'postgresql://notarial_user:changeme123@localhost:5432/sistema_notarial'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Engine options solo para PostgreSQL
if DATABASE_URL.startswith('postgresql'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

# Configuración de carpetas desde variables de entorno
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads/')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed/')
app.config['SCANNED_FOLDER'] = os.getenv('SCANNED_FOLDER', 'scanned/')
app.config['SCANNED_ARCHIVE_FOLDER'] = os.getenv('SCANNED_ARCHIVE_FOLDER', 'scanned_archive/')
app.config['SCANNED_PREVIEW_FOLDER'] = os.getenv('SCANNED_PREVIEW_FOLDER', 'scanned_preview/')
app.config['ESCANEO_SEPARADO_FOLDER'] = os.getenv('ESCANEO_SEPARADO_FOLDER', 'escaneo_separado/')

# Inicializar base de datos
db.init_app(app)
migrate = Migrate(app, db)

# Session timeout (1 hour)
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# CSRF Protection — endpoints de API usan token, no cookies
csrf = CSRFProtect(app)

# Rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day"])

# Upload size limit (100MB)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Almacenamiento temporal de procesamiento (en producción usar Redis/DB)
procesamiento_cache = {}
# Sin límite de tamaño de archivo

# Configuración Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Clase de usuario para Flask-Login (wrapper del modelo Usuario)
class User(UserMixin):
    def __init__(self, usuario_db):
        self.id = usuario_db.username
        self.usuario_db = usuario_db
    
    def get_id(self):
        return self.usuario_db.username

@login_manager.user_loader
def load_user(user_id):
    """Cargar usuario desde base de datos"""
    usuario = Usuario.query.filter_by(username=user_id, activo=True).first()
    if usuario:
        return User(usuario)
    return None

# ==================== FUNCIONES HELPER ====================

def guardar_documento_procesado(session_id, nombre_archivo, resultado_procesamiento, usuario_actual, mes=None, numero_libro=None):
    """Guarda los metadatos del documento procesado en la BD
    
    Args:
        session_id: ID único de sesión
        nombre_archivo: Nombre del archivo original
        resultado_procesamiento: Dict con resultado de procesar_pdf
        usuario_actual: Usuario (Flask-Login)
        mes: Mes del libro (nuevo)
        numero_libro: Número del libro (nuevo)
    
    Returns:
        Documento: Objeto del documento guardado
    """
    try:
        # Obtener usuario
        usuario = None
        if usuario_actual and hasattr(usuario_actual, 'usuario_db'):
            usuario = usuario_actual.usuario_db
        
        # Extraer datos del resultado
        validacion = resultado_procesamiento.get('validacion', {})
        
        # Parsear fecha de escritura si existe
        fecha_escritura = None
        if validacion.get('fecha_escritura'):
            try:
                fecha_str = validacion['fecha_escritura']
                # Intentar diferentes formatos
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                    try:
                        fecha_escritura = datetime.strptime(fecha_str, fmt).date()
                        break
                    except:
                        continue
            except:
                pass
        
        # Crear documento
        documento = Documento(
            session_id=session_id,
            nombre_archivo=nombre_archivo,
            ruta_archivo=resultado_procesamiento.get('ruta_salida'),
            usuario=usuario,
            estado='procesado',
            tiempo_procesamiento=resultado_procesamiento.get('tiempo_procesamiento'),
            metodo_ocr=resultado_procesamiento.get('metodo_ocr', 'hybrid'),
            
            # Clasificación extendida
            mes=mes,
            numero_libro=numero_libro,
            
            # Datos extraídos
            numero_escritura=validacion.get('numero_escritura'),
            fecha_escritura=fecha_escritura,
            tipo_acto=validacion.get('tipo_acto'),
            otorgantes=validacion.get('otorgantes'),
            identificaciones=validacion.get('identificaciones'),
            cuantia=validacion.get('cuantia'),
            
            # Metadatos
            total_paginas=resultado_procesamiento.get('total_paginas'),
            confianza_promedio=validacion.get('confianza_promedio'),
            requiere_revision=len(resultado_procesamiento.get('codigos_faltantes', [])) > 0,
            
            # Guardamos el nombre del reporte en notas para poder descargarlo
            notas=os.path.basename(resultado_procesamiento.get('reporte_path', ''))
        )
        
        db.session.add(documento)
        
        # Registrar en auditoría
        if usuario:
            auditoria = AuditoriaDB(
                documento=documento,
                usuario=usuario,
                accion='procesamiento',
                detalles={
                    'archivos_generados': resultado_procesamiento.get('archivos_generados'),
                    'codigos_encontrados': len(resultado_procesamiento.get('codigos_encontrados', [])),
                    'codigos_faltantes': len(resultado_procesamiento.get('codigos_faltantes', [])),
                    'success': resultado_procesamiento.get('success', False)
                },
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get('User-Agent') if request else None
            )
            db.session.add(auditoria)
        
        db.session.commit()
        
        return documento
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error guardando documento en BD: {str(e)}")
        raise

# ==================== RUTAS ====================


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Buscar usuario en base de datos
        usuario = Usuario.query.filter_by(username=username, activo=True).first()
        
        if usuario and usuario.check_password(password):
            # Actualizar último acceso
            usuario.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            
            # Login exitoso
            user = User(usuario)
            login_user(user)
            
            # Registrar acceso en auditoría
            auditoria = AuditoriaDB(
                usuario=usuario,
                accion='login',
                detalles={'ip': request.remote_addr},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(auditoria)
            db.session.commit()
            
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos. Verifica tus credenciales.', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Obtener últimos documentos procesados
    documentos = Documento.query.filter_by(usuario_id=current_user.usuario_db.id)\
        .order_by(Documento.fecha_procesamiento.desc())\
        .limit(20).all()
        
    return render_template('dashboard.html', 
                          años=list(range(2014, 2031)),
                          tipos=MAPEO_TIPOS.items(),
                          documentos=documentos)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    file = request.files['pdf_file']
    
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Solo se permiten archivos PDF'}), 400
    
    # Validar magic bytes PDF
    header = file.read(5)
    file.seek(0)
    if header != b'%PDF-':
        return jsonify({'error': 'El archivo no es un PDF válido'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    año = request.form.get('año')
    mes = request.form.get('mes', 'DESCONOCIDO')
    tipo = request.form.get('tipo_libro', 'P')
    try:
        numero_libro = int(request.form.get('numero_libro', 0))
    except (ValueError, TypeError):
        numero_libro = 0
    
    usuario_actual = current_user if current_user.is_authenticated else None
    
    resultado = procesar_pdf(filepath, año, mes, tipo, numero_libro)
    
    if resultado.get('success'):
        try:
            session_id = resultado.get('session_id')
            if usuario_actual:
                guardar_documento_procesado(
                    session_id=session_id,
                    nombre_archivo=filename,
                    resultado_procesamiento=resultado,
                    usuario_actual=usuario_actual,
                    mes=mes,
                    numero_libro=numero_libro
                )
        except Exception as e:
            logger.warning(f"Error guardando en BD (continuando): {e}")
    
    return jsonify(resultado)

def procesar_pdf(filepath, año, mes, tipo_libro, numero_libro):
    """Procesa el PDF según la Resolución 202-2021"""
    
    logger.info(f"INICIANDO PROCESAMIENTO - Archivo: {filepath}, Año: {año}, Mes: {mes}, Tipo: {tipo_libro}, Libro: {numero_libro}")
    
    try:
        # 1. Buscar códigos notariales (OCR solo en zona superior del PDF)
        logger.info("PASO 1: Buscando códigos notariales...")
        processor = ProcesadorOCR()
        resultado = processor.buscar_codigos_notariales('', año, tipo_libro, pdf_path=filepath)
        
        if isinstance(resultado, tuple):
            codigos_encontrados, codigo_a_pagina = resultado
        else:
            codigos_encontrados = resultado
            codigo_a_pagina = {}
        
        if not codigos_encontrados:
            logger.warning("No se encontraron códigos válidos")
            return {'error': 'No se encontraron códigos válidos en el documento'}
        
        logger.info(f"Códigos encontrados: {len(codigos_encontrados)}")
        
        # 2. Validar secuenciales
        logger.info("PASO 2: Validando secuenciales...")
        validador = ValidadorNotarial()
        validacion = validador.validar_secuenciales(codigos_encontrados)
        logger.info("Validación completada")
        
        # 3. Dividir PDF
        logger.info("PASO 3: Dividiendo PDF...")
        splitter = PDFSplitter()
        archivos_generados = splitter.dividir_por_codigos(
            filepath, 
            codigos_encontrados, 
            año,
            mes,
            tipo_libro,
            numero_libro,
            app.config['PROCESSED_FOLDER'],
            codigo_a_pagina=codigo_a_pagina
        )
        
        if not archivos_generados:
            logger.warning("No se generaron archivos")
        
        # 4. Generar reporte PDF
        logger.info("PASO 4: Generando reporte PDF...")
        reporte_path = generar_reporte_pdf(
            archivos_generados, 
            validacion, 
            año, 
            tipo_libro,
            filepath
        )
        logger.info(f"Reporte generado: {reporte_path}")
        
        # 5. Generar hash de integridad
        logger.info("PASO 5: Calculando hashes de integridad...")
        hashes = calcular_hashes(archivos_generados)
        logger.info(f"Hashes calculados: {len(hashes)}")
        
        logger.info("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        
        # Generar session_id único
        session_id = str(uuid.uuid4())
        
        # Guardar datos en cache para corrección manual
        procesamiento_cache[session_id] = {
            'filepath': filepath,
            'año': año,
            'mes': mes,
            'tipo_libro': tipo_libro,
            'numero_libro': numero_libro,
            'codigos_encontrados': codigos_encontrados,
            'archivos_generados': archivos_generados
        }
        
        return {
            'success': True,
            'archivos_generados': len(archivos_generados),
            'codigos_encontrados': codigos_encontrados,
            'validacion': validacion,
            'hashes': hashes,
            'reporte_path': reporte_path,
            'ruta_salida': f"{año}/{MAPEO_TIPOS.get(tipo_libro, 'OTROS')}/",
            'codigos_faltantes': validacion.get('faltantes', []),
            'session_id': session_id
        }
        
    except Exception as e:
        logger.error(f"ERROR EN PROCESAMIENTO: {e}", exc_info=True)
        return {'error': 'Error en el procesamiento del documento'}

def generar_reporte_pdf(archivos, validacion, año, tipo, original_path):
    """Genera reporte en PDF para anexar al acta"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    reporte_path = os.path.join(
        app.config['PROCESSED_FOLDER'], 
        f"REPORTE_{año}_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    
    c = canvas.Canvas(reporte_path, pagesize=letter)
    width, height = letter
    
    # Encabezado
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 50, "REPORTE DE PROCESAMIENTO NOTARIAL")
    c.setFont("Helvetica", 10)
    c.drawString(100, height - 70, f"Resolución 202-2021 - Consejo de la Judicatura")
    
    # Información del proceso
    y = height - 100
    c.drawString(100, y, f"Fecha de procesamiento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    y -= 20
    c.drawString(100, y, f"Año configurado: {año}")
    y -= 20
    c.drawString(100, y, f"Tipo de libro: {MAPEO_TIPOS.get(tipo, 'OTROS')} ({tipo})")
    y -= 20
    c.drawString(100, y, f"Notaría: 1101007")
    y -= 20
    c.drawString(100, y, f"Archivo original: {os.path.basename(original_path)}")
    y -= 30
    
    # Estadísticas
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "ESTADÍSTICAS DEL PROCESAMIENTO")
    y -= 20
    c.setFont("Helvetica", 10)
    
    c.drawString(100, y, f"Total de archivos generados: {len(archivos)}")
    y -= 20
    c.drawString(100, y, f"Primer secuencial: {validacion.get('primer_secuencial', 'N/A')}")
    y -= 20
    c.drawString(100, y, f"Último secuencial: {validacion.get('ultimo_secuencial', 'N/A')}")
    y -= 20
    c.drawString(100, y, f"Secuenciales faltantes: {len(validacion.get('faltantes', []))}")
    y -= 30
    
    # Lista de archivos generados (primera página)
    if archivos:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y, "ARCHIVOS GENERADOS:")
        y -= 20
        c.setFont("Helvetica", 9)
        
        for i, archivo in enumerate(archivos[:30]):  # Máximo 30 por página
            c.drawString(120, y, f"{i+1}. {os.path.basename(archivo)}")
            y -= 15
            if y < 50:  # Nueva página si se acaba el espacio
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)
    
    # Hash de integridad
    c.showPage()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 50, "VERIFICACIÓN DE INTEGRIDAD")
    c.setFont("Helvetica", 10)
    
    y = height - 80
    c.drawString(100, y, "Hashes SHA-256 de los archivos:")
    y -= 20
    
    for archivo in archivos[:10]:  # Mostrar primeros 10 hashes
        with open(archivo, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        c.drawString(120, y, f"{os.path.basename(archivo)}:")
        y -= 15
        c.drawString(140, y, file_hash[:64])
        y -= 25
    
    c.save()
    return reporte_path

def calcular_hashes(archivos):
    """Calcula hash SHA-256 para cada archivo"""
    hashes = {}
    for archivo in archivos:
        with open(archivo, 'rb') as f:
            hashes[os.path.basename(archivo)] = hashlib.sha256(f.read()).hexdigest()
    return hashes

@app.route('/agregar_codigo_manual', methods=['POST'])
@login_required
def agregar_codigo_manual():
    """Endpoint para agregar código manual y reprocesar división"""
    try:
        data = request.json
        session_id = data.get('session_id')
        codigo_manual = data.get('codigo')
        pagina_inicio = int(data.get('pagina_inicio', 0))
        
        logger.info(f"AGREGANDO CÓDIGO MANUAL - Session: {session_id}, Código: {codigo_manual}, Página: {pagina_inicio}")
        
        # Validar datos
        if not session_id or session_id not in procesamiento_cache:
            return jsonify({'error': 'Sesión no encontrada o expirada'}), 400
        
        if not codigo_manual or pagina_inicio < 0:
            return jsonify({'error': 'Código y página son requeridos'}), 400
        
        # Obtener datos de procesamiento
        datos = procesamiento_cache[session_id]
        
        # Verificar que el código no exista ya
        if codigo_manual in datos['codigos_encontrados']:
            return jsonify({'error': f'El código {codigo_manual} ya existe'}), 400
        
        # Agregar código manual a la lista
        codigos_actualizados = datos['codigos_encontrados'] + [codigo_manual]
        
        logger.info(f"Total de códigos: {len(codigos_actualizados)}")
        
        # Reprocesar división con código adicional
        splitter = PDFSplitter()
        archivos_generados = splitter.dividir_por_codigos_con_manual(
            datos['filepath'],
            codigos_actualizados,
            [(codigo_manual, pagina_inicio)],  # Códigos manuales con páginas
            datos['año'],
            datos['mes'],
            datos['tipo_libro'],
            datos['numero_libro'],
            app.config['PROCESSED_FOLDER']
        )
        
        # Actualizar cache
        datos['codigos_encontrados'] = codigos_actualizados
        datos['archivos_generados'] = archivos_generados
        
        # Recalcular validación
        validador = ValidadorNotarial()
        validacion = validador.validar_secuenciales(codigos_actualizados)
        
        # Generar hashes
        hashes = calcular_hashes(archivos_generados)
        
        logger.info(f"Código agregado exitosamente - Archivos generados: {len(archivos_generados)}")
        
        return jsonify({
            'success': True,
            'archivos_generados': len(archivos_generados),
            'codigos_encontrados': codigos_actualizados,
            'validacion': validacion,
            'hashes': hashes,
            'ruta_salida': f"{datos['año']}/{MAPEO_TIPOS.get(datos['tipo_libro'], 'OTROS')}/",
            'codigos_faltantes': validacion.get('faltantes', []),
            'mensaje': f'Código {codigo_manual} agregado exitosamente'
        })
        
    except Exception as e:
        logger.error(f"ERROR: {e}", exc_info=True)
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/documentos')
@login_required
def documentos_lista():
    processed_folder = app.config['PROCESSED_FOLDER']
    anio = request.args.get('anio', type=int)
    tipo = request.args.get('tipo')
    
    anios_disponibles = sorted([d for d in os.listdir(processed_folder) 
                                if os.path.isdir(os.path.join(processed_folder, d)) and d.isdigit()], reverse=True)
    
    tipos_map = MAPEO_TIPOS_INVERSO
    
    archivos = []
    archivos_rutas = {}  # archivo -> ruta relativa
    if anio and tipo:
        año_dir = os.path.join(processed_folder, str(anio))
        if os.path.isdir(año_dir):
            for root, dirs, files in os.walk(año_dir):
                for f in files:
                    if f.endswith('.pdf') and tipo in root.upper():
                        archivos.append(f)
                        archivos_rutas[f] = os.path.relpath(os.path.join(root, f), processed_folder)
            archivos = sorted(set(archivos))
    
    return render_template('documentos.html',
                           anios_disponibles=anios_disponibles,
                           tipos_map=tipos_map,
                           anio_seleccionado=anio,
                           tipo_seleccionado=tipo,
                           archivos=archivos,
                           archivos_rutas=archivos_rutas)

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    processed_folder = os.path.realpath(app.config['PROCESSED_FOLDER'])
    filepath = os.path.realpath(os.path.join(processed_folder, filename))
    if not filepath.startswith(processed_folder + os.sep) and filepath != processed_folder:
        abort(403)
    if not os.path.exists(filepath):
        abort(404)
    return send_file(filepath)

@app.route('/download_zip', methods=['POST'])
@login_required
def download_zip():
    """Download multiple files as a ZIP archive"""
    import zipfile
    import io

    data = request.json
    filenames = data.get('files', [])

    if not filenames:
        return jsonify({'error': 'No files selected'}), 400

    processed_folder = os.path.realpath(app.config['PROCESSED_FOLDER'])

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        added = 0
        for fname in filenames:
            filepath = os.path.realpath(os.path.join(processed_folder, fname))
            if not filepath.startswith(processed_folder + os.sep):
                continue
            if os.path.exists(filepath) and os.path.isfile(filepath):
                zf.write(filepath, os.path.basename(fname))
                added += 1

    if added == 0:
        return jsonify({'error': 'No valid files found'}), 400

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'documentos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    )



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== API PARA DESKTOP APP ====================

# Token store: token -> {"username": ..., "created": ...}
api_tokens = {}

@app.route('/api/login', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def api_login():
    """Endpoint de login para la app de escritorio"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Faltan credenciales'}), 400
        
        usuario = Usuario.query.filter_by(username=username, activo=True).first()
        
        if usuario and usuario.check_password(password):
            token = f"token_{uuid.uuid4().hex}"
            api_tokens[token] = {
                'username': username,
                'created': datetime.utcnow()
            }
            return jsonify({
                'success': True,
                'user': {
                    'username': usuario.username,
                    'role': getattr(usuario, 'rol', 'user')
                },
                'token': token
            })
        return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        
    except Exception as e:
        logger.error(f"Error API Login: {e}", exc_info=True)
        return jsonify({'error': 'Error interno del servidor'}), 500

def validate_api_token():
    """Valida token de la desktop app. Retorna username o None."""
    auth_header = request.headers.get('Authorization', '')
    token = request.headers.get('X-Auth-Token', '') or auth_header.replace('Bearer ', '')
    if not token or token not in api_tokens:
        return None
    return api_tokens[token]['username']

@app.route('/api/upload_scan', methods=['POST'])
@csrf.exempt
def api_upload_scan():
    """Recibe PDF procesado desde desktop app"""
    try:
        api_username = validate_api_token()
        if not api_username:
            return jsonify({'error': 'Token inválido o expirado'}), 401
        
        if 'pdf_file' not in request.files:
            return jsonify({'error': 'No se envió archivo'}), 400
            
        file = request.files['pdf_file']
        año = request.form.get('año')
        mes = request.form.get('mes', 'DESCONOCIDO')
        tipo_libro = request.form.get('tipo_libro')
        try:
            numero_libro = int(request.form.get('numero_libro', 0))
        except (ValueError, TypeError):
            numero_libro = 0
        username = request.form.get('username')
        
        if not all([año, tipo_libro, username]):
             return jsonify({'error': 'Faltan metadatos (año, tipo, usuario)'}), 400
        
        if username != api_username:
            return jsonify({'error': 'Usuario no coincide con token'}), 403
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logger.info(f"Recibido desde Desktop App: {filename} - Usuario: {username}, Año: {año}, Mes: {mes}, Tipo: {tipo_libro}, Libro: {numero_libro}")
        
        resultado = procesar_pdf(filepath, año, mes, tipo_libro, numero_libro)
        
        usuario_db = Usuario.query.filter_by(username=username).first()
        user_obj = User(usuario_db) if usuario_db else None
        
        if resultado.get('success'):
             session_id = resultado.get('session_id')
             guardar_documento_procesado(
                session_id=session_id,
                nombre_archivo=filename,
                resultado_procesamiento=resultado,
                usuario_actual=user_obj,
                mes=mes,
                numero_libro=numero_libro
            )
            
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error API Upload: {e}", exc_info=True)
        return jsonify({'error': 'Error interno del servidor'}), 500

if __name__ == '__main__':
    # Crear directorios necesarios
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
        for año in range(2014, 2031):
            for tipo in MAPEO_TIPOS.values():
                os.makedirs(os.path.join(folder, str(año), tipo), exist_ok=True)
    
    # Crear directorios para módulo de escaneo
    for folder in ['scanned', 'scanned_archive', 'escaneo_separado', 'scanned_preview']:
        os.makedirs(folder, exist_ok=True)
    
    # Crear estructura de años y tipos en escaneo_separado
    for año in range(2014, 2031):
        for tipo in MAPEO_TIPOS.values():
            os.makedirs(os.path.join('escaneo_separado', str(año), tipo), exist_ok=True)
    
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)