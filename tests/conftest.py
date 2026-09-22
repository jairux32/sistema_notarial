import os
import sys
import importlib.util
import pytest

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
