import io
import json
import os

import pytest


def _upload_and_get_session_id(client, tmp_dirs, codes):
    from tests.conftest import make_notarial_pdf
    pdf_path = os.path.join(tmp_dirs['upload'], 'input.pdf')
    make_notarial_pdf(pdf_path, codes)
    with open(pdf_path, 'rb') as f:
        content = f.read()
    resp = client.post(
        '/upload',
        data={
            'año': '2025',
            'mes': 'ENERO',
            'tipo_libro': 'P',
            'numero_libro': '1',
            'pdf_file': (io.BytesIO(content), 'input.pdf'),
        },
        content_type='multipart/form-data',
    )
    data = resp.get_json()
    assert data.get('success'), f"Upload failed: {data}"
    return data['session_id']


def _add_manual_code(client, session_id, codigo, pagina_inicio=0):
    return client.post(
        '/agregar_codigo_manual',
        data=json.dumps({
            'session_id': session_id,
            'codigo': codigo,
            'pagina_inicio': pagina_inicio,
        }),
        content_type='application/json',
    )


def test_add_manual_code_success(client, tmp_dirs):
    codes = ['20251101007P00001', '20251101007P00002']
    session_id = _upload_and_get_session_id(client, tmp_dirs, codes)
    resp = _add_manual_code(client, session_id, '20251101007P00003', 0)
    data = resp.get_json()
    assert data['success'] is True
    assert data['archivos_generados'] == 3


def test_add_duplicate_code_returns_error(client, tmp_dirs):
    codes = ['20251101007P00001']
    session_id = _upload_and_get_session_id(client, tmp_dirs, codes)
    resp = _add_manual_code(client, session_id, '20251101007P00001', 0)
    assert resp.status_code == 400
    assert 'ya existe' in resp.get_json()['error']


def test_add_code_invalid_session(client):
    resp = _add_manual_code(client, 'nonexistent-id', '20251101007P00001', 0)
    assert resp.status_code == 400
    assert 'Sesión no encontrada' in resp.get_json()['error']


def test_add_code_missing_fields(client, tmp_dirs):
    codes = ['20251101007P00001']
    session_id = _upload_and_get_session_id(client, tmp_dirs, codes)
    resp = client.post(
        '/agregar_codigo_manual',
        data=json.dumps({'session_id': session_id, 'codigo': '', 'pagina_inicio': 0}),
        content_type='application/json',
    )
    assert resp.status_code == 400


def _count_pdfs_recursive(directory):
    count = 0
    for _, _, files in os.walk(directory):
        count += sum(1 for f in files if f.endswith('.pdf'))
    return count


def test_add_code_creates_new_file(client, tmp_dirs):
    codes = ['20251101007P00001']
    session_id = _upload_and_get_session_id(client, tmp_dirs, codes)
    processed_dir = tmp_dirs['processed']
    count_before = _count_pdfs_recursive(processed_dir)
    resp = _add_manual_code(client, session_id, '20251101007P00002', 0)
    assert resp.get_json()['success'] is True
    count_after = _count_pdfs_recursive(processed_dir)
    assert count_after > count_before
