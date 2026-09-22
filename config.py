from __future__ import annotations
import os
import platform

# Configuración básica
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_123')
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'

# Rutas de archivos
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
PROCESSED_FOLDER = os.getenv('PROCESSED_FOLDER', os.path.join(BASE_DIR, 'processed'))
LOG_FOLDER = os.path.join(BASE_DIR, 'logs')

# Rutas para módulo de escaneo
SCANNED_FOLDER = os.path.join(BASE_DIR, 'scanned')
SCANNED_ARCHIVE = os.path.join(BASE_DIR, 'scanned_archive')
ESCANEO_SEPARADO = os.path.join(BASE_DIR, 'escaneo_separado')
SCANNED_PREVIEW = os.path.join(BASE_DIR, 'scanned_preview')

# Configuración Tesseract (multiplataforma)
if platform.system() == 'Windows':
    TESSERACT_CMD = os.getenv('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
else:
    TESSERACT_CMD = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')

# Configuración de base de datos (SQLite por defecto en Windows, PostgreSQL en Linux)
DEFAULT_DB = 'sqlite:///sistema_notarial.db' if platform.system() == 'Windows' else \
    'postgresql://notarial_user:changeme123@localhost:5432/sistema_notarial'
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DB)

# Mapeo de tipos de libro (fuente única de verdad)
MAPEO_TIPOS = {
    'P': 'PROTOCOLO',
    'D': 'DILIGENCIA',
    'C': 'CERTIFICACIONES',
    'O': 'OTROS',
    'A': 'ARRIENDOS'
}

# Inverso: nombre -> letra (generado automáticamente)
MAPEO_TIPOS_INVERSO = {v: k for k, v in MAPEO_TIPOS.items()}

# Configuración de usuario
# Los usuarios se gestionan en la base de datos (models.py - Usuario)
# USUARIOS migrados a PostgreSQL con hash de contraseñas