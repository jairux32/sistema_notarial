import io
import os
import zipfile
import pytest


def test_download_single_file(client, tmp_dirs):
    subdir = os.path.join(tmp_dirs['processed'], 'subdir')
    os.makedirs(subdir, exist_ok=True)
    filepath = os.path.join(subdir, 'test.pdf')
    with open(filepath, 'wb') as f:
        f.write(b'%PDF-1.4 test content')

    resp = client.get('/download/subdir/test.pdf')
    assert resp.status_code == 200
    assert resp.data == b'%PDF-1.4 test content'


def test_download_path_traversal_returns_403(client, tmp_dirs):
    resp = client.get('/download/../../etc/passwd')
    assert resp.status_code == 403


def test_download_nonexistent_returns_404(client, tmp_dirs):
    resp = client.get('/download/nonexistent/file.pdf')
    assert resp.status_code == 404


def test_download_zip_multiple_files(client, tmp_dirs):
    for name in ['path1.pdf', 'path2.pdf']:
        with open(os.path.join(tmp_dirs['processed'], name), 'wb') as f:
            f.write(b'%PDF-1.4 content of ' + name.encode())

    resp = client.post('/download_zip', json={'files': ['path1.pdf', 'path2.pdf']})
    assert resp.status_code == 200
    assert resp.content_type == 'application/zip'

    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = zf.namelist()
        assert 'path1.pdf' in names
        assert 'path2.pdf' in names
        assert zf.read('path1.pdf') == b'%PDF-1.4 content of path1.pdf'
        assert zf.read('path2.pdf') == b'%PDF-1.4 content of path2.pdf'


def test_download_zip_empty_list(client, tmp_dirs):
    resp = client.post('/download_zip', json={'files': []})
    assert resp.status_code == 400


def test_download_zip_skips_traversal(client, tmp_dirs):
    with open(os.path.join(tmp_dirs['processed'], 'valid.pdf'), 'wb') as f:
        f.write(b'%PDF-1.4 valid')

    resp = client.post('/download_zip', json={'files': ['../../etc/passwd', 'valid.pdf']})
    assert resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        assert 'valid.pdf' in zf.namelist()
        assert len(zf.namelist()) == 1


def test_download_zip_no_valid_files(client, tmp_dirs):
    resp = client.post('/download_zip', json={'files': ['nonexistent.pdf']})
    assert resp.status_code == 400
