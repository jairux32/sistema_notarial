import os
import sys
import importlib.util
import tempfile
import shutil
import pytest
import fitz

# Ensure project root is on sys.path
_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Set env vars BEFORE importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-secret-key'

# Pre-import the Flask app using importlib to avoid pytest's name collision
_app_spec = importlib.util.spec_from_file_location("_flask_app", os.path.join(_root, "app.py"))
_app_mod = importlib.util.module_from_spec(_app_spec)
_app_spec.loader.exec_module(_app_mod)
_flask_app = _app_mod.app
procesar_pdf = _app_mod.procesar_pdf
procesamiento_cache = _app_mod.procesamiento_cache


# ---------------------------------------------------------------------------
# Synthetic PDF helpers
# ---------------------------------------------------------------------------

def make_notarial_pdf(path, codes, pages_per_code=1):
    """Create a PDF with notarial codes embedded as text on each page.

    Each code gets `pages_per_code` pages with the code written in the
    upper zone (y=50) so the text-layer extraction finds it without Tesseract.
    """
    doc = fitz.open()
    for code in codes:
        for _ in range(pages_per_code):
            page = doc.new_page(width=595, height=842)  # A4
            # Write code in the upper zone (top 150px) so it's found by
            # the text-extraction path in _buscar_en_pdf
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
            page.insert_text(fitz.Point(50, 120), f"Documento notarial {code}", fontsize=10, fontname="helv")
    doc.save(path)
    doc.close()


def make_blank_pdf(path, num_pages=3):
    """Create a PDF with blank pages (no text)."""
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page()
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app_instance():
    """Create a Flask test app with SQLite in-memory DB."""
    _flask_app.config['TESTING'] = True
    _flask_app.config['WTF_CSRF_ENABLED'] = False
    _flask_app.config['LOGIN_DISABLED'] = True

    with _flask_app.app_context():
        from models import db
        db.create_all()
        yield _flask_app
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture
def db_session(app_instance):
    from models import db
    return db


@pytest.fixture
def tmp_dirs(app_instance):
    """Create temporary upload/processed dirs and patch app config."""
    upload_dir = tempfile.mkdtemp()
    processed_dir = tempfile.mkdtemp()
    app_instance.config['UPLOAD_FOLDER'] = upload_dir
    app_instance.config['PROCESSED_FOLDER'] = processed_dir
    yield {'upload': upload_dir, 'processed': processed_dir}
    shutil.rmtree(upload_dir, ignore_errors=True)
    shutil.rmtree(processed_dir, ignore_errors=True)


@pytest.fixture
def sample_pdf_with_codes(tmp_dirs):
    """Create a synthetic PDF with 3 notarial codes and return its path."""
    codes = [
        '20251101007P00001',
        '20251101007P00002',
        '20251101007P00003',
    ]
    pdf_path = os.path.join(tmp_dirs['upload'], 'test_input.pdf')
    make_notarial_pdf(pdf_path, codes)
    return pdf_path, codes


@pytest.fixture
def sample_blank_pdf(tmp_dirs):
    """Create a blank PDF (no codes) and return its path."""
    pdf_path = os.path.join(tmp_dirs['upload'], 'blank_input.pdf')
    make_blank_pdf(pdf_path, 3)
    return pdf_path


@pytest.fixture
def test_user(app_instance, db_session):
    """Create a test user in the DB and return (username, password)."""
    from models import Usuario
    with app_instance.app_context():
        u = Usuario(username='testuser', nombre_completo='Test User', rol='usuario')
        u.set_password('testpass123')
        db_session.session.add(u)
        db_session.session.commit()
        return 'testuser', 'testpass123'


@pytest.fixture
def api_token(client, test_user):
    """Login via API and return a valid token."""
    username, password = test_user
    resp = client.post('/api/login', json={'username': username, 'password': password})
    data = resp.get_json()
    return data['token']
