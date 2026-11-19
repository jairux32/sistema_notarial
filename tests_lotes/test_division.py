import pytest

from lotes.deteccion import detectar_pdf
from lotes.division import dividir, puede_borrar_original, verificar
from lotes.reglas import armar_actos

from .sintetico import cod, crear_libro

A, T = 2024, "P"


def libro_con_habilitantes(ruta):
    """8 páginas: acto 10 (págs 1-3, con habilitante de OTRA notaría en la 2), acto 11 (4-5, con habilitante PROPIO viejo en la 5),
    acto 12 (6-8). Todas las páginas llevan además la línea de factura y un número de 6 dígitos que no son códigos."""
    return crear_libro(
        ruta,
        [
            {"codigo": cod(A, T, 10), "titulo": True},
            {"ajenos": [cod(A, T, 99, notaria="1101003")]},
            {},
            {"codigo": cod(A, T, 11), "titulo": True},
            {"ajenos": [cod(2019, T, 7)]},
            {"codigo": cod(A, T, 12), "titulo": True},
            {},
            {},
        ],
    )


def test_lectura_real_de_codigos_de_barras(tmp_path):
    ruta = tmp_path / "libro.pdf"
    total = libro_con_habilitantes(ruta)
    n, dets = detectar_pdf(ruta)
    assert n == total == 8
    por_pagina = {d.pagina: d for d in dets}
    assert por_pagina[1].barras == (cod(A, T, 10),)
    assert cod(A, T, 99, notaria="1101003") in por_pagina[2].barras  # el ajeno SÍ se lee (se descarta por las reglas)
    assert 3 not in por_pagina  # página interior: nada que leer
    assert por_pagina[1].textos == (cod(A, T, 10),)  # el título confirma


def test_ciclo_completo_dividir_y_verificar(tmp_path):
    ruta = tmp_path / "libro.pdf"
    libro_con_habilitantes(ruta)
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    assert [(a.codigo.secuencial, a.inicio, a.fin) for a in res.actos] == [(10, 1, 3), (11, 4, 5), (12, 6, 8)]
    assert not res.requiere_revision
    gen = dividir(ruta, res, tmp_path / "preparacion")
    assert sorted(g.nombre for g in gen) == sorted(f"{cod(A, T, s)}.pdf" for s in (10, 11, 12))
    ver = verificar(ruta, res, gen)
    assert ver.correcta and ver.paginas_generadas == 8
    permitido, motivos = puede_borrar_original(res, ver)
    assert permitido and motivos == []
    assert not list((tmp_path / "preparacion").glob(".*.tmp"))  # no quedan temporales


def test_paginas_sin_codigo_al_inicio_no_se_pierden_y_bloquean_el_borrado(tmp_path):
    ruta = tmp_path / "libro.pdf"
    crear_libro(ruta, [{}, {}, {"codigo": cod(A, T, 5), "titulo": True}, {}])
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    gen = dividir(ruta, res, tmp_path / "prep")
    assert {g.nombre for g in gen} == {"SIN_CODIGO.pdf", f"{cod(A, T, 5)}.pdf"}
    ver = verificar(ruta, res, gen)
    assert ver.correcta and ver.paginas_generadas == 4  # no se perdió ninguna página
    permitido, motivos = puede_borrar_original(res, ver)
    assert not permitido and any("sin código" in m for m in motivos)


def test_verificacion_detecta_un_pdf_alterado(tmp_path):
    ruta = tmp_path / "libro.pdf"
    libro_con_habilitantes(ruta)
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    gen = dividir(ruta, res, tmp_path / "prep")
    # se reemplaza un acto por un PDF de otro contenido pero con el mismo número de páginas
    otro = tmp_path / "otro.pdf"
    crear_libro(otro, [{"codigo": cod(A, T, 10)}, {}, {}])
    gen[0].ruta.write_bytes(otro.read_bytes())
    ver = verificar(ruta, res, gen)
    assert not ver.correcta and any("no es idéntica" in p for p in ver.problemas)
    assert not puede_borrar_original(res, ver)[0]


def test_verificacion_detecta_un_pdf_faltante_o_truncado(tmp_path):
    ruta = tmp_path / "libro.pdf"
    libro_con_habilitantes(ruta)
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    gen = dividir(ruta, res, tmp_path / "prep")
    gen[1].ruta.write_bytes(b"%PDF-1.4 truncado")
    ver = verificar(ruta, res, gen)
    assert not ver.correcta and any("no se pudo abrir" in p or "páginas" in p for p in ver.problemas)


def test_no_pisa_archivos_existentes(tmp_path):
    ruta = tmp_path / "libro.pdf"
    libro_con_habilitantes(ruta)
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    dividir(ruta, res, tmp_path / "prep")
    with pytest.raises(FileExistsError):
        dividir(ruta, res, tmp_path / "prep")


def test_verificacion_detecta_que_falta_un_archivo_en_la_lista(tmp_path):
    ruta = tmp_path / "libro.pdf"
    libro_con_habilitantes(ruta)
    total, dets = detectar_pdf(ruta)
    res = armar_actos(dets, total, A, T)
    gen = dividir(ruta, res, tmp_path / "prep")
    ver = verificar(ruta, res, gen[:-1])  # se «olvidó» un acto en la lista
    assert not ver.correcta and any("suman" in p for p in ver.problemas)
