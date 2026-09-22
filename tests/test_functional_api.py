import io
import pytest


class TestApiLogin:

    def test_api_login_success(self, client, test_user):
        username, password = test_user
        resp = client.post('/api/login', json={
            'username': username,
            'password': password
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert 'token' in data
        assert data['user']['username'] == 'testuser'

    def test_api_login_wrong_password(self, client, test_user):
        username, _ = test_user
        resp = client.post('/api/login', json={
            'username': username,
            'password': 'wrongpass'
        })
        assert resp.status_code == 401

    def test_api_login_missing_credentials(self, client):
        resp = client.post('/api/login', json={})
        assert resp.status_code == 400


class TestApiUploadValidation:

    def test_api_upload_without_token(self, client, tmp_dirs, sample_pdf_with_codes):
        pdf_path, _ = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                data={
                    'pdf_file': (f, 'test.pdf'),
                    'año': '2025',
                    'mes': 'ENERO',
                    'tipo_libro': 'P',
                    'numero_libro': '1',
                    'username': 'testuser',
                },
                content_type='multipart/form-data')
        assert resp.status_code == 401

    def test_api_upload_with_invalid_token(self, client, tmp_dirs, sample_pdf_with_codes):
        pdf_path, _ = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                headers={'X-Auth-Token': 'invalid_token_xyz'},
                data={
                    'pdf_file': (f, 'test.pdf'),
                    'año': '2025',
                    'mes': 'ENERO',
                    'tipo_libro': 'P',
                    'numero_libro': '1',
                    'username': 'testuser',
                },
                content_type='multipart/form-data')
        assert resp.status_code == 401

    def test_api_upload_username_mismatch(self, client, api_token, tmp_dirs, sample_pdf_with_codes):
        pdf_path, _ = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                headers={'X-Auth-Token': api_token},
                data={
                    'pdf_file': (f, 'test.pdf'),
                    'año': '2025',
                    'mes': 'ENERO',
                    'tipo_libro': 'P',
                    'numero_libro': '1',
                    'username': 'other_user',
                },
                content_type='multipart/form-data')
        data = resp.get_json()
        assert resp.status_code == 403
        assert 'Usuario no coincide' in data['error']

    def test_api_upload_missing_metadata(self, client, api_token, tmp_dirs, sample_pdf_with_codes):
        pdf_path, _ = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                headers={'X-Auth-Token': api_token},
                data={
                    'pdf_file': (f, 'test.pdf'),
                    'mes': 'ENERO',
                    'numero_libro': '1',
                    'username': 'testuser',
                },
                content_type='multipart/form-data')
        data = resp.get_json()
        assert resp.status_code == 400
        assert 'Faltan metadatos' in data['error']

    def test_api_upload_no_file(self, client, api_token, tmp_dirs):
        resp = client.post('/api/upload_scan',
            headers={'X-Auth-Token': api_token},
            data={
                'año': '2025',
                'mes': 'ENERO',
                'tipo_libro': 'P',
                'numero_libro': '1',
                'username': 'testuser',
            },
            content_type='multipart/form-data')
        assert resp.status_code == 400


class TestApiUploadSuccess:

    def test_api_upload_success(self, client, api_token, tmp_dirs, sample_pdf_with_codes):
        pdf_path, _ = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                headers={'X-Auth-Token': api_token},
                data={
                    'pdf_file': (f, 'codigo_notarial.pdf'),
                    'año': '2025',
                    'mes': 'ENERO',
                    'tipo_libro': 'P',
                    'numero_libro': '1',
                    'username': 'testuser',
                },
                content_type='multipart/form-data')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data.get('success') is True
        assert 'archivos_generados' in data

    def test_api_upload_persists_to_db(self, client, api_token, tmp_dirs, sample_pdf_with_codes, app_instance, db_session):
        pdf_path, codes = sample_pdf_with_codes
        with open(pdf_path, 'rb') as f:
            resp = client.post('/api/upload_scan',
                headers={'X-Auth-Token': api_token},
                data={
                    'pdf_file': (f, 'codigo_notarial.pdf'),
                    'año': '2025',
                    'mes': 'ENERO',
                    'tipo_libro': 'P',
                    'numero_libro': '1',
                    'username': 'testuser',
                },
                content_type='multipart/form-data')
        assert resp.status_code == 200
        from models import Documento
        docs = Documento.query.all()
        assert len(docs) >= 1
