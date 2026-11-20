"""Libro de PRUEBA imprimible para el escáner (códigos falsos del año 2099; no se confunde con ningún acto real).

    python -m lotes.hoja_prueba SALIDA.pdf          genera el libro (9 hojas) y un resultado_esperado.txt al lado

Se imprime por una cara, se escanea (con el escáner o con el programa en vivo) y el motor debe partir el libro en los
mismos actos que aquí se declaran. Sirve para comprobar: lectura de barras tras imprimir y escanear, hojas en blanco
del dorso (si se escanea a dos caras), códigos de otra notaría y habilitantes propios que NO abren acto.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

import numpy as np
import zxingcpp
from PIL import Image
from zxingcpp import BarcodeFormat

ANIO, TIPO, NOTARIA = 2099, "P", "1101007"
OTRA_NOTARIA = "1101010"


def _cod(sec: int, notaria: str = NOTARIA) -> str:
    return f"{ANIO}{notaria}{TIPO}{sec:05d}"


# (código que ABRE acto | None, [códigos ajenos o habilitantes], nota de la página)
HOJAS = [
    (_cod(1), [], "Abre el acto 00001"),
    (None, [], "Página interior del acto 00001"),
    (None, [_cod(555, OTRA_NOTARIA)], "Interior del 00001 con un habilitante de OTRA notaría (no abre acto)"),
    (_cod(2), [], "Abre el acto 00002"),
    (None, [_cod(1)], "Interior del 00002 con un habilitante propio ya usado, 00001 (no abre acto)"),
    (_cod(3), [], "Abre el acto 00003 (una sola hoja)"),
    (_cod(4), [], "Abre el acto 00004"),
    (None, [], "Página interior del acto 00004"),
    (None, [], "Última hoja del libro (en el programa en vivo: botón «Fin de libro»)"),
]
ESPERADO = [(1, 3, _cod(1)), (4, 5, _cod(2)), (6, 6, _cod(3)), (7, 9, _cod(4))]


def _png_barras(texto: str) -> bytes:
    b = zxingcpp.create_barcode(texto, BarcodeFormat.Code128)
    arr = np.array(zxingcpp.write_barcode_to_image(b, scale=3, add_hrt=False))
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def generar(ruta) -> int:
    doc = fitz.open()
    total = len(HOJAS)
    for i, (abre, ajenos, nota) in enumerate(HOJAS, start=1):
        pag = doc.new_page(width=595, height=842)
        pag.insert_text((60, 120), "Factura: 004-002-000056756", fontsize=11)  # distractor, como en los libros reales
        pag.insert_text((470, 40), f"{8400 + i:06d}", fontsize=14)  # número de 6 dígitos que NO es un código
        y = 50
        for cod in ([abre] if abre else []) + list(ajenos):
            pag.insert_image(fitz.Rect(300, y, 560, y + 60), stream=_png_barras(cod))
            pag.insert_text((340, y + 74), cod, fontsize=11)
            y += 90 if cod == abre else 100
        if abre:
            pag.insert_text((60, 170), f"PROTOCOLIZACION N° {abre}", fontsize=12)
        pag.insert_text((60, 420), f"Hoja {i} de {total}", fontsize=26)
        pag.insert_text((60, 460), nota, fontsize=12)
        pag.insert_text((60, 780), "HOJA DE PRUEBA - NO ES UN DOCUMENTO REAL - códigos del año 2099", fontsize=10)
    doc.save(str(ruta))
    doc.close()
    return total


def resultado_esperado() -> str:
    lineas = ["Resultado esperado del libro de prueba (año 2099, tipo P):", ""]
    for ini, fin, cod in ESPERADO:
        lineas.append(f"  hojas {ini}-{fin}  →  {cod}.pdf")
    lineas += ["", "Códigos que NO deben abrir acto: " + ", ".join(
        f"hoja {n}: {c}" for n, (_, aj, _) in enumerate(HOJAS, 1) for c in aj)]
    return "\n".join(lineas) + "\n"


def comprobar(ruta) -> list[str]:
    """Pasa el motor por el libro y devuelve las diferencias con lo esperado (lista vacía = correcto)."""
    from .deteccion import detectar_pdf
    from .reglas import armar_actos

    total, det = detectar_pdf(ruta, usar_texto=False)  # como un escaneo: solo imagen, sin capa de texto
    res = armar_actos(det, total, ANIO, TIPO)
    problemas = []
    if res.cobertura() != ESPERADO:
        problemas.append(f"actos: esperado {ESPERADO}, obtenido {res.cobertura()}")
    if res.requiere_revision:
        problemas.append(f"el motor pide revisión: {res.avisos} {res.saltos}")
    return problemas


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) != 2:
        sys.exit("uso: python -m lotes.hoja_prueba SALIDA.pdf")
    salida = Path(sys.argv[1])
    generar(salida)
    salida.with_name("resultado_esperado.txt").write_text(resultado_esperado(), encoding="utf-8")
    malo = comprobar(salida)
    print("comprobación del motor sobre el PDF generado:", "CORRECTA" if not malo else malo)
    sys.exit(1 if malo else 0)
