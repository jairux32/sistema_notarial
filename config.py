import os

# Configuración básica
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de Flask
SECRET_KEY = 'clave_secreta_notarial_2024_ubuntu'
DEBUG = True

# Rutas de archivos
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'processed')
LOG_FOLDER = os.path.join(BASE_DIR, 'logs')

# Sin límite de tamaño de archivo
# MAX_CONTENT_LENGTH = None

# Configuración Tesseract (Ubuntu)
TESSERACT_CMD = '/usr/bin/tesseract'

# Mapeo de tipos de libro
TIPOS_LIBRO = {
    'P': 'PROTOCOLO',
    'D': 'DILIGENCIA',
    'C': 'CERTIFICACIONES',
    'O': 'OTROS',
    'A': 'ARRIENDOS'
}

# Configuración de usuario
USUARIOS = {
    'admin': {
        'password': 'PabloPunin1970@',
        'nombre': 'Administrador Sistema'
    }
}