import json
from datetime import datetime
import os

class Auditoria:
    LOG_FILE = "auditoria_notarial.json"
    
    @staticmethod
    def registrar_acceso(usuario):
        """Registra acceso de usuario"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'usuario': usuario,
            'accion': 'LOGIN',
            'ip': '127.0.0.1'  # En producción, obtener IP real
        }
        Auditoria._escribir_log(log_entry)
    
    @staticmethod
    def registrar_procesamiento(usuario, archivo, año, tipo, resultado):
        """Registra procesamiento de archivo"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'usuario': usuario,
            'accion': 'PROCESAMIENTO',
            'archivo': archivo,
            'año': año,
            'tipo': tipo,
            'resultado': resultado.get('success', False),
            'archivos_generados': resultado.get('archivos_generados', 0),
            'codigos_encontrados': len(resultado.get('codigos_encontrados', [])),
            'errores': resultado.get('error', None)
        }
        Auditoria._escribir_log(log_entry)
    
    @staticmethod
    def _escribir_log(entry):
        """Escribe entrada en el archivo de log"""
        logs = []
        
        # Cargar logs existentes
        if os.path.exists(Auditoria.LOG_FILE):
            with open(Auditoria.LOG_FILE, 'r') as f:
                try:
                    logs = json.load(f)
                except:
                    logs = []
        
        # Agregar nueva entrada
        logs.append(entry)
        
        # Guardar (mantener últimos 1000 registros)
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        with open(Auditoria.LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2)