"""Guarda en el archivo los actos de un lote ya revisado por una persona.

Garantías:
  · Antes de copiar se vuelve a comprobar todo: el original sigue igual (sha256), cada acto cortado sigue igual y trae
    las páginas exactas. Si algo no cuadra se detiene sin tocar nada.
  · Un lote «para revisar» (páginas sin código, saltos de numeración, avisos) solo se guarda si la persona lo acepta
    de forma expresa.
  · Cada archivo se copia con nombre temporal y se renombra; NUNCA pisa uno distinto que ya exista (si ya hay uno
    idéntico, es el mismo trabajo hecho antes y se sigue).
  · Cada copia se compara con su sha256 antes de dar el lote por guardado.
  · El original NO se borra: se aparta en la carpeta de espera. Borrarlo es decisión aparte de una persona.
  · Si el proceso se corta a la mitad, repetir la orden termina el trabajo sin duplicar nada.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import informe as inf
from .division import ArchivoGenerado, Verificacion, puede_borrar_original, verificar
from .entrada import aviso as entrada_aviso
from .espacio import Espacio, carpeta_destino, validar_id


class Bloqueado(Exception):
    """El lote no se puede guardar; `motivos` dice por qué, en lenguaje llano."""

    def __init__(self, motivos: list[str]):
        super().__init__("; ".join(motivos))
        self.motivos = motivos


def revalidar(espacio: Espacio, lote_id: str) -> tuple[dict, list[str]]:
    """Vuelve a comprobar la preparación de un lote contra el original. Devuelve (informe, problemas)."""
    prep = espacio.preparacion / lote_id
    info = inf.cargar(prep)
    original = espacio.entrada / f"{lote_id}.pdf"
    problemas: list[str] = []
    res = inf.resultado_desde_dict(info["resultado"])
    generados = [ArchivoGenerado(g["nombre"], prep / g["nombre"], g["inicio"], g["fin"]) for g in info["generados"]]
    if not original.is_file():
        problemas.append("el PDF original ya no está en la carpeta de entrada")
    elif original.stat().st_size != info["original"]["bytes"] or inf.sha256_archivo(original) != info["original"]["sha256"]:
        problemas.append("el PDF original cambió después de analizarlo")
    for g, esperado in zip(generados, info["generados"]):
        if not g.ruta.is_file():
            problemas.append(f"{g.nombre}: ya no existe en la preparación")
        elif inf.sha256_archivo(g.ruta) != esperado["sha256"]:
            problemas.append(f"{g.nombre}: se dañó o lo cambiaron después de prepararlo")
    if not problemas:
        problemas += verificar(original, res, generados).problemas
    return info, problemas


def _nombre_final(nombre: str, lote_id: str) -> str:
    # SIN_CODIGO.pdf se repite de un lote a otro: se identifica con el lote para que nunca choque
    return f"SIN_CODIGO_{lote_id}.pdf" if nombre == "SIN_CODIGO.pdf" else nombre


def _copiar_sin_pisar(origen: Path, destino: Path, sha: str) -> str:
    """Copia `origen` en `destino`. Devuelve «copiado» o «ya estaba». Si hay otro archivo distinto, falla."""
    if destino.exists():
        if inf.sha256_archivo(destino) == sha:
            return "ya estaba"
        raise Bloqueado([f"en el archivo ya existe «{destino.name}» y es DISTINTO; no se sobrescribe"])
    tmp = destino.with_name("." + destino.name + ".tmp")
    shutil.copyfile(origen, tmp)
    if inf.sha256_archivo(tmp) != sha:
        tmp.unlink(missing_ok=True)
        raise Bloqueado([f"la copia de «{destino.name}» no salió igual; no se guardó"])
    os.replace(tmp, destino)
    return "copiado"


def _apartar_original(espacio: Espacio, lote_id: str) -> Path | None:
    origen = espacio.entrada / f"{lote_id}.pdf"
    if not origen.is_file():
        return None
    destino = espacio.espera / f"{lote_id}.pdf"
    n = 1
    while destino.exists():
        n += 1
        destino = espacio.espera / f"{lote_id}_{n}.pdf"
    shutil.move(str(origen), str(destino))
    nota = espacio.entrada / f"{lote_id}.aviso"
    if nota.is_file():
        shutil.move(str(nota), str(destino.with_suffix(".aviso")))
    return destino


def aplicar(espacio: Espacio, lote_id: str, mes: int, libro: int, aceptar_revision: bool = False) -> dict:
    validar_id(lote_id)
    prep = espacio.preparacion / lote_id
    marca = prep / "aplicado.json"
    if marca.is_file():  # ya guardado antes; si el original quedó sin apartar (corte a mitad), se termina
        hecho = json.loads(marca.read_text(encoding="utf-8"))
        if (espacio.entrada / f"{lote_id}.pdf").is_file():
            hecho["original_en_espera"] = str(_apartar_original(espacio, lote_id))
            marca.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
        if hecho.get("ultimo_secuencial") is not None:  # por si el corte fue antes de anotarlo
            espacio.registrar_ultimo(hecho["anio"], hecho["tipo"], hecho["ultimo_secuencial"])
        return hecho

    info, problemas = revalidar(espacio, lote_id)
    if problemas:
        raise Bloqueado(problemas)
    res = inf.resultado_desde_dict(info["resultado"])
    puede, motivos = puede_borrar_original(res, Verificacion())
    nota = entrada_aviso(espacio, lote_id)
    if nota:  # el escaneo dejó un aviso (p. ej. hojas sin tomar): también exige aceptación expresa
        puede, motivos = False, motivos + [nota]
    if not puede and not aceptar_revision:
        raise Bloqueado(["el lote necesita revisión y no se aceptó expresamente"] + motivos)

    destino = carpeta_destino(espacio, info["anio"], info["tipo"], mes, libro)
    destino.mkdir(parents=True, exist_ok=True)
    archivos = []
    for g in info["generados"]:
        final = _nombre_final(g["nombre"], lote_id)
        estado = _copiar_sin_pisar(prep / g["nombre"], destino / final, g["sha256"])
        archivos.append({"nombre": final, "origen": g["nombre"], "inicio": g["inicio"], "fin": g["fin"], "estado": estado})

    hecho = {
        "lote": lote_id,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "anio": info["anio"], "tipo": info["tipo"], "mes": mes, "libro": libro,
        "destino": str(destino),
        "archivos": archivos,
        "paginas": info["original"]["paginas"],
        "revision_aceptada": bool(not puede),
        "motivos_revision": motivos if not puede else [],
        "original_sha256": info["original"]["sha256"],
        "ultimo_secuencial": res.ultimo_secuencial,
    }
    tmp = prep / ".aplicado.json.tmp"
    tmp.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, marca)  # desde aquí el lote cuenta como guardado
    hecho["original_en_espera"] = str(_apartar_original(espacio, lote_id))
    marca.write_text(json.dumps(hecho, ensure_ascii=False, indent=2), encoding="utf-8")
    if res.ultimo_secuencial is not None:
        espacio.registrar_ultimo(info["anio"], info["tipo"], res.ultimo_secuencial)
    return hecho
