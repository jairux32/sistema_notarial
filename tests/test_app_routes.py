"""Tests for Flask routes."""
import io
import json
import pytest
from unittest.mock import patch, MagicMock


class TestLoginRoute:
    def test_root_redirects_to_login(self, client):
        resp = client.get('/')
        assert resp.status_code in (301, 302)
        assert 'login' in resp.headers.get('Location', '')

    def test_login_page_renders(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200


class TestSecurityHeaders:
    def test_x_frame_options(self, client):
        resp = client.get('/login')
        assert resp.headers.get('X-Frame-Options') == 'DENY'

    def test_x_content_type_options(self, client):
        resp = client.get('/login')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_xss_protection(self, client):
        resp = client.get('/login')
        assert resp.headers.get('X-XSS-Protection') == '1; mode=block'


class TestAPILogin:
    def test_api_login_returns_token(self, client, app_instance):
        from models import db, Usuario
        with app_instance.app_context():
            u = Usuario(username='apitest', nombre_completo='API Test')
            u.set_password('pass123')
            db.session.add(u)
            db.session.commit()

        resp = client.post('/api/login', json={
            'username': 'apitest',
            'password': 'pass123',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'token' in data
        assert data['user']['username'] == 'apitest'

    def test_api_login_wrong_password(self, client, app_instance):
        from models import db, Usuario
        with app_instance.app_context():
            u = Usuario(username='apitest2', nombre_completo='API Test 2')
            u.set_password('pass123')
            db.session.add(u)
            db.session.commit()

        resp = client.post('/api/login', json={
            'username': 'apitest2',
            'password': 'wrong',
        })
        assert resp.status_code in (401, 403)


class TestProtectedEndpointsRequireToken:
    def test_upload_without_token(self, client):
        resp = client.post('/api/upload_scan')
        assert resp.status_code == 401

    def test_upload_with_invalid_token(self, client):
        resp = client.post('/api/upload_scan', headers={
            'X-Auth-Token': 'token_invalido_aaaa'
        })
        assert resp.status_code == 401


class TestDocumentosRoute:
    def test_with_login_disabled_serves_page(self, client):
        """LOGIN_DISABLED=True lets anonymous users through; the route
        reads the filesystem and renders a template (no current_user access)."""
        resp = client.get('/documentos')
        assert resp.status_code == 200
