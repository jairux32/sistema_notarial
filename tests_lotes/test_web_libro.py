"""Pantalla web con libro abierto: la tanda escaneada se divide y se guarda sola; lo dudoso queda por revisar."""
import io
import time

import pytest
from PIL import Image

from lotes import libro, web
from lotes.espacio import Espacio
from lotes.kodak import ErrorEscaner

from .sintetico import cod, png_barras

A = 2099


def _hoja(sec=None, ajeno=None):
    hoja = Image.new("L", (2480, 3508), 255)
    for i, c in enumerate([cod(A, "P", sec)] if sec else [] + ([ajeno] if ajeno else [])):
        barras = Image.open(io.BytesIO(png_barras(c))).convert("L").resize((900, 300))
        hoja.paste(barras, (1400, 150 + i * 400))
    b = io.BytesIO()
    hoja.save(b, "JPEG", quality=85)
    return b.getvalue()


class Escaner:
    def __init__(self, tandas):
        self.tandas = list(tandas)
        self.quedaron_hojas = False
        self.imagenes_crudas = 0

    def escanear(self, caras="Simplex", avance=None, **kw):
        t = self.tandas.pop(0)
        if isinstance(t, str):
            raise ErrorEscaner(t)
        self.imagenes_crudas = len(t)
        return t


@pytest.fixture
def esp(tmp_path):
    return Espacio(tmp_path / "datos", tmp_path / "escaneo").asegurar()


def _cliente(esp, tandas=()):
    app = web.crear_app(esp, Escaner(tandas))
    return app.test_client(), app.config["FICHA"]


def _esperar(cl):
    t = time.time()
    while time.time() - t < 15:
        d = cl.get("/escaneo.json").get_json()
        if not d["en_curso"]:
            return d
        time.sleep(0.05)
    raise AssertionError("el escaneo no terminó")


def _abrir(cl, ficha, mes=3, n=1):
    return cl.post("/libro/abrir", data={"ficha": ficha, "anio": A, "tipo": "P", "mes": mes, "libro": n})


def _destino(esp):
    return esp.archivo / str(A) / "PROTOCOLOS" / "Marzo" / "libro 1"


def test_sin_libro_el_inicio_ofrece_abrirlo(esp):
    cl, _ = _cliente(esp)
    pag = cl.get("/").get_data(as_text=True)
    assert "Abrir un libro" in pag and "Fin de libro" not in pag


def test_abrir_libro_y_escanear_guarda_solo(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(), _hoja(2), _hoja()]])
    assert _abrir(cl, ficha).status_code == 302
    assert "Libro abierto:" in cl.get("/").get_data(as_text=True)
    cl.post("/escanear", data={"ficha": ficha, "hojas": "4"})
    d = _esperar(cl)
    assert "Se guardaron 1 actos" in d["mensaje"] and cod(A, "P", 2) in d["mensaje"] and "ATENCIÓN" not in d["mensaje"]
    assert [p.name for p in _destino(esp).glob("*.pdf")] == [cod(A, "P", 1) + ".pdf"]
    pag = cl.get("/").get_data(as_text=True)
    assert "acto abierto" in pag and cod(A, "P", 1) in pag


def test_acto_partido_entre_dos_escaneos_y_fin_de_libro(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja()], [_hoja(), _hoja(2), _hoja()]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    assert [p.name for p in _destino(esp).glob("*.pdf")] == [cod(A, "P", 1) + ".pdf"]
    import pymupdf as fitz
    with fitz.open(str(_destino(esp) / (cod(A, "P", 1) + ".pdf"))) as d:
        assert d.page_count == 3
    assert cl.post("/libro/cerrar", data={"ficha": ficha}).status_code == 302
    assert sorted(p.name for p in _destino(esp).glob("*.pdf")) == [cod(A, "P", 1) + ".pdf", cod(A, "P", 2) + ".pdf"]
    assert "Abrir un libro" in cl.get("/").get_data(as_text=True)


def test_tanda_con_salto_queda_por_revisar_y_bloquea_escanear(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(3), _hoja()], [_hoja(4)]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    d = _esperar(cl)
    assert "QUEDÓ POR REVISAR" in d["mensaje"] and not list(_destino(esp).glob("*.pdf")) if _destino(esp).exists() else True
    pag = cl.get("/").get_data(as_text=True)
    assert "Hay una tanda por revisar" in pag and "disabled" in pag
    cl.post("/escanear", data={"ficha": ficha})  # no debe escanear
    assert "Hay una tanda por revisar" in cl.get("/escaneo.json").get_json()["error"]
    lote = libro.pendientes(esp)[0]["id"]
    rev = cl.get(f"/revision/{lote}").get_data(as_text=True)
    assert "No se guardó nada todavía" in rev and "Guardar de todos modos" in rev and "faltan" in rev
    assert cl.get(f"/miniatura/{lote}/1.png").mimetype == "image/png"


def test_aprobar_guarda_y_descartar_aparta(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(3), _hoja()]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    lote = libro.pendientes(esp)[0]["id"]
    assert cl.post(f"/revision/{lote}/aprobar", data={}).status_code == 400  # sin ficha
    r = cl.post(f"/revision/{lote}/aprobar", data={"ficha": ficha})
    assert r.status_code == 200 and "Se guardaron 1 actos" in r.get_data(as_text=True)
    assert not libro.pendientes(esp) and cl.get(f"/revision/{lote}").status_code == 404


def test_descartar_deja_escanear_de_nuevo(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(3)], [_hoja(1), _hoja(), _hoja(2)]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    lote = libro.pendientes(esp)[0]["id"]
    assert cl.post(f"/revision/{lote}/descartar", data={"ficha": ficha}).status_code == 302
    assert list((esp.espera / "descartadas").glob("*.pdf")) and not libro.pendientes(esp)
    cl.post("/escanear", data={"ficha": ficha})
    assert "Se guardaron" in _esperar(cl)["mensaje"]


def test_tanda_sin_codigos_no_ofrece_guardar_de_todos_modos(esp):
    cl, ficha = _cliente(esp, [[_hoja(), _hoja()]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    lote = libro.pendientes(esp)[0]["id"]
    rev = cl.get(f"/revision/{lote}").get_data(as_text=True)
    assert "Guardar de todos modos" not in rev and "Descartar y volver a escanear" in rev
    assert cl.post(f"/revision/{lote}/aprobar", data={"ficha": ficha}).status_code == 409


def test_hojas_indicadas_que_no_coinciden_dejan_la_tanda_por_revisar(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(), _hoja(2)]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha, "hojas": "5"})
    d = _esperar(cl)
    assert "QUEDÓ POR REVISAR" in d["mensaje"] and "puso 5 y se escanearon 3" in d["mensaje"]


def test_fin_de_libro_con_tanda_por_revisar_se_niega(esp):
    cl, ficha = _cliente(esp, [[_hoja(1), _hoja(3)]])
    _abrir(cl, ficha)
    cl.post("/escanear", data={"ficha": ficha})
    _esperar(cl)
    r = cl.post("/libro/cerrar", data={"ficha": ficha})
    assert r.status_code == 409 and "por revisar" in r.get_data(as_text=True)


def test_abrir_libro_con_datos_malos_no_revienta(esp):
    cl, ficha = _cliente(esp)
    for datos in ({"anio": "x", "tipo": "P", "mes": "3", "libro": "1"}, {"anio": A, "tipo": "Z", "mes": "3", "libro": "1"},
                  {"anio": A, "tipo": "P", "mes": "14", "libro": "1"}):
        assert cl.post("/libro/abrir", data={"ficha": ficha, **datos}).status_code == 302
    assert libro.estado(esp) is None
    assert "No se pudo abrir el libro" in cl.get("/escaneo.json").get_json()["error"]


def test_dos_aperturas_seguidas_no_abren_dos_libros(esp):
    cl, ficha = _cliente(esp)
    _abrir(cl, ficha, mes=3, n=1)
    _abrir(cl, ficha, mes=4, n=2)
    assert libro.estado(esp)["mes"] == 3
