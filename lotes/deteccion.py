"""Lectura de los códigos de una página de PDF: código de barras (fuente principal) y texto (respaldo y confirmación).

En los libros de 2015 en adelante el código de acto aparece tres veces en la primera página: código de barras Code 128,
el mismo número impreso debajo y el título («PROTOCOLIZACIÓN N° …»). El código de barras se lee casi sin errores, así que
es la fuente principal; el texto confirma. El sello de 2014 (sin código de barras) necesita OCR y va en otro módulo.
"""
from __future__ import annotations

from pathlib import Path

try:  # PyMuPDF ≥ 1.24 se importa como pymupdf; versiones anteriores, como fitz
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

import zxingcpp
from PIL import Image

from .codigos import codigos_en_texto
from .reglas import DeteccionPagina


def leer_barras(pagina, dpi: int = 200, franja: float = 0.5) -> tuple[str, ...]:
    """Textos de los códigos de barras Code 128 de la franja superior de la página."""
    r = pagina.rect
    clip = fitz.Rect(r.x0, r.y0, r.x1, r.y0 + r.height * franja)
    zoom = dpi / 72
    pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY, alpha=False)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    lecturas = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.Code128, try_rotate=True)
    vistos: list[str] = []
    for lec in lecturas:
        if lec.text and lec.text not in vistos:
            vistos.append(lec.text)
    return tuple(vistos)


def leer_texto(pagina, franja: float = 0.5) -> tuple[str, ...]:
    """Códigos con forma válida que aparecen en el texto digital de la franja superior (si el PDF lo trae)."""
    r = pagina.rect
    clip = fitz.Rect(r.x0, r.y0, r.x1, r.y0 + r.height * franja)
    texto = pagina.get_text("text", clip=clip)
    return tuple(c.texto for c in codigos_en_texto(texto))


def detectar_pdf(ruta: str | Path, dpi: int = 200, franja: float = 0.5, usar_texto: bool = True) -> tuple[int, list[DeteccionPagina]]:
    """Recorre el PDF página por página. Devuelve (total de páginas, detecciones solo de las páginas con algo)."""
    detecciones: list[DeteccionPagina] = []
    with fitz.open(str(ruta)) as doc:
        total = doc.page_count
        for i in range(total):
            pag = doc.load_page(i)
            barras = leer_barras(pag, dpi=dpi, franja=franja)
            textos = leer_texto(pag, franja=franja) if usar_texto else ()
            if barras or textos:
                detecciones.append(DeteccionPagina(pagina=i + 1, barras=barras, textos=textos))
    return total, detecciones
