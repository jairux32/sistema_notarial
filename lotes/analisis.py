"""Análisis de un libro con dos ayudas para los códigos que el primer paso no leyó:

  · RECUPERACIÓN dirigida: si la numeración tiene un hueco (faltan 00900…), se vuelven a leer, con más esfuerzo (otras
    resoluciones, hoja entera, blanco y negro), SOLO las hojas que caen dentro del hueco, y se acepta únicamente un código
    que sea justo uno de los números que faltan. Así no se agregan actos inventados. Todo código recuperado deja el libro
    «para revisar» para que una persona lo confirme.
  · CÓDIGOS A MANO: la persona dice «la hoja 769 es el 01181» y eso manda sobre lo que se haya leído.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

import numpy as np
import zxingcpp
from PIL import Image

from .codigos import NOTARIA_PROPIA, parse_codigo
from .deteccion import detectar_pdf
from .reglas import Resultado, armar_actos

# (resolución, parte de la hoja que se mira, pasar a blanco y negro). De lo más barato a lo más caro.
AJUSTES = ((300, 0.5, False), (150, 0.5, False), (200, 1.0, False), (300, 1.0, False), (400, 1.0, False),
           (200, 1.0, True), (300, 1.0, True), (150, 1.0, True))
MAX_PAGINAS_POR_HUECO = 400

Lector = Callable[[int, set], "str | None"]


def lector_a_fondo(doc, anio: int, tipo: str, notaria: str = NOTARIA_PROPIA) -> Lector:
    """Lector de una hoja con varios ajustes. Devuelve el texto del código solo si es uno de los `esperados`."""

    def leer(pagina: int, esperados: set) -> str | None:
        try:
            pg = doc.load_page(pagina - 1)
        except Exception:  # hoja dañada: no se puede leer
            return None
        r = pg.rect
        for dpi, franja, binaria in AJUSTES:
            try:
                clip = fitz.Rect(r.x0, r.y0, r.x1, r.y0 + r.height * franja)
                zoom = dpi / 72
                pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY, alpha=False)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                if binaria:
                    img = img.point(lambda v: 255 if v > 150 else 0)
                lecturas = zxingcpp.read_barcodes(np.array(img), try_rotate=True)
            except Exception:  # imagen dañada en esa hoja
                continue
            for b in lecturas:
                cod = parse_codigo((b.text or "").strip())
                if cod and cod.notaria == notaria and cod.anio == anio and cod.tipo == tipo and cod.secuencial in esperados:
                    return cod.texto
        return None

    return leer


def analizar(pdf: Path, anio: int, tipo: str, ultimo_previo: int | None = None, siguientes: list[int] | None = None,
             dpi: int = 200, manuales: dict[int, str] | None = None, recuperar: bool = True, leido=None,
             lector: Lector | None = None, pasadas: int = 3) -> Resultado:
    """Lee el libro, arma los actos y, si quedan huecos, intenta recuperar los códigos que faltan."""
    total, det = leido or detectar_pdf(pdf, dpi=dpi, usar_texto=True)
    manuales = dict(manuales or {})
    res = armar_actos(det, total, anio, tipo, ultimo_previo=ultimo_previo, siguientes=siguientes, manuales=manuales)
    if not recuperar or not res.huecos:
        return res
    doc = None
    if lector is None:
        doc = fitz.open(str(pdf))
        lector = lector_a_fondo(doc, anio, tipo)
    try:
        recuperados: dict[int, str] = {}
        for _ in range(pasadas):
            nuevos: dict[int, str] = {}
            for desde, hasta, p0, p1 in res.huecos:
                if p1 - p0 + 1 > MAX_PAGINAS_POR_HUECO:
                    continue
                esperados = set(range(desde, hasta + 1))
                for p in range(p0, p1 + 1):
                    texto = lector(p, esperados)
                    cod = parse_codigo(texto) if texto else None
                    if cod and cod.secuencial in esperados:
                        nuevos[p] = cod.texto
                        esperados.discard(cod.secuencial)
                    if not esperados:
                        break
            if not nuevos:
                break
            recuperados.update(nuevos)
            res = armar_actos(det, total, anio, tipo, ultimo_previo=ultimo_previo, siguientes=siguientes,
                              manuales=manuales, recuperados=recuperados)
        return res
    finally:
        if doc is not None:
            doc.close()
