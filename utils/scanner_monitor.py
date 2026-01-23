import os
import glob
import shutil
from datetime import datetime

class ScannerMonitor:
    """Monitor de carpeta para detectar archivos escaneados nuevos"""
    
    def __init__(self, watch_dir='scanned/'):
        self.watch_dir = watch_dir
        self.processed_files = set()
        
        # Crear directorio si no existe
        os.makedirs(watch_dir, exist_ok=True)
    
    def detectar_archivos_nuevos(self):
        """Detecta archivos PDF nuevos en la carpeta de escaneo"""
        # Buscar todos los PDFs en la carpeta
        archivos_actuales = set(glob.glob(os.path.join(self.watch_dir, '*.pdf')))
        
        # Filtrar solo los nuevos (no procesados)
        nuevos = archivos_actuales - self.processed_files
        
        # Ordenar por fecha de modificación (más antiguos primero)
        nuevos_ordenados = sorted(nuevos, key=lambda x: os.path.getmtime(x))
        
        return nuevos_ordenados
    
    def marcar_como_procesado(self, archivo):
        """Marca un archivo como procesado"""
        self.processed_files.add(archivo)
    
    def archivar_archivo(self, archivo, archive_dir='scanned_archive/'):
        """Mueve archivo procesado a carpeta de archivo"""
        # Crear directorio de archivo con fecha
        fecha = datetime.now().strftime('%Y-%m-%d')
        destino_dir = os.path.join(archive_dir, fecha)
        os.makedirs(destino_dir, exist_ok=True)
        
        # Mover archivo
        nombre_archivo = os.path.basename(archivo)
        destino = os.path.join(destino_dir, nombre_archivo)
        
        # Si ya existe, agregar timestamp
        if os.path.exists(destino):
            timestamp = datetime.now().strftime('%H%M%S')
            nombre_base, ext = os.path.splitext(nombre_archivo)
            nombre_archivo = f"{nombre_base}_{timestamp}{ext}"
            destino = os.path.join(destino_dir, nombre_archivo)
        
        shutil.move(archivo, destino)
        print(f"📦 Archivo archivado: {destino}")
        
        return destino
    
    def limpiar_procesados(self):
        """Limpia la lista de archivos procesados (útil para reiniciar)"""
        self.processed_files.clear()
    
    def obtener_info_archivo(self, archivo):
        """Obtiene información de un archivo"""
        stat = os.stat(archivo)
        return {
            'nombre': os.path.basename(archivo),
            'ruta': archivo,
            'tamaño': stat.st_size,
            'tamaño_mb': round(stat.st_size / (1024 * 1024), 2),
            'fecha_modificacion': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
