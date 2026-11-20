"""Cliente de la API Web de la Kodak S2060w/S2080w (firmware 230802), escrito a partir de lo medido en la notaría.

Flujo: abrir sesión → comprobar que hay hojas → configurar → StartScan → bajar cada imagen (JPEG) en cuanto aparece y
borrarla del escáner → cerrar la sesión SIEMPRE. Una sesión abierta bloquea el escáner para los demás (HTTP 423) y caduca
a los 5 minutos sin llamadas, por eso la sesión se cierra en un `finally`.

El escáner usa un certificado propio, así que no se verifica (`verify=False`); solo se habla con la IP configurada.
Nada de lo que se baja se imprime ni se registra: solo contadores.
"""
from __future__ import annotations

import io
import json
import time
from typing import Callable

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ErrorEscaner(Exception):
    """Algo impidió escanear; el mensaje está escrito para la persona que escanea."""


def es_hoja_en_blanco(jpeg: bytes, umbral_oscuro: float = 0.002) -> bool:
    """Verdadero si casi no hay píxeles oscuros (dorso vacío). `umbral_oscuro` = fracción mínima de píxeles < 128."""
    from PIL import Image

    with Image.open(io.BytesIO(jpeg)) as im:
        g = im.convert("L")
        g.thumbnail((400, 400))
        datos = g.tobytes()
    oscuros = sum(1 for b in datos if b < 128)
    return oscuros / max(len(datos), 1) < umbral_oscuro


class Kodak:
    def __init__(self, ip: str, esquema: str = "https", usuario: str = "Separador Notaria7",
                 http: requests.Session | None = None, dormir: Callable[[float], None] = time.sleep):
        self.base = f"{esquema}://{ip}/api/session"
        self.usuario = usuario
        self.http = http or requests.Session()
        self.http.verify = False
        self.dormir = dormir
        self.imagenes_crudas = 0  # imágenes entregadas por el escáner, antes de quitar dorsos en blanco
        self.quedaron_hojas = False  # tras escanear: ¿el alimentador todavía detectaba papel?

    # ------------------------------------------------------------------ llamadas
    def _abrir_sesion(self, intentos: int = 15) -> str:
        for _ in range(intentos):
            try:
                r = self.http.post(self.base, data=json.dumps({"OCPUserName": self.usuario}), timeout=15)
            except requests.RequestException as e:
                raise ErrorEscaner(f"no se pudo hablar con el escáner (¿apagado o fuera de la red?): {type(e).__name__}") from e
            if r.status_code == 200:
                return r.json()["SessionId"]
            if r.status_code == 423:
                raise ErrorEscaner("el escáner está en uso por otro programa o equipo; espere un momento y reintente")
            if r.status_code == 408:  # despertando
                self.dormir(2)
                continue
            raise ErrorEscaner(f"el escáner no abrió la sesión (código {r.status_code})")
        raise ErrorEscaner("el escáner no terminó de despertar; reintente en un minuto")

    def _cerrar_sesion(self, sid: str) -> None:
        try:
            self.http.delete(f"{self.base}?SessionId={sid}", timeout=10)
        except requests.RequestException:
            pass  # caduca sola a los 5 minutos

    # ------------------------------------------------------------------ escaneo
    def escanear(self, caras: str = "Simplex", color: str = "Gray", dpi: int = 300, espera_max: int = 600,
                 sin_avance: int = 150, avance: Callable[[str, int], None] | None = None) -> list[bytes]:
        """Escanea el alimentador entero y devuelve los JPEG en orden. Con `caras="Duplex"` quita los dorsos en blanco."""
        if caras not in ("Simplex", "Duplex"):
            raise ValueError("caras debe ser Simplex o Duplex")
        notificar = avance or (lambda mensaje, hojas: None)
        self.quedaron_hojas = False
        self.imagenes_crudas = 0
        notificar("Conectando con el escáner…", 0)
        sid = self._abrir_sesion()
        q = f"?SessionId={sid}"
        try:
            st = self.http.get(f"{self.base}/status{q}", timeout=15).json()["Status"]
            if str(st.get("PaperDetected")) != "1":
                raise ErrorEscaner("no hay hojas en el alimentador")
            # AutoStart=1 es lo que hace que StartScan arranque solo (medido 20-nov-2026): con AutoStart=0 el escáner
            # queda «Scanning» pero esperando que alguien pulse ▶ en su pantalla.
            cfg = {"Configuration": {"DPI": dpi, "ScanSide": caras, "ColorMode": color, "SkipBlankPages": 0, "AutoStart": 1}}
            r = self.http.put(f"{self.base}{q}", data=json.dumps(cfg, separators=(",", ":")), timeout=15)
            if r.status_code != 200:
                raise ErrorEscaner(f"el escáner no aceptó la configuración (código {r.status_code})")
            r = self.http.post(f"{self.base}/StartScan{q}", data={}, timeout=15)
            if r.status_code != 200:
                raise ErrorEscaner(f"el escáner no empezó a escanear (código {r.status_code})")
            notificar("Escaneando…", 0)
            imagenes: list[bytes] = []
            bajadas = 0
            inicio = ultimo_avance = time.monotonic()
            while True:
                self.dormir(1.5)
                st = self.http.get(f"{self.base}/status{q}", timeout=15).json()["Status"]
                disponibles = int(st.get("NumImagesScanned") or 0)
                while bajadas < disponibles:
                    n = bajadas + 1
                    img = self.http.get(f"{self.base}/image/{n}{q}", timeout=60)
                    if img.status_code != 200:
                        raise ErrorEscaner(f"no se pudo bajar la imagen {n} del escáner (código {img.status_code})")
                    imagenes.append(img.content)
                    self.http.delete(f"{self.base}/image/{n}{q}", timeout=15)
                    bajadas = n
                    ultimo_avance = time.monotonic()
                    notificar("Escaneando…", len(imagenes))
                if st.get("State") == "Error" or int(st.get("ErrorNum") or 0):
                    raise ErrorEscaner(f"el escáner informó un error: {st.get('LastError') or st.get('ErrorNum')}")
                if st.get("State") == "Done Scanning" and bajadas >= disponibles:
                    break
                ahora = time.monotonic()
                if ahora - inicio > espera_max:
                    raise ErrorEscaner("el escaneo tardó demasiado y se canceló")
                if ahora - ultimo_avance > sin_avance:
                    raise ErrorEscaner("el escáner dejó de entregar hojas")
            # Medido en la notaría (20-nov-2026): el escáner puede dar el lote por terminado dejando hojas sin tomar
            # dentro del alimentador, sin avisar de error. Se anota para que la persona lo sepa.
            fin = self.http.get(f"{self.base}/status{q}", timeout=15).json()["Status"]
            self.quedaron_hojas = str(fin.get("PaperDetected")) == "1"
            if not imagenes:
                raise ErrorEscaner("el escáner no entregó ninguna hoja")
            self.imagenes_crudas = len(imagenes)
            if caras == "Duplex":
                imagenes = [im for i, im in enumerate(imagenes) if i % 2 == 0 or not es_hoja_en_blanco(im)]
            return imagenes
        except requests.RequestException as e:
            raise ErrorEscaner(f"se perdió la comunicación con el escáner: {type(e).__name__}") from e
        finally:
            self._cerrar_sesion(sid)
