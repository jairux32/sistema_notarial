"""Tests for SQLAlchemy models."""
import pytest
from datetime import datetime, date
from decimal import Decimal

from models import db, Usuario, Documento, Auditoria


class TestUsuario:
    def test_create_and_hash(self, app_instance):
        with app_instance.app_context():
            u = Usuario(username='testadmin', nombre_completo='Test Admin', rol='admin')
            u.set_password('secret123')
            db.session.add(u)
            db.session.commit()

            loaded = Usuario.query.filter_by(username='testadmin').first()
            assert loaded is not None
            assert loaded.check_password('secret123') is True
            assert loaded.check_password('wrong') is False

    def test_to_dict(self, app_instance):
        with app_instance.app_context():
            u = Usuario(username='u1', nombre_completo='User One', rol='usuario')
            u.set_password('pw')
            db.session.add(u)
            db.session.commit()

            d = u.to_dict()
            assert d['username'] == 'u1'
            assert d['rol'] == 'usuario'
            assert 'password_hash' not in d

    def test_unique_username(self, app_instance):
        with app_instance.app_context():
            u1 = Usuario(username='dup', nombre_completo='A')
            u1.set_password('pw')
            db.session.add(u1)
            db.session.commit()

            u2 = Usuario(username='dup', nombre_completo='B')
            u2.set_password('pw')
            db.session.add(u2)
            with pytest.raises(Exception):
                db.session.commit()


class TestDocumento:
    def test_create_documento(self, app_instance):
        with app_instance.app_context():
            doc = Documento(
                session_id='test-session-001',
                nombre_archivo='test.pdf',
                estado='procesado',
                total_paginas=10,
                mes='ENERO',
                numero_libro=1,
            )
            db.session.add(doc)
            db.session.commit()

            loaded = Documento.query.filter_by(session_id='test-session-001').first()
            assert loaded.nombre_archivo == 'test.pdf'
            assert loaded.mes == 'ENERO'
            assert loaded.numero_libro == 1
            assert loaded.total_paginas == 10

    def test_to_dict(self, app_instance):
        with app_instance.app_context():
            doc = Documento(session_id='s2', nombre_archivo='b.pdf')
            db.session.add(doc)
            db.session.commit()
            d = doc.to_dict()
            assert d['session_id'] == 's2'
            assert d['nombre_archivo'] == 'b.pdf'


class TestAuditoria:
    def test_create_auditoria(self, app_instance):
        with app_instance.app_context():
            doc = Documento(session_id='s3', nombre_archivo='c.pdf')
            db.session.add(doc)
            db.session.commit()

            aud = Auditoria(
                documento_id=doc.id,
                accion='procesamiento',
                detalles={'codigos': ['20251101007P00001']},
            )
            db.session.add(aud)
            db.session.commit()

            loaded = Auditoria.query.filter_by(accion='procesamiento').first()
            assert loaded.detalles['codigos'] == ['20251101007P00001']

    def test_to_dict(self, app_instance):
        with app_instance.app_context():
            aud = Auditoria(accion='test_action')
            db.session.add(aud)
            db.session.commit()
            d = aud.to_dict()
            assert d['accion'] == 'test_action'
