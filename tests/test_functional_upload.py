import io
import os

import pytest
import fitz


def _upload_pdf(client, content, filename, form_data=None):
    if form_data is None:
        form_data = {
            'año': '2025',
            'mes': 'ENERO',
            'tipo_libro': 'P',
            'numero_libro': '1',
        }
    return client.post(
        '/upload',
        data={
            **form_data,
            'pdf_file': (io.BytesIO(content), filename),
        },
        content_type='multipart/form-data',
    )


def _login_user(client, app_instance, username):
    with client.session_transaction() as sess:
        sess['_user_id'] = username
        sess['_fresh'] = True
    with app_instance.app_context():
        from models import Usuario
        assert Usuario.query.filter_by(username=username).first() is not None


def test_upload_missing_file(client):
    resp = client.post('/upload', data={}, content_type='multipart/form-data')
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'No se seleccionó archivo'


def test_upload_empty_filename(client):
    resp = client.post(
        '/upload',
        data={'pdf_file': (io.BytesIO(b'test'), '')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'Nombre de archivo vacío'


def test_upload_non_pdf_extension(client):
    resp = _upload_pdf(client, b'test content', 'document.txt')
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'Solo se permiten archivos PDF'


def test_upload_bad_magic_bytes(client):
    resp = _upload_pdf(client, b'NOTPDF\x00\x00\x00', 'fake.pdf')
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'El archivo no es un PDF válido'


def test_upload_no_codes_found(client, sample_blank_pdf):
    with open(sample_blank_pdf, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'blank.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('success') is not True
    assert 'error' in data or 'No se encontraron' in str(data)


def test_upload_success_with_codes(client, sample_pdf_with_codes):
    pdf_path, codes = sample_pdf_with_codes
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'test_input.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['archivos_generados'] == 3
    assert data['session_id']
    assert isinstance(data['validacion'], dict)
    assert isinstance(data['hashes'], dict)


def test_upload_persists_to_db(client, sample_pdf_with_codes, app_instance, test_user):
    from models import Documento
    username, _ = test_user
    _login_user(client, app_instance, username)
    pdf_path, _ = sample_pdf_with_codes
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'test_input.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    with app_instance.app_context():
        doc = Documento.query.filter_by(session_id=data['session_id']).first()
        assert doc is not None
        assert doc.nombre_archivo == 'test_input.pdf'
        assert doc.estado == 'procesado'


def test_upload_persists_auditoria(client, sample_pdf_with_codes, app_instance, test_user):
    from models import Documento, Auditoria
    username, _ = test_user
    _login_user(client, app_instance, username)
    pdf_path, _ = sample_pdf_with_codes
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'test_input.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    with app_instance.app_context():
        doc = Documento.query.filter_by(session_id=data['session_id']).first()
        assert doc is not None
        audit = Auditoria.query.filter_by(documento_id=doc.id).first()
        assert audit is not None
        assert audit.accion == 'procesamiento'


def test_upload_creates_output_files(client, sample_pdf_with_codes, tmp_dirs):
    pdf_path, _ = sample_pdf_with_codes
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'test_input.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    processed_dir = tmp_dirs['processed']
    pdf_files = []
    for dirpath, _, filenames in os.walk(processed_dir):
        pdf_files.extend(f for f in filenames if f.endswith('.pdf'))
    assert len(pdf_files) >= 4


def test_upload_generates_report(client, sample_pdf_with_codes):
    pdf_path, _ = sample_pdf_with_codes
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = _upload_pdf(client, content, 'test_input.pdf')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    reporte_path = data.get('reporte_path')
    assert reporte_path is not None
    assert os.path.isfile(reporte_path)
    doc = fitz.open(reporte_path)
    assert doc.page_count > 0
    doc.close()
