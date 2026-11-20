"""Lotes de la carpeta de entrada: guardar un escaneo, listarlos y prepararlos (leer códigos, cortar y verificar).

Nada aquí toca el archivo definitivo ni borra un original: eso lo hace `aplicar`, y solo con la orden de una persona.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

from . import informe as inf
from .codigos import NOTARIA_PROPIA, parse_codigo
from .deteccion import detectar_pdf
from .division import dividir, puede_borrar_original, verificar
from .espacio import Espacio, validar_id
from .reglas import armar_actos


def nuevo_id(ahora: datetime | None = None, espacio: Espacio | None = None) -> str:
    """Identificador de lote por fecha y hora. Con `espacio`, nunca repite uno ya usado (ni siquiera apartado)."""
    base = "escaneo_" + (ahora or datetime.now()).strftime("%Y%m%d_%H%M%S")
    if espacio is None:
        return base
    usados = {p.stem for d in (espacio.entrada, espacio.espera, espacio.espera / "descartadas") if d.is_dir() for p in d.glob("*.pdf")}
    usados |= {p.name for p in espacio.preparacion.iterdir()} if espacio.preparacion.is_dir() else set()
    try:
        import json
        usados |= set(json.loads((espacio.datos / "libro" / "estado.json").read_text(encoding="utf-8")).get("lotes", []))
    except (OSError, ValueError):
        pass
    candidato, n = base, 1
    while candidato in usados:
        n += 1
        candidato = f"{base}_{n}"
    return candidato


def jpegs_a_pdf(jpegs: list[bytes], destino: Path, dpi: int = 300) -> int:
    """Arma un PDF con una página por imagen, sin recomprimir los JPEG. Escribe con nombre temporal y renombra."""
    from PIL import Image
    import io
    import os

    doc = fitz.open()
    for datos in jpegs:
        with Image.open(io.BytesIO(datos)) as im:
            w, h = im.size
        ancho, alto = w * 72 / dpi, h * 72 / dpi
        pag = doc.new_page(width=ancho, height=alto)
        pag.insert_image(fitz.Rect(0, 0, ancho, alto), stream=datos)
    tmp = destino.with_name("." + destino.name + ".tmp")
    doc.save(str(tmp), garbage=0, deflate=False)
    doc.close()
    os.replace(tmp, destino)
    return len(jpegs)


def listar(espacio: Espacio) -> list[dict]:
    """Lotes que esperan en la carpeta de entrada, del más antiguo al más nuevo."""
    lotes = []
    for p in sorted(espacio.entrada.glob("*.pdf")):
        if p.name.startswith("."):
            continue
        lote_id = p.stem
        try:
            validar_id(lote_id)
        except ValueError:
            continue  # nombre raro: se ignora, no se toca
        prep = espacio.preparacion / lote_id
        lotes.append({
            "id": lote_id,
            "bytes": p.stat().st_size,
            "fecha": datetime.fromtimestamp(p.stat().st_mtime),
            "preparado": (prep / inf.NOMBRE).is_file(),
            "aviso": aviso(espacio, lote_id),
        })
    return lotes


AVISO_HOJAS = ("Al terminar de escanear, el escáner todavía detectaba hojas dentro del alimentador: es posible que "
               "falten hojas en este lote. Revise el alimentador y escanee de nuevo lo que haya quedado.")


def aviso_por_conteo(indicadas: int, entregadas: int) -> str:
    return (f"Usted indicó {indicadas} hojas y el escáner entregó {entregadas}. Puede que se hayan pegado hojas "
            "(entran juntas y solo se escanea la de arriba) o que falte alguna. Revise la pila y vuelva a escanear.")


def marcar_aviso(espacio: Espacio, lote_id: str, texto: str = AVISO_HOJAS) -> None:
    (espacio.entrada / f"{validar_id(lote_id)}.aviso").write_text(texto, encoding="utf-8")


def aviso(espacio: Espacio, lote_id: str) -> str | None:
    """Aviso que dejó el escaneo sobre este lote (por ejemplo, hojas sin tomar), o None."""
    try:
        return (espacio.entrada / f"{validar_id(lote_id)}.aviso").read_text(encoding="utf-8") or None
    except (OSError, ValueError):
        return None


def aplicados(espacio: Espacio, maximo: int = 30) -> list[dict]:
    """Lotes ya guardados en el archivo (su original está en la carpeta de espera), los más recientes primero."""
    import json

    res = []
    for marca in espacio.preparacion.glob("*/aplicado.json"):
        try:
            res.append(json.loads(marca.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    res.sort(key=lambda d: d.get("fecha", ""), reverse=True)
    return res[:maximo]


def serie_probable(pdf: Path, dpi: int = 200) -> tuple[int, str] | None:
    """(año, tipo) del primer código de la Notaría Séptima que traiga el PDF, o None."""
    _, det = detectar_pdf(pdf, dpi=dpi, usar_texto=True)
    for d in det:
        for crudo in d.barras + d.textos:
            c = parse_codigo(crudo)
            if c and c.notaria == NOTARIA_PROPIA:
                return c.anio, c.tipo
    return None


def preparar(espacio: Espacio, lote_id: str, anio: int | None = None, tipo: str | None = None, dpi: int = 200,
             rehacer: bool = False) -> dict:
    """Lee los códigos del lote, corta los actos en `preparacion/<id>` y los verifica. Devuelve el informe.

    Si ya estaba preparado se devuelve tal cual (salvo `rehacer`, que descarta SOLO la preparación, nunca el original,
    y no se permite si el lote ya se guardó en el archivo).
    """
    validar_id(lote_id)
    pdf = espacio.entrada / f"{lote_id}.pdf"
    prep = espacio.preparacion / lote_id
    if not pdf.is_file():
        raise FileNotFoundError(f"no existe el lote {lote_id} en la carpeta de entrada")
    if (prep / "aplicado.json").exists():
        raise ValueError("este lote ya se guardó en el archivo")
    if (prep / inf.NOMBRE).is_file() and not rehacer:
        return inf.cargar(prep)
    if prep.exists():
        shutil.rmtree(prep)  # solo la preparación derivada; el original no se toca
    if anio is None or tipo is None:
        serie = serie_probable(pdf, dpi)
        if serie is None:
            return {"sin_serie": True, "original": {"ruta": str(pdf)}}
        anio, tipo = serie
    st0 = pdf.stat()
    sha0 = inf.sha256_archivo(pdf)
    ultimo_previo = espacio.ultimo(anio, tipo)
    total, det = detectar_pdf(pdf, dpi=dpi, usar_texto=True)
    res = armar_actos(det, total, anio, tipo, ultimo_previo=ultimo_previo)
    if not res.actos:
        return {"sin_actos": True, "anio": anio, "tipo": tipo, "original": {"ruta": str(pdf)},
                "resultado": inf.resultado_a_dict(res)}
    generados = dividir(pdf, res, prep)
    ver = verificar(pdf, res, generados)
    st1 = pdf.stat()
    if (st1.st_size, st1.st_mtime_ns) != (st0.st_size, st0.st_mtime_ns):
        ver.problemas.append("el original cambió mientras se analizaba")
    puede, motivos = puede_borrar_original(res, ver)
    info = {
        "version": inf.VERSION,
        "creado": datetime.now().isoformat(timespec="seconds"),
        "lote": lote_id,
        "original": {"ruta": str(pdf), "bytes": st0.st_size, "sha256": sha0, "paginas": res.total_paginas},
        "anio": anio, "tipo": tipo, "ultimo_previo": ultimo_previo,
        "preparacion": str(prep),
        "resultado": inf.resultado_a_dict(res),
        "generados": [
            {"nombre": g.nombre, "inicio": g.inicio, "fin": g.fin, "bytes": g.ruta.stat().st_size,
             "sha256": inf.sha256_archivo(g.ruta)}
            for g in generados
        ],
        "verificacion": {"correcta": ver.correcta, "problemas": ver.problemas,
                         "paginas_originales": ver.paginas_originales, "paginas_generadas": ver.paginas_generadas},
        "puede_borrar_original": puede, "motivos": motivos,
    }
    inf.guardar(prep, info)
    return info
