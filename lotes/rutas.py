"""Interpreta la ruta de un PDF del archivo escaneado: año, tipo (P/D/C/A/O), mes y libro.

El acervo real tiene nombres irregulares («10. Octubre 2014», «9 Septiembre», «ENERO», «ARRIENDOS 2024», «libro1»,
«LIBRO 3», «DEL 02 AL 06 DE ENERO»…). Aquí solo se mira el NOMBRE de las carpetas; no se abre ningún archivo.

Estructura esperada (relativa a la raíz del escaneo):  AÑO / TIPO / [MES] / [LIBRO] / archivo.pdf
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import PurePosixPath

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
TIPOS = {
    "protocolo": "P", "protocolos": "P",
    "diligencia": "D", "diligencias": "D",
    "certificacion": "C", "certificaciones": "C",
    "arriendo": "A", "arriendos": "A",
    "otro": "O", "otros": "O",
}
_LIBRO = re.compile(r"\blibros?\s*\d*|\bdel\s+\d+", re.I)  # «libro1», «LIBRO 3», «DEL 02 AL 06 DE ENERO»


def plano(texto: str) -> str:
    """Minúsculas, sin tildes ni signos: «10. Octubre 2014» → «10 octubre 2014»."""
    t = unicodedata.normalize("NFD", texto)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def mes_de(nombre: str) -> int | None:
    """Número de mes (1-12) que nombra una carpeta, o None. Acepta el nombre o el número delante («9 Septiembre»)."""
    p = plano(nombre)
    for palabra in p.split():
        if palabra in MESES:
            return MESES[palabra]
    return None


def tipo_de(nombre: str) -> str | None:
    p = re.sub(r"\d+", " ", plano(nombre)).strip()
    p = " ".join(p.split())
    return TIPOS.get(p)


def numeros(nombre: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", nombre))


@dataclass(frozen=True)
class RutaLibro:
    relativa: str
    anio: int | None
    tipo: str | None
    mes: int | None
    libro: str | None  # nombre de la carpeta del libro; None si el PDF está directamente en la del mes (o del tipo)
    archivo: str
    problemas: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.anio is not None and self.tipo is not None and not self.problemas

    @property
    def serie(self) -> tuple[int, str] | None:
        return (self.anio, self.tipo) if self.anio is not None and self.tipo else None

    @property
    def orden(self) -> tuple:
        """Clave para recorrer los libros de una serie en su orden natural (mes, números del libro, nombre)."""
        return (self.mes or 0, numeros(self.libro or ""), plano(self.libro or ""), plano(self.archivo))


def parse_ruta(relativa: str) -> RutaLibro:
    """`relativa` va con «/» o «\\» y sin la raíz. El último elemento es el archivo."""
    partes = [p for p in re.split(r"[\\/]+", relativa) if p]
    archivo = partes[-1] if partes else ""
    dirs = partes[:-1]
    rel = "/".join(partes)
    problemas: list[str] = []

    if not dirs or not re.fullmatch(r"(19|20)\d{2}", dirs[0]):
        return RutaLibro(rel, None, None, None, None, archivo, ("fuera del esquema: la primera carpeta no es un año",))
    anio = int(dirs[0])
    if len(dirs) < 2:
        return RutaLibro(rel, anio, None, None, None, archivo, ("falta la carpeta del tipo de acto",))
    tipo = tipo_de(dirs[1])
    if tipo is None:
        problemas.append(f"tipo no reconocido: «{dirs[1]}»")

    resto = dirs[2:]
    mes: int | None = None
    libro: str | None = None
    if resto:
        m = mes_de(resto[0])
        if m is not None:
            mes = m
            resto = resto[1:]
        elif not _LIBRO.search(plano(resto[0])):
            problemas.append(f"carpeta «{resto[0]}» no es un mes ni un libro")
    if resto:
        libro = "/".join(resto)
    return RutaLibro(rel, anio, tipo, mes, libro, archivo, tuple(problemas))
