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
  · Un código con número MUY ADELANTADO que aparece suelto (la numeración sigue sin él) no abre acto: si se tomara como
    bueno, haría descartar como «habilitantes» todos los actos reales que vienen después (medido en 2026: un `…00260`
    suelto en la hoja 1013 dejó dos libros enteros «sin actos»). Se decide mirando la secuencia completa del libro (y
    el comienzo del libro siguiente, si se conoce): se conserva la cadena creciente más larga y lo demás se anota
    como «fuera de orden» y deja el libro para revisión.
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
    # (primer número que falta, último, primera hoja donde puede estar, última hoja): sirve para buscar ahí con más esfuerzo
    huecos: list[tuple[int, int, int, int]] = field(default_factory=list)

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


def _representante(d: DeteccionPagina, anio: int, tipo: str, notaria: str) -> Codigo | None:
    """El código que esa página propondría como acto (de la notaría, año y tipo del libro), sin mirar el orden."""
    validos = [(c, f) for c, f in _candidatos(d).values() if c.notaria == notaria and c.anio == anio and c.tipo == tipo]
    if not validos:
        return None
    con_barras = [v for v in validos if "barras" in v[1]]
    return min((con_barras or validos), key=lambda v: v[0].secuencial)[0]


def secuenciales_validos(detecciones: list[DeteccionPagina], anio: int, tipo: str, notaria: str = NOTARIA_PROPIA) -> list[int]:
    """Secuenciales que propone cada página (en orden de página). Sirve para dejar ver el comienzo del libro siguiente."""
    reps = (_representante(d, anio, tipo, notaria) for d in sorted(detecciones, key=lambda d: d.pagina))
    return [r.secuencial for r in reps if r]


def _cadena_creciente(elementos: list[tuple[int | None, int]]) -> set[int]:
    """Páginas de la cadena estrictamente creciente más larga de `elementos` = [(página o None, secuencial)].

    Entre cadenas igual de largas gana la más «apretada» (menor último − primero: la que sigue la numeración sin saltos);
    entre repetidos, el primero. El último secuencial del libro anterior entra como primer elemento (página 0), así que la
    cadena lo sigue a él.
    Los elementos con página None (del libro siguiente) o 0 (el ancla) cuentan para decidir pero no se devuelven.
    """
    n = len(elementos)
    if n == 0:
        return set()
    largo = [1] * n
    ultimo = [elementos[i][1] for i in range(n)]  # secuencial final de la mejor cadena que empieza en i
    siguiente = [-1] * n
    for i in range(n - 1, -1, -1):
        mejor = -1
        for j in range(i + 1, n):
            if elementos[j][1] <= elementos[i][1]:
                continue
            if mejor < 0 or (largo[j], -ultimo[j]) > (largo[mejor], -ultimo[mejor]):
                mejor = j
        if mejor >= 0:
            largo[i], ultimo[i], siguiente[i] = 1 + largo[mejor], ultimo[mejor], mejor
    inicio = min(range(n), key=lambda i: (-largo[i], ultimo[i] - elementos[i][1], i))
    paginas: set[int] = set()
    i = inicio
    while i >= 0:
        pag = elementos[i][0]
        if pag:
            paginas.add(pag)
        i = siguiente[i]
    return paginas


def armar_actos(
    detecciones: list[DeteccionPagina],
    total_paginas: int,
    anio: int,
    tipo: str,
    ultimo_previo: int | None = None,
    notaria: str = NOTARIA_PROPIA,
    siguientes: list[int] | None = None,
    manuales: dict[int, str] | None = None,
    recuperados: dict[int, str] | None = None,
) -> Resultado:
    """Arma los actos de un libro.

    `anio` y `tipo` (P/D/C/A/O) vienen de la carpeta. `ultimo_previo` es el último secuencial del libro anterior de la
    misma serie (año+tipo); None si es el primer libro que se procesa de esa serie. `siguientes` son los secuenciales
    del comienzo del libro que sigue (ver `secuenciales_validos`), solo para reconocer códigos sueltos al final.
    `manuales` {hoja: código} lo puso una persona y manda sobre lo leído; `recuperados` los halló una segunda lectura con más
    esfuerzo en el hueco de la numeración (dejan el libro para revisión).
    """
    corregidas = {**(recuperados or {}), **(manuales or {})}
    if corregidas:
        detecciones = [d for d in detecciones if d.pagina not in corregidas] + [
            DeteccionPagina(pagina=p, barras=(t,)) for p, t in corregidas.items()]
    por_pagina = {d.pagina: d for d in detecciones}

    # Orden de la numeración: qué páginas siguen la cadena creciente y cuáles traen un código suelto fuera de ella.
    elementos: list[tuple[int | None, int]] = [(0, ultimo_previo)] if ultimo_previo is not None else []
    for d in sorted(detecciones, key=lambda d: d.pagina):
        r = _representante(d, anio, tipo, notaria)
        if r and (ultimo_previo is None or r.secuencial > ultimo_previo):
            elementos.append((d.pagina, r.secuencial))
    extra = [(None, s) for s in (siguientes or []) if ultimo_previo is None or s > ultimo_previo]
    en_cadena = _cadena_creciente(elementos + extra)
    fuera_de_orden = {p for p, _ in elementos if p and p not in en_cadena}
    ultimo = ultimo_previo
    actos: list[Acto] = []
    ajenos: list[tuple[int, str, str]] = []
    saltos: list[str] = []
    huecos: list[tuple[int, int, int, int]] = []  # (desde, hasta, hoja inicial, hoja final) de cada salto
    avisos: list[str] = []

    for pagina in range(1, total_paginas + 1):
        d = por_pagina.get(pagina)
        if d is None:
            continue
        validos: list[tuple[Codigo, set[str]]] = []
        suelto = False
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
            elif pagina in fuera_de_orden:
                ajenos.append((pagina, texto, "fuera de orden: la numeración sigue sin él; se trató como habilitante propio"))
                suelto = True
            else:
                validos.append((cod, fuentes))
        if suelto:
            avisos.append(f"página {pagina}: hay un código fuera de orden (no se tomó como acto nuevo); confirme que es un habilitante")
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
            huecos.append((ultimo + 1, cod.secuencial - 1, (actos[-1].inicio + 1) if actos else 1, pagina - 1))

        actos.append(Acto(cod, inicio=pagina, fin=total_paginas, confianza=confianza, avisos=aviso_acto))
        ultimo = cod.secuencial

    # Un número que «falta» puede estar en el libro pero fuera de orden (p. ej. 811 en la hoja 191, detrás del 812):
    # se dice, para que la persona lo busque ahí y no en el archivo físico entero.
    if huecos:
        presentes: dict[int, list[int]] = {}
        for p, texto, _ in ajenos:
            c = parse_codigo(texto)
            if c and c.notaria == notaria and c.anio == anio and c.tipo == tipo:
                presentes.setdefault(c.secuencial, []).append(p)
        for k, (desde, hasta, _, _) in enumerate(huecos):
            donde = [f"el {n:05d} aparece en la página {presentes[n][0]}, fuera de orden"
                     for n in range(desde, hasta + 1) if n in presentes][:5]
            if donde:
                saltos[k] += " — " + "; ".join(donde)

    for i, acto in enumerate(actos[:-1]):
        acto.fin = actos[i + 1].inicio - 1

    for acto in actos:
        if acto.inicio in (manuales or {}):
            acto.avisos.append(f"el código de la hoja {acto.inicio} lo puso una persona")
        elif acto.inicio in (recuperados or {}):
            msg = (f"hoja {acto.inicio}: el código {acto.codigo.texto} se recuperó leyendo la hoja con más esfuerzo "
                   f"(el primer paso no lo leyó); confirme que es correcto")
            acto.avisos.append(msg)
            avisos.append(msg)

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
        huecos=huecos,
    )
