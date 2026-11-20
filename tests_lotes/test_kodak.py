"""Prueba el cliente de la Kodak contra un escáner de mentira (servidor HTTP local que imita su API)."""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from lotes.kodak import ErrorEscaner, Kodak, es_hoja_en_blanco


def _jpeg(oscuro: bool) -> bytes:
    im = Image.new("L", (600, 800), 255)
    if oscuro:
        for x in range(100, 500):
            for y in range(100, 140):
                im.putpixel((x, y), 0)
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


class Falso:
    """Estado compartido del escáner de mentira."""

    def __init__(self, hojas, papel="1", sesion_status=200, errores=None, papel_final="0"):
        self.hojas, self.papel, self.sesion_status = hojas, papel, sesion_status
        self.papel_final = papel_final
        self.visibles = 0
        self.iniciado = False
        self.sesion_abierta = False
        self.borradas = []
        self.config = None
        self.errores = errores or {}


@pytest.fixture
def escaner():
    estado = Falso([_jpeg(True), _jpeg(True)])
    servidor = None

    def crear(est):
        nonlocal servidor, estado
        estado = est

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, codigo, cuerpo=None):
                datos = json.dumps(cuerpo or {}).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def do_POST(self):
                ruta = urlparse(self.path).path
                n = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(n)
                if ruta == "/api/session":
                    if estado.sesion_status != 200:
                        return self._json(estado.sesion_status)
                    estado.sesion_abierta = True
                    return self._json(200, {"SessionId": "S1"})
                if ruta == "/api/session/StartScan":
                    estado.iniciado = True
                    return self._json(200)
                self._json(404)

            def do_PUT(self):
                n = int(self.headers.get("Content-Length") or 0)
                estado.config = json.loads(self.rfile.read(n))
                self._json(200)

            def do_GET(self):
                ruta = urlparse(self.path).path
                if ruta == "/api/session/status":
                    if estado.iniciado and estado.visibles < len(estado.hojas):
                        estado.visibles += 1
                    hecho = estado.iniciado and estado.visibles >= len(estado.hojas)
                    st = {"State": "Done Scanning" if hecho else ("Scanning" if estado.iniciado else "In Session"),
                          "NumImagesScanned": estado.visibles, "PaperDetected": estado.papel_final if hecho else estado.papel, "ErrorNum": 0}
                    st.update(estado.errores)
                    return self._json(200, {"Status": st})
                if ruta.startswith("/api/session/image/"):
                    n = int(ruta.rsplit("/", 1)[1])
                    cuerpo = estado.hojas[n - 1]
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(cuerpo)))
                    self.end_headers()
                    return self.wfile.write(cuerpo)
                self._json(404)

            def do_DELETE(self):
                ruta = urlparse(self.path).path
                if ruta.startswith("/api/session/image/"):
                    estado.borradas.append(int(ruta.rsplit("/", 1)[1]))
                elif ruta == "/api/session":
                    estado.sesion_abierta = False
                self._json(200)

        servidor = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        k = Kodak(f"127.0.0.1:{servidor.server_port}", esquema="http", dormir=lambda s: None)
        return k, estado

    yield crear
    if servidor:
        servidor.shutdown()
        servidor.server_close()


def test_escanea_baja_borra_y_cierra_la_sesion(escaner):
    k, est = escaner(Falso([_jpeg(True)] * 3))
    avances = []
    imgs = k.escanear(avance=lambda m, n: avances.append(n))
    assert len(imgs) == 3 and all(i[:2] == b"\xff\xd8" for i in imgs)
    assert est.borradas == [1, 2, 3], "cada imagen se borra del escáner al bajarla"
    assert not est.sesion_abierta, "la sesión se cierra siempre"
    assert est.config["Configuration"]["ScanSide"] == "Simplex" and est.config["Configuration"]["DPI"] == 300
    assert est.config["Configuration"]["AutoStart"] == 1  # sin esto el escáner espera que se pulse ▶ en su pantalla
    assert avances[-1] == 3


def test_sin_hojas_no_escanea_y_cierra_la_sesion(escaner):
    k, est = escaner(Falso([], papel="0"))
    with pytest.raises(ErrorEscaner, match="no hay hojas"):
        k.escanear()
    assert not est.iniciado and not est.sesion_abierta


def test_escaner_ocupado_se_explica(escaner):
    k, _ = escaner(Falso([_jpeg(True)], sesion_status=423))
    with pytest.raises(ErrorEscaner, match="en uso"):
        k.escanear()


def test_error_del_escaner_cierra_la_sesion(escaner):
    k, est = escaner(Falso([_jpeg(True)], errores={"State": "Error", "LastError": "atasco"}))
    with pytest.raises(ErrorEscaner, match="atasco"):
        k.escanear()
    assert not est.sesion_abierta


def test_duplex_quita_solo_los_dorsos_en_blanco(escaner):
    k, _ = escaner(Falso([_jpeg(True), _jpeg(False), _jpeg(True), _jpeg(True)]))
    assert len(k.escanear(caras="Duplex")) == 3  # el dorso blanco (2.ª) sale; el dorso con texto (4.ª) se queda


def test_hoja_en_blanco():
    assert es_hoja_en_blanco(_jpeg(False)) and not es_hoja_en_blanco(_jpeg(True))


def test_sin_conexion_da_un_mensaje_claro():
    k = Kodak("127.0.0.1:9", esquema="http", dormir=lambda s: None)
    with pytest.raises(ErrorEscaner, match="no se pudo hablar"):
        k.escanear()


def test_avisa_si_al_terminar_quedaban_hojas_en_el_alimentador(escaner):
    k, est = escaner(Falso([_jpeg(True)] * 2, papel_final="1"))
    assert len(k.escanear()) == 2 and k.quedaron_hojas is True and not est.sesion_abierta


def test_no_avisa_si_el_alimentador_quedo_vacio(escaner):
    k, _ = escaner(Falso([_jpeg(True)] * 2))
    k.escanear()
    assert k.quedaron_hojas is False


def test_cuenta_las_imagenes_crudas_antes_de_quitar_dorsos(escaner):
    k, _ = escaner(Falso([_jpeg(True), _jpeg(False), _jpeg(True), _jpeg(True)]))
    assert len(k.escanear(caras="Duplex")) == 3 and k.imagenes_crudas == 4
