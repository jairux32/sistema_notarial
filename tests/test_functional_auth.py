from models import Auditoria, Usuario


def test_login_success_redirects(client, test_user):
    username, password = test_user
    resp = client.post(
        '/login',
        data={'username': username, 'password': password},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/dashboard' in resp.headers['Location']


def test_login_wrong_credentials(client, test_user):
    resp = client.post(
        '/login',
        data={'username': 'testuser', 'password': 'wrongpassword'},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert 'incorrectos' in resp.data.decode()


def test_login_creates_auditoria(client, test_user, app_instance):
    username, password = test_user
    resp = client.post(
        '/login',
        data={'username': username, 'password': password},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    with app_instance.app_context():
        record = Auditoria.query.filter_by(accion='login').first()
        assert record is not None
        assert record.usuario.username == username


def test_login_updates_ultimo_acceso(client, test_user, app_instance):
    username, password = test_user
    resp = client.post(
        '/login',
        data={'username': username, 'password': password},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    with app_instance.app_context():
        usuario = Usuario.query.filter_by(username=username).first()
        assert usuario.ultimo_acceso is not None


def test_logout_redirects(client, test_user):
    username, password = test_user
    client.post(
        '/login',
        data={'username': username, 'password': password},
        follow_redirects=False,
    )
    resp = client.get('/logout', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']
