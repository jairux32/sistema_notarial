"""Libros ya escaneados (el archivo viejo): dividir un PDF de libro en sus actos y colocar cada uno donde va.

Es el mismo cuidado que el escaneo en vivo, con una diferencia: el original NO está en la carpeta de entrada sino en su
sitio del archivo (p. ej. `2026/PROTOCOLOS/Abril/proto 1 abril 2026.pdf`).

Garantías (las de `aplicar.py`, más las propias de un archivo que ya existe):
  · Dividir y verificar escriben solo en la carpeta de preparación; el original no se toca.
  · Antes de colocar nada se vuelve a comprobar: el original sigue igual (sha256) y cada acto cortado también.
  · Un libro «para revisar» (hojas sin código, saltos, avisos) solo se coloca si la persona lo acepta de forma expresa.
  · Cada acto se copia con nombre temporal y se renombra; NUNCA pisa un archivo distinto; cada copia se compara con su sha256.
  · El original NO se borra: se aparta, con su misma ruta relativa, en `espera/originales/`. Borrarlo es decisión aparte.
  · Si el proceso se corta a la mitad, repetir la orden termina el trabajo sin duplicar nada.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import informe as inf
from .aplicar import Bloqueado, _copiar_sin_pisar
from .deteccion import detectar_pdf
from .division import ArchivoGenerado, Verificacion, dividir, puede_borrar_original, verificar
from .espacio import Espacio, carpeta_destino
from .reglas import armar_actos
from .rutas import numeros, parse_ruta

_ANIO = re.compile(r"(19|20)\d{2}")


def libro_probable(archivo: str) -> int | None:
    """Número de libro que dice el nombre del archivo («proto 6 abril 2026.pdf» → 6), o None si no es claro."""
    sin_ext = archivo.rsplit(".", 1)[0]
    candidatos = [n for n in numeros(sin_ext) if not (len(str(n)) == 4 and _ANIO.fullmatch(str(n)))]
    return candidatos[0] if len(candidatos) == 1 else None


def id_de(relativa: str) -> str:
    """Identificador estable y válido (solo letras, números, guion y guion bajo) para la preparación de ese PDF."""
    base = re.sub(r"[^A-Za-z0-9]+", "-", relativa.rsplit(".", 1)[0]).strip("-")[:50]
    return f"ant_{base}_{hashlib.sha256(relativa.encode('utf-8')).hexdigest()[:8]}"


def _relativa(espacio: Espacio, pdf: Path) -> str:
    return pdf.resolve().relative_to(espacio.archivo.resolve()).as_posix()


def preparar(espacio: Espacio, pdf: Path, anio: int, tipo: str, ultimo_previo: int | None = None,
             siguientes: list[int] | None = None, dpi: int = 200, rehacer: bool = False) -> dict:
    """Lee los códigos del libro, corta los actos en `preparacion/<id>` y los verifica. Devuelve el informe."""
    rel = _relativa(espacio, pdf)
    lote_id = id_de(rel)
    prep = espacio.preparacion / lote_id
    if (prep / "aplicado.json").exists():
        raise ValueError("este libro ya se colocó en el archivo")
    if (prep / inf.NOMBRE).is_file() and not rehacer:
        return inf.cargar(prep)
    if prep.exists():
        shutil.rmtree(prep)  # solo la preparación derivada
    st0 = pdf.stat()
    sha0 = inf.sha256_archivo(pdf)
    total, det = detectar_pdf(pdf, dpi=dpi, usar_texto=True)
    res = armar_actos(det, total, anio, tipo, ultimo_previo=ultimo_previo, siguientes=siguientes)
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
        "relativa": rel,
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


def _revalidar(espacio: Espacio, info: dict) -> list[str]:
    prep = espacio.preparacion / info["lote"]
    original = Path(info["original"]["ruta"])
    problemas: list[str] = []
    res = inf.resultado_desde_dict(info["resultado"])
    generados = [ArchivoGenerado(g["nombre"], prep / g["nombre"], g["inicio"], g["fin"]) for g in info["generados"]]
    if not original.is_file():
        problemas.append("el PDF original ya no está en su sitio")
    elif original.stat().st_size != info["original"]["bytes"] or inf.sha256_archivo(original) != info["original"]["sha256"]:
        problemas.append("el PDF original cambió después de analizarlo")
    for g, esperado in zip(generados, info["generados"]):
        if not g.ruta.is_file():
            problemas.append(f"{g.nombre}: ya no existe en la preparación")
        elif inf.sha256_archivo(g.ruta) != esperado["sha256"]:
            problemas.append(f"{g.nombre}: se dañó o lo cambiaron después de prepararlo")
    if not problemas:
        problemas += verificar(original, res, generados).problemas
    return problemas


def _apartar_original(espacio: Espacio, info: dict) -> Path | None:
    origen = Path(info["original"]["ruta"])
    if not origen.is_file():
        return None
    destino = espacio.espera / "originales" / info["relativa"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    n = 1
    base = destino
    while destino.exists():
        n += 1
        destino = base.with_name(f"{base.stem}_{n}{base.suffix}")
    shutil.move(str(origen), str(destino))
    return destino


def aplicar(espacio: Espacio, lote_id: str, mes: int, libro: int, aceptar_revision: bool = False) -> dict:
    prep = espacio.preparacion / lote_id
    marca = prep / "aplicado.json"
    if marca.is_file():  # ya colocado; si el original quedó sin apartar (corte a mitad), se termina
        hecho = json.loads(marca.read_text(encoding="utf-8"))
        info = inf.cargar(prep)
        if Path(info["original"]["ruta"]).is_file():
            hecho["original_en_espera"] = str(_apartar_original(espacio, info))
            marca.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
        if hecho.get("ultimo_secuencial") is not None:
            espacio.registrar_ultimo(hecho["anio"], hecho["tipo"], hecho["ultimo_secuencial"])
        return hecho

    info = inf.cargar(prep)
    problemas = _revalidar(espacio, info)
    if problemas:
        raise Bloqueado(problemas)
    res = inf.resultado_desde_dict(info["resultado"])
    puede, motivos = puede_borrar_original(res, Verificacion())
    if not puede and not aceptar_revision:
        raise Bloqueado(["el libro necesita revisión y no se aceptó expresamente"] + motivos)

    destino = carpeta_destino(espacio, info["anio"], info["tipo"], mes, libro)
    destino.mkdir(parents=True, exist_ok=True)
    archivos = []
    for g in info["generados"]:
        final = f"SIN_CODIGO_{lote_id}.pdf" if g["nombre"] == "SIN_CODIGO.pdf" else g["nombre"]
        estado = _copiar_sin_pisar(prep / g["nombre"], destino / final, g["sha256"])
        archivos.append({"nombre": final, "origen": g["nombre"], "inicio": g["inicio"], "fin": g["fin"], "estado": estado})

    hecho = {
        "lote": lote_id, "relativa": info["relativa"],
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "anio": info["anio"], "tipo": info["tipo"], "mes": mes, "libro": libro,
        "destino": str(destino), "archivos": archivos, "paginas": info["original"]["paginas"],
        "revision_aceptada": bool(not puede), "motivos_revision": motivos if not puede else [],
        "original_sha256": info["original"]["sha256"], "ultimo_secuencial": res.ultimo_secuencial,
    }
    tmp = prep / ".aplicado.json.tmp"
    tmp.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, marca)  # desde aquí el libro cuenta como colocado
    hecho["original_en_espera"] = str(_apartar_original(espacio, info))
    marca.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
    if res.ultimo_secuencial is not None:
        espacio.registrar_ultimo(info["anio"], info["tipo"], res.ultimo_secuencial)
    return hecho


def deducir(espacio: Espacio, pdf: Path) -> tuple[int, str, int | None, int | None]:
    """(año, tipo, mes, libro probable) a partir de la ruta del PDF dentro del archivo. Falla si no se puede asignar."""
    r = parse_ruta(_relativa(espacio, pdf))
    if not r.ok:
        raise ValueError("; ".join(r.problemas) or "ruta fuera del esquema")
    return r.anio, r.tipo, r.mes, libro_probable(r.archivo)
