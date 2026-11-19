import itertools

from lotes.codigos import codigo_desde_sello_2014, codigos_en_texto, parse_codigo
from lotes.reglas import DeteccionPagina, armar_actos

A, T = 2024, "P"


def c(sec, anio=A, tipo=T, notaria="1101007"):
    return f"{anio}{notaria}{tipo}{sec:05d}"


def det(pagina, *barras, textos=()):
    return DeteccionPagina(pagina=pagina, barras=tuple(barras), textos=tuple(textos))


def cubre_todo(res):
    """Cada página del libro cae en exactamente un tramo."""
    paginas = []
    for ini, fin, _ in res.cobertura():
        assert ini <= fin
        paginas += range(ini, fin + 1)
    return paginas == list(range(1, res.total_paginas + 1))


# ---------------------------------------------------------------- códigos
def test_parse_codigo_valido_e_invalido():
    cod = parse_codigo("20201101007P00787")
    assert (cod.anio, cod.notaria, cod.tipo, cod.secuencial) == (2020, "1101007", "P", 787)
    assert parse_codigo("2020110100P00787") is None
    assert parse_codigo("20201101007X00787") is None
    assert parse_codigo("") is None


def test_texto_no_confunde_factura_ni_contador():
    texto = "Factura: 004-002-000056756   008429   PROTOCOLIZACIÓN 20201101007P00787 POSESIÓN"
    assert [x.texto for x in codigos_en_texto(texto)] == ["20201101007P00787"]


def test_texto_tolera_espacios_entre_bloques():
    assert codigos_en_texto("N° 2023 1101007 D 00618")[0].texto == "20231101007D00618"


def test_sello_2014_se_normaliza():
    assert codigo_desde_sello_2014("N°. 2014-11-01-07-P.   02181").texto == "20141101007P02181"
    assert codigo_desde_sello_2014("17354 1 sin sello") is None


# ---------------------------------------------------------------- armado de actos
def test_libro_simple_tres_actos():
    r = armar_actos([det(1, c(10)), det(3, c(11)), det(4, c(12))], total_paginas=6, anio=A, tipo=T)
    assert [(a.codigo.secuencial, a.inicio, a.fin) for a in r.actos] == [(10, 1, 2), (11, 3, 3), (12, 4, 6)]
    assert not r.requiere_revision and cubre_todo(r)


def test_habilitante_de_otra_notaria_no_abre_acto():
    r = armar_actos([det(1, c(10)), det(2, c(77, notaria="1101003")), det(4, c(11))], 5, A, T)
    assert [a.codigo.secuencial for a in r.actos] == [10, 11]
    assert r.actos[0].fin == 3  # la página del habilitante queda dentro del acto 10
    assert r.ajenos == [(2, c(77, notaria="1101003"), "otra notaría")]
    assert not r.requiere_revision


def test_habilitante_propio_de_otro_anio_o_tipo_o_secuencial_menor():
    r = armar_actos(
        [det(1, c(50)), det(2, c(3, anio=2019)), det(3, c(8, tipo="D")), det(4, c(20)), det(5, c(51))],
        total_paginas=6,
        anio=A,
        tipo=T,
    )
    assert [a.codigo.secuencial for a in r.actos] == [50, 51]
    motivos = [m for _, _, m in r.ajenos]
    assert len(motivos) == 3 and all("habilitante propio" in m for m in motivos)
    assert not r.requiere_revision and cubre_todo(r)


def test_codigo_repetido_del_acto_abierto_no_abre_otro():
    r = armar_actos([det(1, c(10)), det(2, c(10))], 3, A, T)
    assert len(r.actos) == 1 and r.actos[0].fin == 3
    assert "repite" in r.ajenos[0][2]


def test_salto_de_numeracion_pide_revision():
    r = armar_actos([det(1, c(10)), det(2, c(13))], 3, A, T)
    assert r.saltos == ["faltan 00011–00012 antes de " + c(13) + " (página 2)"]
    assert r.requiere_revision
    r2 = armar_actos([det(1, c(10)), det(2, c(12))], 3, A, T)
    assert "faltan 00011 antes" in r2.saltos[0]


def test_paginas_antes_del_primer_codigo_se_conservan():
    r = armar_actos([det(3, c(10)), det(5, c(11))], 6, A, T)
    assert r.huerfanas == (1, 2)
    assert r.requiere_revision and cubre_todo(r)
    assert r.cobertura()[0] == (1, 2, "SIN_CODIGO")


def test_libro_sin_codigos_no_pierde_paginas():
    r = armar_actos([], 4, A, T)
    assert r.requiere_revision and r.huerfanas == (1, 4) and cubre_todo(r)


def test_secuencial_mayor_a_999_funciona():
    r = armar_actos([det(1, c(999)), det(2, c(1000)), det(3, c(1001))], 4, A, T)
    assert [a.codigo.secuencial for a in r.actos] == [999, 1000, 1001] and not r.requiere_revision


def test_dos_codigos_validos_en_la_misma_pagina_se_marcan():
    r = armar_actos([det(1, c(10), c(11))], 2, A, T)
    assert r.actos[0].codigo.secuencial == 10 and r.actos[0].confianza == "baja"
    assert r.requiere_revision and "además de" in r.avisos[0]


def test_barras_mandan_sobre_texto_pero_el_conflicto_se_marca():
    r = armar_actos([det(1, c(10), textos=[f"N° {c(18)}"])], 2, A, T)
    assert r.actos[0].codigo.secuencial == 10  # las barras son más fiables que el OCR
    assert r.actos[0].confianza == "baja" and r.requiere_revision


def test_barras_y_texto_que_coinciden_dan_confianza_alta():
    r = armar_actos([det(1, c(10), textos=[f"PROTOCOLIZACIÓN N° {c(10)}"])], 2, A, T)
    assert r.actos[0].confianza == "alta" and not r.requiere_revision


def test_solo_texto_sirve_con_confianza_media():
    r = armar_actos([det(1, textos=[f"N° {c(10)}"])], 2, A, T)
    assert r.actos[0].confianza == "media" and not r.requiere_revision


def test_continuidad_entre_libros_con_ultimo_previo():
    libro1 = armar_actos([det(1, c(1)), det(2, c(2))], 3, A, T)
    libro2 = armar_actos([det(1, c(3)), det(2, c(4))], 3, A, T, ultimo_previo=libro1.ultimo_secuencial)
    assert not libro2.requiere_revision
    # un habilitante con número viejo al inicio del libro 2 no abre acto
    libro2b = armar_actos([det(1, c(2)), det(2, c(3))], 3, A, T, ultimo_previo=2)
    assert libro2b.huerfanas == (1, 1) and libro2b.actos[0].codigo.secuencial == 3
    # y un salto entre libros se detecta
    libro2c = armar_actos([det(1, c(6))], 2, A, T, ultimo_previo=2)
    assert libro2c.saltos


def test_cobertura_completa_en_muchas_combinaciones():
    # cualquier mezcla de páginas con código, con habilitantes y huérfanas debe cubrir todas las páginas una sola vez
    total = 8
    for marcadas in itertools.chain.from_iterable(itertools.combinations(range(1, total + 1), k) for k in range(0, 5)):
        dets = [det(p, c(100 + i)) for i, p in enumerate(marcadas)]
        dets.append(det(max(1, total - 1), c(5, anio=2010)))
        r = armar_actos(dets, total, A, T)
        assert cubre_todo(r), (marcadas, r.cobertura())


def test_el_anio_distinto_se_rechaza_aunque_el_secuencial_sea_mayor():
    # un poder propio de 2019 con número ALTO: solo el año lo delata
    r = armar_actos([det(1, c(10)), det(2, c(900, anio=2019)), det(3, c(11))], 4, A, T)
    assert [a.codigo.secuencial for a in r.actos] == [10, 11]
    assert "año 2019" in r.ajenos[0][2]


def test_la_letra_distinta_se_rechaza_aunque_el_secuencial_sea_mayor():
    r = armar_actos([det(1, c(10)), det(2, c(900, tipo="D")), det(3, c(11))], 4, A, T)
    assert [a.codigo.secuencial for a in r.actos] == [10, 11]
    assert "tipo D" in r.ajenos[0][2]


def test_las_barras_mandan_aunque_el_texto_lea_un_numero_menor():
    # el OCR leyó 11 (mal) y las barras 12: debe ganar el código de barras
    r = armar_actos([det(1, c(12), textos=[f"N° {c(11)}"])], 2, A, T)
    assert r.actos[0].codigo.secuencial == 12 and r.requiere_revision
