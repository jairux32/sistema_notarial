from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
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
from utils.auditor import Auditoria

import requests

# Importar modelos de base de datos
from models import db, Usuario, Documento, Auditoria as AuditoriaDB

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración desde variables de entorno
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_123')
SCANNER_SERVICE_URL = os.getenv('SCANNER_SERVICE_URL', 'http://localhost:5001')

# Configuración de base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://notarial_user:changeme123@localhost:5432/sistema_notarial'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

# Mapeo tipos de libro
MAPEO_TIPOS = {
    'P': 'PROTOCOLO',
    'D': 'DILIGENCIA', 
    'C': 'CERTIFICACIONES',
    'O': 'OTROS',
    'A': 'ARRIENDOS'
}

# ==================== FUNCIONES HELPER ====================

def guardar_documento_procesado(session_id, nombre_archivo, resultado_procesamiento, usuario_actual=None):
    """
    Guarda un documento procesado en PostgreSQL
    
    Args:
        session_id: ID único de la sesión
        nombre_archivo: Nombre del archivo procesado
        resultado_procesamiento: Dict con resultados del procesamiento
        usuario_actual: Usuario que procesó el documento (opcional)
    
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
        print(f"❌ Error guardando documento en BD: {str(e)}")
        raise

# ==================== RUTAS ====================


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
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
    año = request.form['año']
    tipo_libro = request.form['tipo_libro']
    
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Procesar el archivo
        resultado = procesar_pdf(filepath, año, tipo_libro)
        
        # Guardar en base de datos PostgreSQL
        if resultado.get('success'):
            try:
                session_id = resultado.get('session_id')
                guardar_documento_procesado(
                    session_id=session_id,
                    nombre_archivo=filename,
                    resultado_procesamiento=resultado,
                    usuario_actual=current_user
                )
            except Exception as e:
                print(f"⚠️ Error guardando en BD (continuando): {str(e)}")
        
        return jsonify(resultado)
    
    return jsonify({'error': 'Archivo no válido'}), 400

def procesar_pdf(filepath, año, tipo_libro):
    """Procesa el PDF según la Resolución 202-2021"""
    
    print("\n" + "="*60)
    print(f"🚀 INICIANDO PROCESAMIENTO")
    print("="*60)
    print(f"📄 Archivo: {filepath}")
    print(f"📅 Año: {año}")
    print(f"📚 Tipo: {tipo_libro} ({MAPEO_TIPOS.get(tipo_libro, 'DESCONOCIDO')})")
    
    try:
        # 1. Extraer texto con OCR
        print("\n📖 PASO 1: Extrayendo texto con OCR...")
        processor = ProcesadorOCR()
        texto_ocr = processor.extraer_texto(filepath)
        print(f"✅ Texto extraído: {len(texto_ocr)} caracteres")
        
        # 2. Buscar y corregir códigos
        print("\n🔍 PASO 2: Buscando códigos notariales...")
        codigos_encontrados = processor.buscar_codigos_notariales(texto_ocr, año, tipo_libro)
        
        if not codigos_encontrados:
            print("❌ ERROR: No se encontraron códigos válidos")
            return {'error': 'No se encontraron códigos válidos en el documento'}
        
        print(f"✅ Códigos encontrados: {len(codigos_encontrados)}")
        
        # 3. Validar secuenciales
        print("\n✔️  PASO 3: Validando secuenciales...")
        validador = ValidadorNotarial()
        validacion = validador.validar_secuenciales(codigos_encontrados)
        print(f"✅ Validación completada")
        
        # 4. Dividir PDF
        print("\n✂️  PASO 4: Dividiendo PDF...")
        splitter = PDFSplitter()
        archivos_generados = splitter.dividir_por_codigos(
            filepath, 
            codigos_encontrados, 
            año, 
            tipo_libro,
            app.config['PROCESSED_FOLDER']
        )
        
        if not archivos_generados:
            print("⚠️  ADVERTENCIA: No se generaron archivos")
        
        # 5. Generar reporte PDF
        print("\n📊 PASO 5: Generando reporte PDF...")
        reporte_path = generar_reporte_pdf(
            archivos_generados, 
            validacion, 
            año, 
            tipo_libro,
            filepath
        )
        print(f"✅ Reporte generado: {reporte_path}")
        
        # 6. Generar hash de integridad
        print("\n🔐 PASO 6: Calculando hashes de integridad...")
        hashes = calcular_hashes(archivos_generados)
        print(f"✅ Hashes calculados: {len(hashes)}")
        
        print(f"\n" + "="*60)
        print("✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        print("="*60)
        
        # Generar session_id único
        session_id = str(uuid.uuid4())
        
        # Guardar datos en cache para corrección manual
        procesamiento_cache[session_id] = {
            'filepath': filepath,
            'año': año,
            'tipo_libro': tipo_libro,
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
            'ruta_salida': f"{año}/{MAPEO_TIPOS[tipo_libro]}/",
            'codigos_faltantes': validacion.get('faltantes', []),
            'session_id': session_id
        }
        
    except Exception as e:
        print(f"\n❌ ERROR EN PROCESAMIENTO: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

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
    c.drawString(100, y, f"Tipo de libro: {MAPEO_TIPOS[tipo]} ({tipo})")
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
        
        print(f"\n🔧 AGREGANDO CÓDIGO MANUAL")
        print(f"Session ID: {session_id}")
        print(f"Código: {codigo_manual}")
        print(f"Página: {pagina_inicio}")
        
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
        
        print(f"📋 Total de códigos: {len(codigos_actualizados)}")
        
        # Reprocesar división con código adicional
        splitter = PDFSplitter()
        archivos_generados = splitter.dividir_por_codigos_con_manual(
            datos['filepath'],
            codigos_actualizados,
            [(codigo_manual, pagina_inicio)],  # Códigos manuales con páginas
            datos['año'],
            datos['tipo_libro'],
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
        
        print(f"✅ Código agregado exitosamente")
        print(f"📁 Archivos generados: {len(archivos_generados)}")
        
        return jsonify({
            'success': True,
            'archivos_generados': len(archivos_generados),
            'codigos_encontrados': codigos_actualizados,
            'validacion': validacion,
            'hashes': hashes,
            'ruta_salida': f"{datos['año']}/{MAPEO_TIPOS[datos['tipo_libro']]}/",
            'codigos_faltantes': validacion.get('faltantes', []),
            'mensaje': f'Código {codigo_manual} agregado exitosamente'
        })
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    return send_file(os.path.join(app.config['PROCESSED_FOLDER'], filename))



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== API PARA DESKTOP APP ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    """Endpoint de login para la app de escritorio"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        usuario = Usuario.query.filter_by(username=username, activo=True).first()
        
        if usuario and usuario.check_password(password):
            # En producción usar JWT, aquí simulamos retorno seguro
            return jsonify({
                'success': True,
                'user': {
                    'username': usuario.username,
                    'role': getattr(usuario, 'rol', 'user')
                },
                'token': f"session_{uuid.uuid4()}"  # Token simple por ahora
            })
        return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_scan', methods=['POST'])
def api_upload_scan():
    """Recibe PDF procesado desde desktop app"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'error': 'No se envió archivo'}), 400
            
        file = request.files['pdf_file']
        # Metadatos vienen en form-data
        año = request.form.get('año')
        tipo_libro = request.form.get('tipo_libro')
        username = request.form.get('username')
        
        if not all([año, tipo_libro, username]):
             return jsonify({'error': 'Faltan metadatos (año, tipo, usuario)'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"\n📥 Recibido desde Desktop App: {filename}")
        print(f"   Usuario: {username}, Año: {año}, Tipo: {tipo_libro}")
        
        # Procesar (Validación/Splitting)
        resultado = procesar_pdf(filepath, año, tipo_libro)
        
        # Asignar usuario
        usuario_db = Usuario.query.filter_by(username=username).first()
        user_obj = User(usuario_db) if usuario_db else None
        
        if resultado.get('success'):
             session_id = resultado.get('session_id')
             guardar_documento_procesado(
                session_id=session_id,
                nombre_archivo=filename,
                resultado_procesamiento=resultado,
                usuario_actual=user_obj
            )
            
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error API Upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
    
    app.run(debug=True, host='0.0.0.0', port=5000)