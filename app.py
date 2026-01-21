from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import hashlib
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import logging

from utils.ocr_processor import ProcesadorOCR
from utils.pdf_splitter import PDFSplitter
from utils.validator import ValidadorNotarial
from utils.auditor import Auditoria

app = Flask(__name__)
app.secret_key = 'clave_secreta_notarial_2024'
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['PROCESSED_FOLDER'] = 'processed/'

# Almacenamiento temporal de procesamiento (en producción usar Redis/DB)
procesamiento_cache = {}
# Sin límite de tamaño de archivo

# Configuración Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Usuario predeterminado
class User(UserMixin):
    def __init__(self, id):
        self.id = id

users = {'admin': {'password': 'PabloPunin1970@'}}

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in users else None

# Mapeo tipos de libro
MAPEO_TIPOS = {
    'P': 'PROTOCOLO',
    'D': 'DILIGENCIA', 
    'C': 'CERTIFICACIONES',
    'O': 'OTROS',
    'A': 'ARRIENDOS'
}

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            
            # Registrar acceso
            Auditoria.registrar_acceso(username)
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos. Verifica tus credenciales.', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                          años=list(range(2014, 2031)),
                          tipos=MAPEO_TIPOS.items())

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
        
        # Registrar en auditoría
        Auditoria.registrar_procesamiento(
            usuario=current_user.id,
            archivo=filename,
            año=año,
            tipo=tipo_libro,
            resultado=resultado
        )
        
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

if __name__ == '__main__':
    # Crear directorios necesarios
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
        for año in range(2014, 2031):
            for tipo in MAPEO_TIPOS.values():
                os.makedirs(os.path.join(folder, str(año), tipo), exist_ok=True)
    
    app.run(debug=True, port=5000)