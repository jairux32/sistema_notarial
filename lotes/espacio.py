"""Carpetas del flujo de entrada y reglas para ubicar cada acto en el archivo definitivo.

    DATOS/entrada/        PDF recién escaneados, esperando revisión
    DATOS/preparacion/    una carpeta por lote: los actos ya cortados + informe.json (+ aplicado.json al guardar)
    DATOS/espera/         el PDF original, apartado (NUNCA borrado) después de guardar los actos en el archivo
    DATOS/ultimos.json    último secuencial guardado por año y tipo (para encadenar la numeración entre lotes)
    ARCHIVO/              el escaneo definitivo:  AÑO / TIPO / Mes / libro N / CÓDIGO.pdf

Los nombres de las carpetas del archivo se reutilizan si ya existen (el archivo real tiene mayúsculas y números
irregulares); si no existen se crean con el nombre normal. Mes y libro llegan siempre como números ya validados, de modo
que ningún dato escrito por una persona forma parte de una ruta.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .codigos import TIPOS
from .rutas import mes_de, numeros, plano, tipo_de

NOMBRES_MES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
               "Noviembre", "Diciembre"]
ID_LOTE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


@dataclass(frozen=True)
class Espacio:
    datos: Path
    archivo: Path

    @property
    def entrada(self) -> Path:
        return self.datos / "entrada"

    @property
    def preparacion(self) -> Path:
        return self.datos / "preparacion"

    @property
    def espera(self) -> Path:
        return self.datos / "espera"

    def asegurar(self) -> "Espacio":
        for p in (self.entrada, self.preparacion, self.espera):
            p.mkdir(parents=True, exist_ok=True)
        return self

    # ---- último secuencial guardado por serie
    def _ruta_ultimos(self) -> Path:
        return self.datos / "ultimos.json"

    def ultimos(self) -> dict[str, int]:
        try:
            return {k: int(v) for k, v in json.loads(self._ruta_ultimos().read_text(encoding="utf-8")).items()}
        except (OSError, ValueError):
            return {}

    def ultimo(self, anio: int, tipo: str) -> int | None:
        return self.ultimos().get(f"{anio}{tipo}")

    def registrar_ultimo(self, anio: int, tipo: str, secuencial: int) -> None:
        datos = self.ultimos()
        clave = f"{anio}{tipo}"
        datos[clave] = max(datos.get(clave, 0), secuencial)
        tmp = self.datos / ".ultimos.json.tmp"
        tmp.write_text(json.dumps(datos, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self._ruta_ultimos())


def validar_id(lote_id: str) -> str:
    if not ID_LOTE.match(lote_id or ""):
        raise ValueError("identificador de lote no válido")
    return lote_id


def _hijo_que_cumple(padre: Path, cumple) -> Path | None:
    try:
        candidatos = sorted(p for p in padre.iterdir() if p.is_dir() and cumple(p.name))
    except OSError:
        return None
    return candidatos[0] if candidatos else None


def _es_libro(nombre: str, n: int) -> bool:
    return plano(nombre).startswith("libro") and numeros(nombre) == (n,)


def carpeta_destino(espacio: Espacio, anio: int, tipo: str, mes: int, libro: int) -> Path:
    """Ruta (no la crea) donde se guardan los actos: ARCHIVO/AÑO/TIPO/Mes/libro N, reutilizando carpetas existentes."""
    if tipo not in TIPOS:
        raise ValueError("tipo no válido")
    if not 1 <= mes <= 12:
        raise ValueError("mes no válido")
    if not 1 <= libro <= 999:
        raise ValueError("número de libro no válido")
    if not 1990 <= anio <= 2200:
        raise ValueError("año no válido")
    ruta = espacio.archivo / str(anio)
    for nombre_nuevo, cumple in (
        (TIPOS[tipo], lambda n: tipo_de(n) == tipo),
        (NOMBRES_MES[mes - 1], lambda n: mes_de(n) == mes),
        (f"libro {libro}", lambda n: _es_libro(n, libro)),
    ):
        existente = _hijo_que_cumple(ruta, cumple) if ruta.is_dir() else None
        ruta = existente or (ruta / nombre_nuevo)
    return ruta


def proponer(espacio: Espacio, anio: int, tipo: str, hoy: date | None = None) -> tuple[int, int]:
    """(mes, libro) sugeridos: el mes de hoy y el libro más alto que ya exista en esa carpeta (o el 1)."""
    hoy = hoy or date.today()
    mes = hoy.month
    ruta = espacio.archivo / str(anio)
    tipo_dir = _hijo_que_cumple(ruta, lambda n: tipo_de(n) == tipo) if ruta.is_dir() else None
    mes_dir = _hijo_que_cumple(tipo_dir, lambda n: mes_de(n) == mes) if tipo_dir else None
    libro = 1
    if mes_dir:
        for p in mes_dir.iterdir():
            if p.is_dir() and plano(p.name).startswith("libro") and len(numeros(p.name)) == 1:
                libro = max(libro, numeros(p.name)[0])
    return mes, libro
