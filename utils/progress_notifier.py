"""
Sistema de Notificaciones de Progreso
Muestra el progreso de operaciones largas en tiempo real
"""

import time
import threading
from datetime import datetime

class ProgressNotifier:
    """Gestor de notificaciones de progreso"""
    
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
    
    def create_task(self, task_id, total_steps, description="Procesando"):
        """Crea una nueva tarea de progreso"""
        with self.lock:
            self.tasks[task_id] = {
                'total_steps': total_steps,
                'current_step': 0,
                'description': description,
                'status': 'running',
                'start_time': datetime.now(),
                'messages': []
            }
    
    def update_progress(self, task_id, step, message=""):
        """Actualiza el progreso de una tarea"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['current_step'] = step
                if message:
                    self.tasks[task_id]['messages'].append({
                        'time': datetime.now(),
                        'message': message
                    })
    
    def complete_task(self, task_id, success=True, message=""):
        """Marca una tarea como completada"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'completed' if success else 'failed'
                self.tasks[task_id]['end_time'] = datetime.now()
                if message:
                    self.tasks[task_id]['messages'].append({
                        'time': datetime.now(),
                        'message': message
                    })
    
    def get_progress(self, task_id):
        """Obtiene el progreso de una tarea"""
        with self.lock:
            if task_id not in self.tasks:
                return None
            
            task = self.tasks[task_id]
            percent = (task['current_step'] / task['total_steps'] * 100) if task['total_steps'] > 0 else 0
            
            return {
                'task_id': task_id,
                'description': task['description'],
                'current_step': task['current_step'],
                'total_steps': task['total_steps'],
                'percent': round(percent, 1),
                'status': task['status'],
                'messages': task['messages'][-5:],  # Últimos 5 mensajes
                'elapsed_time': (datetime.now() - task['start_time']).total_seconds()
            }
    
    def cleanup_old_tasks(self, max_age_seconds=3600):
        """Limpia tareas antiguas"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for task_id, task in self.tasks.items():
                if 'end_time' in task:
                    age = (now - task['end_time']).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.tasks[task_id]

# Instancia global
progress_notifier = ProgressNotifier()
