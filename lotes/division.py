"""Corta un libro en un PDF por acto y comprueba el resultado antes de permitir que se borre el original.

Garantías:
  · Los PDF se escriben primero en una carpeta de PREPARACIÓN, con nombre temporal y renombrados al terminar (nunca queda
    un archivo a medias con el nombre final) y sin pisar lo que ya exista.
  · Se conservan TODAS las páginas: las anteriores al primer código van a «SIN_CODIGO.pdf».
  · `verificar` reabre cada PDF generado, comprueba su número de páginas y compara la huella de cada página con la del
    original (texto + imágenes incrustadas). Solo si todo cuadra y el libro no necesita revisión, `puede_borrar_original`
    es verdadero. Aun así el original no se borra solo: lo aprueba una persona.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

from .reglas import Resultado


def huella_pagina(doc, indice: int) -> str:
    """Huella estable de una página: su tamaño, su texto y los bytes de sus imágenes incrustadas."""
    pag = doc.load_page(indice)
    h = hashlib.sha256()
    h.update(f"{round(pag.rect.width, 1)}x{round(pag.rect.height, 1)}|".encode())
    h.update(pag.get_text("text").encode("utf-8", "ignore"))
    for xref, *_ in pag.get_images(full=True):
        try:
            h.update(hashlib.sha256(doc.extract_image(xref)["image"]).digest())
        except Exception:  # imagen no extraíble: se registra su xref como señal mínima
            h.update(f"xref{xref}".encode())
    return h.hexdigest()


@dataclass
class ArchivoGenerado:
    nombre: str
    ruta: Path
    inicio: int
    fin: int


def dividir(ruta_pdf: str | Path, resultado: Resultado, carpeta_preparacion: str | Path) -> list[ArchivoGenerado]:
    """Escribe un PDF por tramo en `carpeta_preparacion`. Falla si algún destino ya existe (no pisa nada)."""
    destino = Path(carpeta_preparacion)
    destino.mkdir(parents=True, exist_ok=True)
    generados: list[ArchivoGenerado] = []
    with fitz.open(str(ruta_pdf)) as origen:
        for inicio, fin, nombre in resultado.cobertura():
            final = destino / f"{nombre}.pdf"
            if final.exists():
                raise FileExistsError(f"ya existe {final}; no se sobrescribe")
            temporal = destino / f".{nombre}.pdf.tmp"
            nuevo = fitz.open()
            nuevo.insert_pdf(origen, from_page=inicio - 1, to_page=fin - 1)
            nuevo.save(str(temporal), garbage=0, deflate=False)
            nuevo.close()
            os.replace(temporal, final)
            generados.append(ArchivoGenerado(nombre=f"{nombre}.pdf", ruta=final, inicio=inicio, fin=fin))
    return generados


@dataclass
class Verificacion:
    problemas: list[str] = field(default_factory=list)
    paginas_originales: int = 0
    paginas_generadas: int = 0

    @property
    def correcta(self) -> bool:
        return not self.problemas


def verificar(ruta_pdf: str | Path, resultado: Resultado, generados: list[ArchivoGenerado]) -> Verificacion:
    v = Verificacion()
    with fitz.open(str(ruta_pdf)) as origen:
        v.paginas_originales = origen.page_count
        if origen.page_count != resultado.total_paginas:
            v.problemas.append(f"el PDF tiene {origen.page_count} páginas y el análisis usó {resultado.total_paginas}")
        # 1) los tramos cubren todas las páginas, sin huecos ni solapes
        esperado = 1
        for inicio, fin, nombre in resultado.cobertura():
            if inicio != esperado or fin < inicio:
                v.problemas.append(f"tramo {nombre}: páginas {inicio}-{fin} no continúan en la {esperado}")
            esperado = fin + 1
        if esperado != origen.page_count + 1:
            v.problemas.append(f"los tramos terminan en la página {esperado - 1} de {origen.page_count}")
        # 2) cada archivo existe, se abre y trae exactamente sus páginas, idénticas a las del original
        for g in generados:
            if not g.ruta.exists():
                v.problemas.append(f"{g.nombre}: no existe")
                continue
            try:
                with fitz.open(str(g.ruta)) as parte:
                    esperadas = g.fin - g.inicio + 1
                    v.paginas_generadas += parte.page_count
                    if parte.page_count != esperadas:
                        v.problemas.append(f"{g.nombre}: tiene {parte.page_count} páginas y debía tener {esperadas}")
                        continue
                    for k in range(parte.page_count):
                        if huella_pagina(parte, k) != huella_pagina(origen, g.inicio - 1 + k):
                            v.problemas.append(f"{g.nombre}: la página {k + 1} no es idéntica a la {g.inicio + k} del original")
                            break
            except Exception as e:  # PDF dañado
                v.problemas.append(f"{g.nombre}: no se pudo abrir ({e})")
    if v.paginas_generadas != v.paginas_originales:
        v.problemas.append(f"suman {v.paginas_generadas} páginas de {v.paginas_originales}")
    return v


def puede_borrar_original(resultado: Resultado, verificacion: Verificacion) -> tuple[bool, list[str]]:
    """Puerta de seguridad: devuelve (permitido, motivos por los que NO). Nunca borra nada por sí misma."""
    motivos: list[str] = []
    if resultado.requiere_revision:
        motivos += [f"revisión pendiente: {m}" for m in (resultado.saltos + resultado.avisos)]
        if resultado.huerfanas:
            motivos.append(f"páginas {resultado.huerfanas[0]}-{resultado.huerfanas[1]} sin código al inicio")
        if not resultado.actos:
            motivos.append("no se detectó ningún acto")
        if not motivos:
            motivos.append("el libro requiere revisión")
    motivos += verificacion.problemas
    return (not motivos), motivos
