"""
Historial de Escaneos
Registra y gestiona el historial de documentos escaneados
"""

import json
import os
from datetime import datetime

class ScanHistory:
    """Gestor de historial de escaneos"""
    
    def __init__(self, history_file='scan_history.json'):
        self.history_file = history_file
        self.history = self.load_history()
    
    def load_history(self):
        """Carga el historial desde archivo"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_history(self):
        """Guarda el historial en archivo"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def add_scan(self, filename, scan_type='simple', pages=1, size_mb=0, 
                 compression_level='none', ocr_codes=0, **kwargs):
        """Agrega un escaneo al historial"""
        entry = {
            'id': len(self.history) + 1,
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'scan_type': scan_type,  # simple, multiple, ocr
            'pages': pages,
            'size_mb': round(size_mb, 2),
            'compression_level': compression_level,
            'ocr_codes': ocr_codes,
            **kwargs
        }
        
        self.history.append(entry)
        self.save_history()
        
        return entry['id']
    
    def get_recent(self, limit=10):
        """Obtiene los escaneos más recientes"""
        return sorted(self.history, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def get_stats(self):
        """Obtiene estadísticas del historial"""
        if not self.history:
            return {
                'total_scans': 0,
                'total_pages': 0,
                'total_size_mb': 0,
                'avg_pages_per_scan': 0,
                'avg_size_mb': 0
            }
        
        total_scans = len(self.history)
        total_pages = sum(s['pages'] for s in self.history)
        total_size = sum(s['size_mb'] for s in self.history)
        
        return {
            'total_scans': total_scans,
            'total_pages': total_pages,
            'total_size_mb': round(total_size, 2),
            'avg_pages_per_scan': round(total_pages / total_scans, 1),
            'avg_size_mb': round(total_size / total_scans, 2),
            'scan_types': self._count_by_type(),
            'compression_usage': self._count_by_compression()
        }
    
    def _count_by_type(self):
        """Cuenta escaneos por tipo"""
        types = {}
        for scan in self.history:
            scan_type = scan.get('scan_type', 'simple')
            types[scan_type] = types.get(scan_type, 0) + 1
        return types
    
    def _count_by_compression(self):
        """Cuenta escaneos por nivel de compresión"""
        compression = {}
        for scan in self.history:
            level = scan.get('compression_level', 'none')
            compression[level] = compression.get(level, 0) + 1
        return compression

# Instancia global
scan_history = ScanHistory()
