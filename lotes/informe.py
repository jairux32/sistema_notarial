"""Informe de una división: se guarda como JSON junto a los PDF generados y se puede releer para verificar después.

Escritura atómica (archivo temporal + renombrado): nunca queda un informe a medias.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .codigos import parse_codigo
from .reglas import Acto, Resultado

VERSION = 1
NOMBRE = "informe.json"


def sha256_archivo(ruta: str | Path, bloque: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            b = f.read(bloque)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def resultado_a_dict(res: Resultado) -> dict:
    return {
        "total_paginas": res.total_paginas,
        "actos": [
            {"codigo": a.codigo.texto, "inicio": a.inicio, "fin": a.fin, "confianza": a.confianza, "avisos": a.avisos}
            for a in res.actos
        ],
        "huerfanas": list(res.huerfanas) if res.huerfanas else None,
        "ajenos": [list(x) for x in res.ajenos],
        "saltos": res.saltos,
        "avisos": res.avisos,
        "ultimo_secuencial": res.ultimo_secuencial,
    }


def resultado_desde_dict(d: dict) -> Resultado:
    actos = []
    for a in d["actos"]:
        cod = parse_codigo(a["codigo"])
        if cod is None:
            raise ValueError(f"código ilegible en el informe: {a['codigo']!r}")
        actos.append(Acto(cod, a["inicio"], a["fin"], a["confianza"], list(a.get("avisos", []))))
    return Resultado(
        actos=actos,
        total_paginas=d["total_paginas"],
        huerfanas=tuple(d["huerfanas"]) if d.get("huerfanas") else None,
        ajenos=[tuple(x) for x in d.get("ajenos", [])],
        saltos=list(d.get("saltos", [])),
        avisos=list(d.get("avisos", [])),
        ultimo_secuencial=d.get("ultimo_secuencial"),
    )


def guardar(carpeta: str | Path, info: dict) -> Path:
    carpeta = Path(carpeta)
    destino = carpeta / NOMBRE
    tmp = carpeta / f".{NOMBRE}.tmp"
    tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, destino)
    return destino


def cargar(ruta: str | Path) -> dict:
    ruta = Path(ruta)
    if ruta.is_dir():
        ruta = ruta / NOMBRE
    info = json.loads(ruta.read_text(encoding="utf-8"))
    if info.get("version") != VERSION:
        raise ValueError(f"versión de informe desconocida: {info.get('version')!r}")
    return info


def texto(info: dict) -> str:
    """Informe legible, en español."""
    o = info["original"]
    r = info["resultado"]
    L = [
        f"LIBRO: {o['ruta']}",
        f"  {r['total_paginas']} páginas · {o['bytes']:,} bytes · sha256 {o['sha256'][:16]}…".replace(",", "."),
        f"  serie {info['anio']} tipo {info['tipo']}"
        + (f" · último secuencial anterior: {info['ultimo_previo']:05d}" if info.get("ultimo_previo") is not None else ""),
        "",
        "ACTOS DETECTADOS:",
    ]
    if r.get("huerfanas"):
        a, b = r["huerfanas"]
        L.append(f"  páginas {a}-{b}  →  SIN_CODIGO.pdf  (anteriores al primer código: se conservan)")
    for a in r["actos"]:
        L.append(f"  páginas {a['inicio']}-{a['fin']}  →  {a['codigo']}.pdf  ({a['fin'] - a['inicio'] + 1} pág., confianza {a['confianza']})")
        L += [f"      aviso: {x}" for x in a.get("avisos", [])]
    if not r["actos"]:
        L.append("  (ninguno)")
    if r["ajenos"]:
        L += ["", "CÓDIGOS QUE NO ABREN ACTO (habilitantes u otras notarías):"]
        L += [f"  página {p}: {c} — {m}" for p, c, m in r["ajenos"]]
    if r["saltos"]:
        L += ["", "HUECOS DE NUMERACIÓN:"] + [f"  {s}" for s in r["saltos"]]
    if r["avisos"]:
        L += ["", "AVISOS:"] + [f"  {s}" for s in r["avisos"]]
    if info.get("generados"):
        L += ["", f"ARCHIVOS GENERADOS en {info.get('preparacion', '?')}:"]
        L += [f"  {g['nombre']}  (páginas {g['inicio']}-{g['fin']}, {g['bytes']:,} bytes)".replace(",", ".") for g in info["generados"]]
    v = info.get("verificacion")
    if v is not None:
        L += ["", "VERIFICACIÓN: " + ("CORRECTA" if v["correcta"] else "CON PROBLEMAS")]
        L += [f"  - {p}" for p in v["problemas"]]
        L.append(f"  páginas originales {v['paginas_originales']} · generadas {v['paginas_generadas']}")
    L += ["", "¿SE PUEDE BORRAR EL ORIGINAL? " + ("sí, previa aprobación de una persona" if info.get("puede_borrar_original") else "NO")]
    if not info.get("puede_borrar_original"):
        L += [f"  - {m}" for m in info.get("motivos", [])]
    L.append("(Este programa nunca borra el original: lo decide y lo hace una persona.)")
    return "\n".join(L) + "\n"
