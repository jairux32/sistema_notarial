"""Correcciones que una persona confirmó mirando el libro físico: «la hoja 25 de este PDF es el 00004».

Se guardan en un archivo (`correcciones.json`, junto a los datos del separador) para no depender de recordar las
opciones de la línea de comandos: todo análisis posterior del mismo libro las aplica solo.

Formato: { "2025/PROTOCOLOS/Enero/prot 1 enero 2025.pdf": { "25": {"codigo": "20251101007P00004", "nota": "…"} } }
Escritura atómica (archivo temporal + renombrar); nunca borra una corrección que no se le pida.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

NOMBRE = "correcciones.json"


def cargar(ruta: Path) -> dict[str, dict[int, str]]:
    """{ruta relativa del PDF: {hoja: código}}. Un archivo ausente es «sin correcciones»; uno dañado es un error."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return {}
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
        return {rel: {int(hoja): datos["codigo"] for hoja, datos in hojas.items()} for rel, hojas in crudo.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"el archivo de correcciones {ruta} no se puede leer ({type(e).__name__}); revíselo a mano") from e


def agregar(ruta: Path, relativa: str, hojas: dict[int, str], nota: str = "") -> None:
    """Suma (o reemplaza) correcciones de un PDF. `hojas` = {hoja: código completo}."""
    ruta = Path(ruta)
    crudo: dict = {}
    if ruta.is_file():
        crudo = json.loads(ruta.read_text(encoding="utf-8"))  # si está dañado, falla: no se pisa
    libro = crudo.setdefault(relativa, {})
    for hoja, codigo in hojas.items():
        libro[str(hoja)] = {"codigo": codigo, "nota": nota, "fecha": date.today().isoformat()}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name("." + ruta.name + ".tmp")
    tmp.write_text(json.dumps(crudo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, ruta)
