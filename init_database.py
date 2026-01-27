#!/usr/bin/env python3
"""
Script de inicialización de la base de datos
Crea las tablas y el usuario admin por defecto
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Usuario, Documento, Auditoria, Configuracion

def init_database():
    """Inicializar base de datos con tablas y datos iniciales"""
    
    with app.app_context():
        print("🔧 Inicializando base de datos...")
        
        # Crear todas las tablas
        print("📊 Creando tablas...")
        db.create_all()
        print("✅ Tablas creadas")
        
        # Verificar si ya existe el usuario admin
        admin = Usuario.query.filter_by(username='admin').first()
        
        if not admin:
            print("👤 Creando usuario admin...")
            admin = Usuario(
                username='admin',
                nombre_completo='Administrador del Sistema',
                rol='admin',
                activo=True
            )
            admin.set_password('admin123')  # CAMBIAR EN PRODUCCIÓN
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuario admin creado")
            print("   Username: admin")
            print("   Password: admin123")
            print("   ⚠️  CAMBIAR PASSWORD EN PRODUCCIÓN")
        else:
            print("ℹ️  Usuario admin ya existe")
        
        # Crear configuración inicial
        configs = [
            ('version_db', '1.0', 'Versión del esquema de base de datos'),
            ('ocr_method', 'hybrid', 'Método de OCR por defecto'),
            ('max_file_size_mb', '50', 'Tamaño máximo de archivo en MB'),
        ]
        
        for clave, valor, descripcion in configs:
            config = Configuracion.query.get(clave)
            if not config:
                config = Configuracion(
                    clave=clave,
                    valor=valor,
                    descripcion=descripcion
                )
                db.session.add(config)
        
        db.session.commit()
        print("✅ Configuración inicial creada")
        
        # Mostrar estadísticas
        total_usuarios = Usuario.query.count()
        total_documentos = Documento.query.count()
        
        print("\n" + "="*50)
        print("✅ Base de datos inicializada correctamente")
        print("="*50)
        print(f"📊 Usuarios: {total_usuarios}")
        print(f"📄 Documentos: {total_documentos}")
        print("="*50)

if __name__ == '__main__':
    init_database()
