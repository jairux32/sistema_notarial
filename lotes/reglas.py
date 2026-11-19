"""Reglas para armar los actos de un libro a partir de los códigos hallados página por página.

Es lógica pura (sin PDF, sin OCR, sin disco): recibe lo que se leyó de cada página y devuelve los actos, lo que se
descartó y por qué, y si el libro necesita revisión humana. Así se puede probar a fondo.

Reglas (decididas con la notaría, 19-nov-2026):
  · El código del acto va SIEMPRE en la primera página del acto; las demás páginas no lo llevan.
  · Solo cuenta un código de la Notaría Séptima (1101007). Los de otras notarías (habilitantes) se anotan como «ajenos»
    y la página queda dentro del acto abierto.
  · Los habilitantes de la propia notaría SÍ traen código 1101007, y son frecuentes. Como son documentos ya emitidos,
    casi siempre llevan un año anterior, otra letra o un secuencial menor. Un acto nuevo exige: mismo año y mismo tipo
    que el libro, y un secuencial MAYOR que el último acto abierto. Lo demás se anota como habilitante propio.
  · Nada se pierde en silencio: las páginas anteriores al primer código se conservan como «huérfanas», y cualquier
    salto de numeración, conflicto o duda deja el libro «para revisión» (los originales no se borran).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .codigos import NOTARIA_PROPIA, Codigo, parse_codigo


@dataclass(frozen=True)
class DeteccionPagina:
    """Lo leído en una página. `barras` y `textos` son cadenas crudas (ya extraídas de la página)."""

    pagina: int  # 1 = primera página del PDF
    barras: tuple[str, ...] = ()
    textos: tuple[str, ...] = ()


@dataclass
class Acto:
    codigo: Codigo
    inicio: int
    fin: int
    confianza: str  # 'alta' = barras y texto coinciden · 'media' = una sola fuente · 'baja' = fuentes en conflicto
    avisos: list[str] = field(default_factory=list)

    @property
    def paginas(self) -> int:
        return self.fin - self.inicio + 1


@dataclass
class Resultado:
    actos: list[Acto]
    total_paginas: int
    huerfanas: tuple[int, int] | None  # páginas anteriores al primer acto
    ajenos: list[tuple[int, str, str]]  # (página, código, motivo): códigos que NO abren acto
    saltos: list[str]  # huecos de numeración: «faltan 00011–00012 antes de 00013»
    avisos: list[str]
    ultimo_secuencial: int | None

    @property
    def requiere_revision(self) -> bool:
        return bool(
            not self.actos
            or self.huerfanas
            or self.saltos
            or self.avisos
            or any(a.confianza == "baja" for a in self.actos)
        )

    def cobertura(self) -> list[tuple[int, int, str]]:
        """Reparte TODAS las páginas: cada una cae en exactamente un tramo (huérfanas o acto)."""
        tramos: list[tuple[int, int, str]] = []
        if self.huerfanas:
            tramos.append((self.huerfanas[0], self.huerfanas[1], "SIN_CODIGO"))
        for a in self.actos:
            tramos.append((a.inicio, a.fin, a.codigo.texto))
        return tramos


def _candidatos(d: DeteccionPagina) -> dict[str, tuple[Codigo, set[str]]]:
    """Códigos con forma válida de la página: texto -> (Codigo, fuentes {'barras','texto'})."""
    from .codigos import codigos_en_texto

    res: dict[str, tuple[Codigo, set[str]]] = {}
    for crudo in d.barras:
        cod = parse_codigo(crudo)
        if cod:
            res.setdefault(cod.texto, (cod, set()))[1].add("barras")
    for crudo in d.textos:
        for cod in codigos_en_texto(crudo) or ([parse_codigo(crudo)] if parse_codigo(crudo) else []):
            res.setdefault(cod.texto, (cod, set()))[1].add("texto")
    return res


def armar_actos(
    detecciones: list[DeteccionPagina],
    total_paginas: int,
    anio: int,
    tipo: str,
    ultimo_previo: int | None = None,
    notaria: str = NOTARIA_PROPIA,
) -> Resultado:
    """Arma los actos de un libro.

    `anio` y `tipo` (P/D/C/A/O) vienen de la carpeta. `ultimo_previo` es el último secuencial del libro anterior de la
    misma serie (año+tipo); None si es el primer libro que se procesa de esa serie.
    """
    por_pagina = {d.pagina: d for d in detecciones}
    ultimo = ultimo_previo
    actos: list[Acto] = []
    ajenos: list[tuple[int, str, str]] = []
    saltos: list[str] = []
    avisos: list[str] = []

    for pagina in range(1, total_paginas + 1):
        d = por_pagina.get(pagina)
        if d is None:
            continue
        validos: list[tuple[Codigo, set[str]]] = []
        for texto, (cod, fuentes) in _candidatos(d).items():
            if cod.notaria != notaria:
                ajenos.append((pagina, texto, "otra notaría"))
            elif cod.anio != anio:
                ajenos.append((pagina, texto, f"año {cod.anio} distinto del libro ({anio}): habilitante propio"))
            elif cod.tipo != tipo:
                ajenos.append((pagina, texto, f"tipo {cod.tipo} distinto del libro ({tipo}): habilitante propio"))
            elif ultimo is not None and cod.secuencial == ultimo:
                ajenos.append((pagina, texto, "repite el código del acto abierto (no abre otro acto)"))
            elif ultimo is not None and cod.secuencial < ultimo:
                ajenos.append(
                    (pagina, texto, f"secuencial {cod.secuencial:05d} no supera al último ({ultimo:05d}): habilitante propio")
                )
            else:
                validos.append((cod, fuentes))
        if not validos:
            continue

        # Si hay lectura de código de barras, manda sobre el texto (el OCR se equivoca más).
        con_barras = [v for v in validos if "barras" in v[1]]
        elegidos = con_barras or validos
        elegidos.sort(key=lambda v: v[0].secuencial)
        cod, fuentes = elegidos[0]
        aviso_acto: list[str] = []
        confianza = "alta" if {"barras", "texto"} <= fuentes else "media"

        otros = [v for v in validos if v[0].texto != cod.texto]
        if otros:
            # dos códigos aceptables en la misma página, o barras y texto que no coinciden
            confianza = "baja"
            detalle = ", ".join(o[0].texto for o in otros)
            msg = f"página {pagina}: además de {cod.texto} se leyó {detalle}; se tomó {cod.texto}"
            aviso_acto.append(msg)
            avisos.append(msg)

        if ultimo is not None and cod.secuencial > ultimo + 1:
            faltan = (
                f"{ultimo + 1:05d}"
                if cod.secuencial == ultimo + 2
                else f"{ultimo + 1:05d}–{cod.secuencial - 1:05d}"
            )
            saltos.append(f"faltan {faltan} antes de {cod.texto} (página {pagina})")

        actos.append(Acto(cod, inicio=pagina, fin=total_paginas, confianza=confianza, avisos=aviso_acto))
        ultimo = cod.secuencial

    for i, acto in enumerate(actos[:-1]):
        acto.fin = actos[i + 1].inicio - 1

    huerfanas = (1, actos[0].inicio - 1) if actos and actos[0].inicio > 1 else None
    if not actos and total_paginas:
        huerfanas = (1, total_paginas)
        avisos.append("no se encontró ningún código de acto en el libro")

    return Resultado(
        actos=actos,
        total_paginas=total_paginas,
        huerfanas=huerfanas,
        ajenos=ajenos,
        saltos=saltos,
        avisos=avisos,
        ultimo_secuencial=ultimo,
    )
