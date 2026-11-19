"""Formato de los códigos de acto de la Notaría Séptima de Loja (Resolución 202-2021 del Consejo de la Judicatura).

Código completo (17 caracteres):  AAAA + 1101007 + L + NNNNN
    AAAA     año del acto
    1101007  código de la notaría (provincia 11, cantón 01, notaría 007)
    L        P protocolos, D diligencias, C certificaciones, A arriendos, O otros
    NNNNN    secuencial dentro del año y del tipo

En 2014 el sello venía escrito de otro modo: «Nº. 2014-11-01-07-P.  02181» (sin código de barras); se normaliza al
mismo código de 17 caracteres.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NOTARIA_PROPIA = "1101007"
TIPOS = {
    "P": "PROTOCOLOS",
    "D": "DILIGENCIAS",
    "C": "CERTIFICACIONES",
    "A": "ARRIENDOS",
    "O": "OTROS",
}

_CODIGO = re.compile(r"^(\d{4})(\d{7})([PDCAO])(\d{5})$")
# En texto libre se toleran espacios entre bloques; los límites impiden tomar un trozo de un número más largo
# (por ejemplo «Factura: 004-002-000056756» o el contador de 6 dígitos de la esquina).
_CODIGO_EN_TEXTO = re.compile(r"(?<!\d)(\d{4})\s?(\d{7})\s?([PDCAO])\s?(\d{5})(?!\d)")
_SELLO_2014 = re.compile(
    r"(?<!\d)(20\d{2})\D{1,3}(\d{2})\D{1,3}(\d{2})\D{1,3}(\d{2})\D{1,3}([PDCAO])\D{1,4}(\d{5})(?!\d)"
)


@dataclass(frozen=True)
class Codigo:
    texto: str
    anio: int
    notaria: str
    tipo: str
    secuencial: int

    def __str__(self) -> str:  # pragma: no cover - comodidad
        return self.texto


def _armar(anio: str, notaria: str, tipo: str, secuencial: str) -> Codigo:
    return Codigo(
        texto=f"{anio}{notaria}{tipo}{secuencial}",
        anio=int(anio),
        notaria=notaria,
        tipo=tipo,
        secuencial=int(secuencial),
    )


def parse_codigo(texto: str) -> Codigo | None:
    """Interpreta un código ya limpio de 17 caracteres. None si no tiene esa forma."""
    m = _CODIGO.match((texto or "").strip().upper())
    return _armar(*m.groups()) if m else None


def codigos_en_texto(texto: str) -> list[Codigo]:
    """Todos los códigos con forma válida que aparecen en un texto (de cualquier notaría), sin repetir y en orden."""
    vistos: dict[str, Codigo] = {}
    for m in _CODIGO_EN_TEXTO.finditer((texto or "").upper()):
        cod = _armar(*m.groups())
        vistos.setdefault(cod.texto, cod)
    return list(vistos.values())


def codigo_desde_sello_2014(texto: str) -> Codigo | None:
    """Normaliza el sello de 2014 («Nº. 2014-11-01-07-P.  02181») al código de 17 caracteres."""
    m = _SELLO_2014.search((texto or "").upper())
    if not m:
        return None
    anio, prov, canton, notaria, tipo, sec = m.groups()
    return _armar(anio, f"{prov}{canton}0{notaria}", tipo, sec)
