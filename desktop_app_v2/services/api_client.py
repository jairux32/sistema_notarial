"""API client for Flask backend with offline queue"""
from __future__ import annotations
from typing import Tuple, Optional, Any
import requests
import json
import os
import uuid
from datetime import datetime


class APIClient:
    def __init__(self, base_url: str = 'http://localhost:5000'):
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.user = None
        self.offline_queue_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'offline_queue.json'
        )
        self._load_offline_queue()

    def _load_offline_queue(self):
        if os.path.exists(self.offline_queue_path):
            try:
                with open(self.offline_queue_path, 'r') as f:
                    self.offline_queue = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.offline_queue = []
        else:
            self.offline_queue = []

    def _save_offline_queue(self):
        import tempfile
        dir_name = os.path.dirname(self.offline_queue_path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self.offline_queue, f, indent=2)
            os.replace(tmp_path, self.offline_queue_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def login(self, username, password):
        try:
            resp = requests.post(
                f'{self.base_url}/api/login',
                json={'username': username, 'password': password},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    self.token = data.get('token')
                    self.user = data.get('user')
                    return True, self.user, None
                return False, None, data.get('error', 'Error desconocido')
            return False, None, f'Error HTTP {resp.status_code}'
        except requests.ConnectionError:
            return False, None, 'No se pudo conectar al servidor'
        except requests.Timeout:
            return False, None, 'Tiempo de espera agotado'
        except Exception as e:
            return False, None, str(e)

    def is_server_available(self):
        try:
            resp = requests.get(f'{self.base_url}/api/login', timeout=3)
            return resp.status_code in (200, 405, 401)
        except Exception:
            return False

    def upload_scan(self, pdf_path, username, ano, mes, tipo_libro, numero_libro):
        try:
            with open(pdf_path, 'rb') as f:
                files = {'pdf_file': (os.path.basename(pdf_path), f, 'application/pdf')}
                data = {
                    'username': username,
                    'ano': ano,
                    'mes': mes,
                    'tipo_libro': tipo_libro,
                    'numero_libro': str(numero_libro)
                }
                resp = requests.post(
                    f'{self.base_url}/api/upload_scan',
                    files=files,
                    data=data,
                    timeout=300
                )
            if resp.status_code == 200:
                return True, resp.json(), None
            return False, None, f'Error HTTP {resp.status_code}'
        except requests.ConnectionError:
            self._enqueue_offline(pdf_path, username, ano, mes, tipo_libro, numero_libro)
            return False, None, 'Servidor no disponible. Guardado en cola offline.'
        except Exception as e:
            return False, None, str(e)

    MAX_RETRIES = 3

    def _enqueue_offline(self, pdf_path, username, ano, mes, tipo_libro, numero_libro):
        entry = {
            'id': str(uuid.uuid4()),
            'pdf_path': pdf_path,
            'username': username,
            'ano': ano,
            'mes': mes,
            'tipo_libro': tipo_libro,
            'numero_libro': numero_libro,
            'created_at': datetime.now().isoformat(),
            'status': 'pending',
            'retries': 0
        }
        self.offline_queue.append(entry)
        self._save_offline_queue()

    def sync_offline_queue(self):
        if not self.offline_queue:
            return 0, 0

        synced = 0
        failed = 0
        remaining = []

        for entry in self.offline_queue:
            if entry['status'] != 'pending':
                continue
            if not os.path.exists(entry['pdf_path']):
                failed += 1
                continue

            success, result, error = self.upload_scan(
                entry['pdf_path'], entry['username'],
                entry['ano'], entry['mes'],
                entry['tipo_libro'], entry['numero_libro']
            )
            if success:
                synced += 1
            else:
                entry['retries'] = entry.get('retries', 0) + 1
                if entry['retries'] >= self.MAX_RETRIES:
                    entry['status'] = 'failed'
                    failed += 1
                else:
                    remaining.append(entry)
                    failed += 1

        self.offline_queue = remaining
        self._save_offline_queue()
        return synced, failed

    def get_offline_queue(self):
        return [e for e in self.offline_queue if e['status'] == 'pending']
