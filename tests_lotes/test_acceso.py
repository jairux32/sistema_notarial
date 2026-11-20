"""Clave de acceso de la pantalla: sale de un archivo, y sin clave no se abre a la red."""
import base64

import pytest

from lotes import web
from lotes.espacio import Espacio


@pytest.fixture(autouse=True)
def _sin_entorno(monkeypatch):
    for v in ("SEPARADOR_USUARIO", "SEPARADOR_CLAVE", "SEPARADOR_CLAVE_ARCHIVO"):
        monkeypatch.delenv(v, raising=False)


def test_la_clave_se_lee_del_archivo_y_se_recorta(monkeypatch, tmp_path):
    f = tmp_path / "clave"
    f.write_text("  secreta uno \n", encoding="utf-8")
    monkeypatch.setenv("SEPARADOR_USUARIO", "notaria")
    monkeypatch.setenv("SEPARADOR_CLAVE_ARCHIVO", str(f))
    assert web.credenciales() == ("notaria", "secreta uno")


def test_la_clave_del_entorno_manda_sobre_el_archivo(monkeypatch, tmp_path):
    f = tmp_path / "clave"
    f.write_text("del archivo", encoding="utf-8")
    monkeypatch.setenv("SEPARADOR_USUARIO", "u")
    monkeypatch.setenv("SEPARADOR_CLAVE", "del entorno")
    monkeypatch.setenv("SEPARADOR_CLAVE_ARCHIVO", str(f))
    assert web.credenciales() == ("u", "del entorno")


def test_archivo_inexistente_o_vacio_es_sin_clave(monkeypatch, tmp_path):
    monkeypatch.setenv("SEPARADOR_USUARIO", "u")
    monkeypatch.setenv("SEPARADOR_CLAVE_ARCHIVO", str(tmp_path / "no_existe"))
    assert web.credenciales() == ("u", None)
    (tmp_path / "vacia").write_text("\n", encoding="utf-8")
    monkeypatch.setenv("SEPARADOR_CLAVE_ARCHIVO", str(tmp_path / "vacia"))
    assert web.credenciales() == ("u", None)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.74", "::"])
def test_sin_clave_no_se_abre_a_la_red(host):
    with pytest.raises(SystemExit):
        web.comprobar_acceso(host, None, None)
    with pytest.raises(SystemExit):
        web.comprobar_acceso(host, "u", None)
    with pytest.raises(SystemExit):
        web.comprobar_acceso(host, None, "c")


def test_con_clave_se_puede_abrir_a_la_red_y_en_local_no_hace_falta():
    web.comprobar_acceso("0.0.0.0", "u", "c")
    for host in ("127.0.0.1", "localhost", "::1"):
        web.comprobar_acceso(host, None, None)


def test_la_pantalla_pide_la_clave_del_archivo(monkeypatch, tmp_path):
    f = tmp_path / "clave"
    f.write_text("abc123\n", encoding="utf-8")
    monkeypatch.setenv("SEPARADOR_USUARIO", "notaria")
    monkeypatch.setenv("SEPARADOR_CLAVE_ARCHIVO", str(f))
    cl = web.crear_app(Espacio(tmp_path / "d", tmp_path / "a")).test_client()
    assert cl.get("/").status_code == 401

    def cab(u, c):
        return {"Authorization": "Basic " + base64.b64encode(f"{u}:{c}".encode()).decode()}

    assert cl.get("/", headers=cab("notaria", "mala")).status_code == 401
    assert cl.get("/", headers=cab("otro", "abc123")).status_code == 401
    assert cl.get("/", headers=cab("notaria", "abc123")).status_code == 200
