"""
Script de migración de datos de JSON a PostgreSQL
Ejecutar después de levantar los contenedores Docker
"""
import json
import os
from datetime import datetime
from app import app, db
from models import Usuario, Documento, Auditoria

def migrar_datos():
    """Migrar datos del archivo JSON a PostgreSQL"""
    
    json_file = 'auditoria_notarial.json'
    
    if not os.path.exists(json_file):
        print(f"❌ Archivo {json_file} no encontrado")
        return
    
    with app.app_context():
        print("🔄 Iniciando migración de datos...")
        
        # Leer datos del JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📄 Encontrados {len(data)} registros en JSON")
        
        # Crear usuario por defecto si no existe
        usuario = Usuario.query.filter_by(username='admin').first()
        if not usuario:
            usuario = Usuario(
                username='admin',
                nombre_completo='Administrador del Sistema',
                rol='admin'
            )
            usuario.set_password('admin123')  # CAMBIAR EN PRODUCCIÓN
            db.session.add(usuario)
            db.session.commit()
            print("✅ Usuario admin creado")
        
        # Migrar documentos
        migrados = 0
        errores = 0
        
        for session_id, doc_data in data.items():
            try:
                # Verificar si ya existe
                if Documento.query.filter_by(session_id=session_id).first():
                    print(f"⏭️  Documento {session_id} ya existe, saltando...")
                    continue
                
                # Parsear fecha de escritura
                fecha_escritura = None
                if doc_data.get('fecha_escritura'):
                    try:
                        fecha_escritura = datetime.strptime(
                            doc_data['fecha_escritura'], 
                            '%Y-%m-%d'
                        ).date()
                    except:
                        pass
                
                # Parsear fecha de procesamiento
                fecha_procesamiento = datetime.utcnow()
                if doc_data.get('timestamp'):
                    try:
                        fecha_procesamiento = datetime.fromisoformat(
                            doc_data['timestamp'].replace('Z', '+00:00')
                        )
                    except:
                        pass
                
                # Crear documento
                documento = Documento(
                    session_id=session_id,
                    nombre_archivo=doc_data.get('nombre_archivo', 'desconocido.pdf'),
                    fecha_procesamiento=fecha_procesamiento,
                    usuario_id=usuario.id,
                    estado='procesado',
                    tiempo_procesamiento=doc_data.get('tiempo_procesamiento'),
                    metodo_ocr=doc_data.get('metodo_ocr', 'hybrid'),
                    numero_escritura=doc_data.get('numero_escritura'),
                    fecha_escritura=fecha_escritura,
                    tipo_acto=doc_data.get('tipo_acto'),
                    otorgantes=doc_data.get('otorgantes'),
                    identificaciones=doc_data.get('identificaciones'),
                    cuantia=doc_data.get('cuantia'),
                    total_paginas=doc_data.get('total_paginas'),
                    confianza_promedio=doc_data.get('confianza_promedio'),
                    requiere_revision=doc_data.get('requiere_revision', False)
                )
                
                db.session.add(documento)
                
                # Crear registro de auditoría
                auditoria = Auditoria(
                    documento=documento,
                    usuario=usuario,
                    accion='migracion',
                    detalles={
                        'origen': 'JSON',
                        'archivo': json_file,
                        'fecha_migracion': datetime.utcnow().isoformat()
                    }
                )
                db.session.add(auditoria)
                
                migrados += 1
                
                # Commit cada 50 registros
                if migrados % 50 == 0:
                    db.session.commit()
                    print(f"✅ Migrados {migrados} documentos...")
                
            except Exception as e:
                errores += 1
                print(f"❌ Error migrando {session_id}: {str(e)}")
                db.session.rollback()
        
        # Commit final
        db.session.commit()
        
        print(f"\n{'='*50}")
        print(f"✅ Migración completada")
        print(f"📊 Documentos migrados: {migrados}")
        print(f"❌ Errores: {errores}")
        print(f"{'='*50}")
        
        # Renombrar archivo JSON como backup
        backup_file = f"{json_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(json_file, backup_file)
        print(f"💾 Backup creado: {backup_file}")


if __name__ == '__main__':
    migrar_datos()
