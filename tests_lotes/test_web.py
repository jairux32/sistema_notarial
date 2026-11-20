import io
import re
import time

import pytest
from PIL import Image

from lotes import web
from lotes.espacio import Espacio
from lotes.kodak import ErrorEscaner

from .sintetico import cod, crear_libro, png_barras

A = 2099


def _pag(sec=None):
    return {"codigo": cod(A, "P", sec), "titulo": True} if sec else {}


class EscanerFalso:
    def __init__(self, jpegs=None, error=None, quedaron=False):
        self.jpegs, self.error, self.llamadas = jpegs or [], error, []
        self.quedaron_hojas = quedaron

    def escanear(self, caras="Simplex", avance=None, **kw):
        self.llamadas.append(caras)
        if avance:
            avance("Escaneando…", len(self.jpegs))
        if self.error:
            raise ErrorEscaner(self.error)
        return self.jpegs


def _jpeg_con_codigo(sec):
    hoja = Image.new("L", (2480, 3508), 255)
    if sec:
        barras = Image.open(io.BytesIO(png_barras(cod(A, "P", sec)))).convert("L")
        hoja.paste(barras.resize((900, 300)), (1400, 150))
    b = io.BytesIO()
    hoja.save(b, "JPEG", quality=85)
    return b.getvalue()


@pytest.fixture
def esp(tmp_path):
    return Espacio(tmp_path / "datos", tmp_path / "escaneo").asegurar()


def _cliente(esp, escaner=None):
    app = web.crear_app(esp, escaner)
    return app.test_client(), app.config["FICHA"]


def _esperar(cl, hasta=10):
    t = time.time()
    while time.time() - t < hasta:
        d = cl.get("/escaneo.json").get_json()
        if not d["en_curso"]:
            return d
        time.sleep(0.05)
    raise AssertionError("el escaneo no terminó")


def test_inicio_vacio(esp):
    cl, _ = _cliente(esp)
    r = cl.get("/")
    assert r.status_code == 200 and "No hay lotes esperando" in r.get_data(as_text=True)


def test_post_sin_ficha_se_rechaza(esp):
    cl, _ = _cliente(esp, EscanerFalso())
    assert cl.post("/escanear", data={}).status_code == 400
    assert cl.post("/lote/abc/guardar", data={"mes": 3, "libro": 1}).status_code == 400


def test_flujo_completo_escanear_revisar_guardar(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1), _jpeg_con_codigo(None), _jpeg_con_codigo(2)])
    cl, ficha = _cliente(esp, esc)
    assert cl.post("/escanear", data={"ficha": ficha, "caras": "Simplex"}).status_code == 302
    assert _esperar(cl)["error"] == ""
    pdfs = list(esp.entrada.glob("escaneo_*.pdf"))
    assert len(pdfs) == 1
    lote = pdfs[0].stem

    pag = cl.get(f"/lote/{lote}").get_data(as_text=True)
    assert cod(A, "P", 1) in pag and cod(A, "P", 2) in pag and "Guardar en el archivo" in pag
    assert cl.get(f"/miniatura/{lote}/1.png").mimetype == "image/png"
    assert cl.get(f"/miniatura/{lote}/9.png").status_code == 404

    r = cl.post(f"/lote/{lote}/guardar", data={"ficha": ficha, "mes": "3", "libro": "1"})
    assert r.status_code == 200 and "Se guardaron 2 archivos" in r.get_data(as_text=True)
    destino = esp.archivo / str(A) / "PROTOCOLOS" / "Marzo" / "libro 1"
    assert len(list(destino.glob("*.pdf"))) == 2
    assert not pdfs[0].exists() and (esp.espera / pdfs[0].name).exists()
    assert "Guardados recientemente" in cl.get("/").get_data(as_text=True)


def test_error_del_escaner_se_muestra_y_no_deja_lotes(esp):
    cl, ficha = _cliente(esp, EscanerFalso(error="no hay hojas en el alimentador"))
    cl.post("/escanear", data={"ficha": ficha})
    d = _esperar(cl)
    assert "no hay hojas" in d["error"] and not list(esp.entrada.glob("*.pdf"))
    assert "no hay hojas" in cl.get("/").get_data(as_text=True)


def test_dos_caras_se_pasa_al_escaner(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1)])
    cl, ficha = _cliente(esp, esc)
    cl.post("/escanear", data={"ficha": ficha, "caras": "Duplex"})
    _esperar(cl)
    assert esc.llamadas == ["Duplex"]


def test_sin_escaner_configurado_no_revienta(esp):
    cl, ficha = _cliente(esp, None)
    cl.post("/escanear", data={"ficha": ficha})
    assert "No hay escáner" in cl.get("/").get_data(as_text=True)


def test_lote_inexistente_o_con_ruta_rara_da_404(esp):
    cl, _ = _cliente(esp)
    assert cl.get("/lote/noexiste").status_code == 404
    assert cl.get("/lote/..%2Fx").status_code == 404
    assert cl.get("/miniatura/noexiste/1.png").status_code == 404


def test_guardar_bloqueado_muestra_los_motivos_y_no_mueve_nada(esp):
    crear_libro(esp.entrada / "l1.pdf", [_pag(), _pag(1), _pag()])  # para revisar
    cl, ficha = _cliente(esp)
    pag = cl.get("/lote/l1").get_data(as_text=True)
    assert "antes del primer código" in pag and 'name="acepto"' in pag
    r = cl.post("/lote/l1/guardar", data={"ficha": ficha, "mes": "3", "libro": "1"})
    assert r.status_code == 409 and "revisión" in r.get_data(as_text=True)
    assert (esp.entrada / "l1.pdf").exists() and not list(esp.archivo.rglob("*.pdf"))
    r = cl.post("/lote/l1/guardar", data={"ficha": ficha, "mes": "3", "libro": "1", "acepto": "1"})
    assert r.status_code == 200


def test_mes_o_libro_invalidos_no_guardan(esp):
    crear_libro(esp.entrada / "l1.pdf", [_pag(1)])
    cl, ficha = _cliente(esp)
    cl.get("/lote/l1")
    for datos in ({"mes": "13", "libro": "1"}, {"mes": "3", "libro": "../../x"}, {"mes": "3", "libro": "5000"}):
        assert cl.post("/lote/l1/guardar", data={"ficha": ficha, **datos}).status_code == 400
    assert (esp.entrada / "l1.pdf").exists()


def test_clave_de_acceso_si_se_define(esp, monkeypatch):
    monkeypatch.setenv("SEPARADOR_USUARIO", "u")
    monkeypatch.setenv("SEPARADOR_CLAVE", "prueba-no-real")
    cl, _ = _cliente(esp)
    assert cl.get("/").status_code == 401
    import base64
    ok = base64.b64encode(b"u:prueba-no-real").decode()
    assert cl.get("/", headers={"Authorization": f"Basic {ok}"}).status_code == 200
    mal = base64.b64encode(b"u:otra").decode()
    assert cl.get("/", headers={"Authorization": f"Basic {mal}"}).status_code == 401


def test_rehacer_con_otro_tipo(esp):
    crear_libro(esp.entrada / "l1.pdf", [_pag(1), _pag(2)])
    cl, ficha = _cliente(esp)
    cl.get("/lote/l1")
    r = cl.post("/lote/l1/rehacer", data={"ficha": ficha, "anio": "2099", "tipo": "D"})
    assert r.status_code == 200 and "No se pudo armar ningún acto" in r.get_data(as_text=True)
    r = cl.post("/lote/l1/rehacer", data={"ficha": ficha, "anio": "2099", "tipo": "P"})
    assert r.status_code == 302 and cod(A, "P", 1) in cl.get("/lote/l1").get_data(as_text=True)
    assert cl.post("/lote/l1/rehacer", data={"ficha": ficha, "anio": "2099", "tipo": "X"}).status_code == 400


def test_hojas_sin_tomar_avisan_y_exigen_aceptacion(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1), _jpeg_con_codigo(None)], quedaron=True)
    cl, ficha = _cliente(esp, esc)
    cl.post("/escanear", data={"ficha": ficha})
    d = _esperar(cl)
    assert "quedaron hojas sin escanear" in d["mensaje"]
    lote = next(esp.entrada.glob("escaneo_*.pdf")).stem
    assert "posibles hojas sin escanear" in cl.get("/").get_data(as_text=True)
    pag = cl.get(f"/lote/{lote}").get_data(as_text=True)
    assert "todavía detectaba hojas" in pag and 'name="acepto"' in pag
    r = cl.post(f"/lote/{lote}/guardar", data={"ficha": ficha, "mes": "3", "libro": "1"})
    assert r.status_code == 409 and "todavía detectaba hojas" in r.get_data(as_text=True)
    assert (esp.entrada / f"{lote}.pdf").exists()
    r = cl.post(f"/lote/{lote}/guardar", data={"ficha": ficha, "mes": "3", "libro": "1", "acepto": "1"})
    assert r.status_code == 200 and not list(esp.entrada.glob("*.aviso")) and list(esp.espera.glob("*.aviso"))


def test_si_las_hojas_indicadas_no_coinciden_avisa_y_exige_aceptacion(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1), _jpeg_con_codigo(None)])
    cl, ficha = _cliente(esp, esc)
    cl.post("/escanear", data={"ficha": ficha, "hojas": "3"})
    d = _esperar(cl)
    assert "puso 3 y se escanearon 2" in d["mensaje"]
    lote = next(esp.entrada.glob("escaneo_*.pdf")).stem
    pag = cl.get(f"/lote/{lote}").get_data(as_text=True)
    assert "indicó 3 hojas y el escáner entregó 2" in pag
    r = cl.post(f"/lote/{lote}/guardar", data={"ficha": ficha, "mes": "3", "libro": "1"})
    assert r.status_code == 409


def test_si_las_hojas_coinciden_no_hay_aviso(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1), _jpeg_con_codigo(None)])
    cl, ficha = _cliente(esp, esc)
    cl.post("/escanear", data={"ficha": ficha, "hojas": "2"})
    assert "ATENCIÓN" not in _esperar(cl)["mensaje"] and not list(esp.entrada.glob("*.aviso"))


def test_dos_caras_cuenta_dos_imagenes_por_hoja(esp):
    esc = EscanerFalso([_jpeg_con_codigo(1), _jpeg_con_codigo(2)])
    esc.imagenes_crudas = 4  # 2 hojas a dos caras; los dorsos en blanco ya se quitaron
    cl, ficha = _cliente(esp, esc)
    cl.post("/escanear", data={"ficha": ficha, "hojas": "2", "caras": "Duplex"})
    assert "ATENCIÓN" not in _esperar(cl)["mensaje"]


def test_hojas_indicadas_basura_se_ignora(esp):
    cl, ficha = _cliente(esp, EscanerFalso([_jpeg_con_codigo(1)]))
    assert cl.post("/escanear", data={"ficha": ficha, "hojas": "abc"}).status_code == 302
    assert "ATENCIÓN" not in _esperar(cl)["mensaje"]
