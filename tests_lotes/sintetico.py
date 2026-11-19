"""Genera libros PDF de MENTIRA (con códigos de barras reales Code 128) para probar el motor. No usa ningún escaneo real."""
from __future__ import annotations

import io

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

import numpy as np
import zxingcpp
from PIL import Image
from zxingcpp import BarcodeFormat


def png_barras(texto: str) -> bytes:
    b = zxingcpp.create_barcode(texto, BarcodeFormat.Code128)
    arr = np.array(zxingcpp.write_barcode_to_image(b, scale=3, add_hrt=False))
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def crear_libro(ruta, paginas: list[dict]) -> int:
    """Cada elemento describe una página:
        codigo   código de acto con barras y número impreso (como en 2015+); None = página interior
        titulo   si True, repite el código en un título «PROTOCOLIZACIÓN N° …»
        ajenos   otros códigos de barras en la página (habilitantes de otras notarías o de la propia)
        texto_solo  código escrito solo como texto (sin barras)
    """
    doc = fitz.open()
    for i, p in enumerate(paginas, start=1):
        pag = doc.new_page(width=595, height=842)
        pag.insert_text((60, 120), "Factura: 004-002-000056756", fontsize=11)
        pag.insert_text((470, 40), f"{8400 + i:06d}", fontsize=14)  # número de 6 dígitos que NO es código
        y_barras = 50
        for cod in ([p["codigo"]] if p.get("codigo") else []) + list(p.get("ajenos", [])):
            pag.insert_image(fitz.Rect(300, y_barras, 560, y_barras + 60), stream=png_barras(cod))
            pag.insert_text((340, y_barras + 74), cod, fontsize=11)
            y_barras += 100 if cod != p.get("codigo") else 90
        if p.get("codigo") and p.get("titulo"):
            pag.insert_text((60, 170), f"PROTOCOLIZACION N° {p['codigo']}", fontsize=12)
        if p.get("texto_solo"):
            pag.insert_text((60, 190), p["texto_solo"], fontsize=12)
        pag.insert_text((60, 400), f"Contenido de la página {i} del libro de prueba", fontsize=12)
        pag.insert_text((60, 430), f"Texto distinto {i * 7919} para la huella", fontsize=10)
    doc.save(str(ruta))
    doc.close()
    return len(paginas)


def cod(anio: int, tipo: str, sec: int, notaria: str = "1101007") -> str:
    return f"{anio}{notaria}{tipo}{sec:05d}"
