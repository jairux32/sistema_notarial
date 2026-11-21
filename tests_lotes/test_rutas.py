import pytest

from lotes.rutas import mes_de, parse_ruta, plano, tipo_de


@pytest.mark.parametrize("nombre,esperado", [
    ("10. Octubre", 10), ("10. Octubre 2014", 10), ("9 Septiembre", 9), ("ENERO", 1), ("Febrero", 2),
    ("SEPTIEMBRE", 9), ("setiembre", 9), ("4.- Abril", 4), ("Libro 1", None), ("DEL 02 AL 06 DE ENERO", 1),
])
def test_mes_de(nombre, esperado):
    assert mes_de(nombre) == esperado


@pytest.mark.parametrize("nombre,esperado", [
    ("PROTOCOLOS", "P"), ("PROTOCOLOS 2015", "P"), ("Diligencias", "D"), ("DILIGENCIAS 2015", "D"),
    ("CERTIFICACIONES", "C"), ("ARRIENDOS 2024", "A"), ("OTROS", "O"), ("ARCHIVO", None), ("", None),
])
def test_tipo_de(nombre, esperado):
    assert tipo_de(nombre) == esperado


def test_plano_quita_tildes_y_signos():
    assert plano("  4.- Mayo / Protocolización ") == "4 mayo protocolizacion"


def test_ruta_normal_2019_en_adelante():
    r = parse_ruta("2022/PROTOCOLOS/3. Marzo/libro 12/libro12.pdf")
    assert (r.anio, r.tipo, r.mes, r.libro, r.archivo) == (2022, "P", 3, "libro 12", "libro12.pdf")
    assert r.ok and r.serie == (2022, "P")


def test_ruta_con_barras_de_windows():
    r = parse_ruta("2018\\DILIGENCIAS\\8. Agosto\\libro 2\\x.pdf")
    assert (r.anio, r.tipo, r.mes, r.libro) == (2018, "D", 8, "libro 2") and r.ok


def test_mes_con_el_año_dentro_y_libro_en_mayusculas():
    r = parse_ruta("2014/PROTOCOLOS/10. Octubre 2014/Libro88/a.pdf")
    assert (r.mes, r.libro) == (10, "Libro88") and r.ok


def test_libro_por_rango_de_fechas_2014():
    r = parse_ruta("2014/PROTOCOLOS/1. Enero 2014/DEL 02 AL 06 DE ENERO/0001.pdf")
    assert (r.mes, r.libro) == (1, "DEL 02 AL 06 DE ENERO") and r.ok


def test_pdf_directo_en_la_carpeta_del_mes():
    r = parse_ruta("2016/PROTOCOLOS/5. Mayo/pagina_001.pdf")
    assert (r.mes, r.libro) == (5, None) and r.ok


def test_libro_directamente_bajo_el_tipo_sin_mes():
    r = parse_ruta("2023/OTROS/Libro 1/x.pdf")
    assert (r.mes, r.libro) == (None, "Libro 1") and r.ok


def test_tipo_con_el_año_pegado():
    assert parse_ruta("2015/DILIGENCIAS 2015/1. Enero/libro1/x.pdf").tipo == "D"
    assert parse_ruta("2024/ARRIENDOS 2024/x.pdf").tipo == "A"


@pytest.mark.parametrize("ruta", [
    "suelto.pdf",                       # sin carpetas
    "ARCHIVO/2020/x.pdf",               # la primera no es un año
    "2020/x.pdf",                       # falta el tipo
    "2020/PAPELES/1. Enero/x.pdf",      # tipo desconocido
    "2020/PROTOCOLOS/varios/x.pdf",     # ni mes ni libro
])
def test_rutas_irregulares_se_marcan_y_no_se_adivinan(ruta):
    r = parse_ruta(ruta)
    assert not r.ok and r.problemas


def test_orden_natural_de_los_libros():
    rutas = [parse_ruta(x) for x in (
        "2014/PROTOCOLOS/11. Noviembre 2014/LIBRO100/a.pdf",
        "2014/PROTOCOLOS/10. Octubre 2014/libro89/a.pdf",
        "2014/PROTOCOLOS/10. Octubre 2014/Libro88/a.pdf",
        "2014/PROTOCOLOS/11. Noviembre 2014/LIBRO99/a.pdf",
    )]
    orden = [r.libro for r in sorted(rutas, key=lambda r: r.orden)]
    assert orden == ["Libro88", "libro89", "LIBRO99", "LIBRO100"]   # 99 antes que 100 (no por texto)


def test_orden_por_el_numero_del_nombre_aunque_haya_erratas():
    nombres = ["dili 4 julio 2026.pdf", "dilli 3 julio 2026.pdf", "dili 1 julio 2026.pdf", "dili 2 julio 2026.pdf"]
    rutas = [parse_ruta(f"2026/DILIGENCIAS/Julio/{n}") for n in nombres]
    assert [r.archivo[:7] for r in sorted(rutas, key=lambda r: r.orden)] == ["dili 1 ", "dili 2 ", "dilli 3", "dili 4 "]
    mezcla = [parse_ruta(f"2025/PROTOCOLOS/Febrero/{n}") for n in ("proto 3 febrero 2025.pdf", "prot 4 febrero 2025.pdf",
                                                                    "prot 1 febrero 2025.pdf", "proto 5 febrero 2025.pdf")]
    assert [r.archivo.split()[1] for r in sorted(mezcla, key=lambda r: r.orden)] == ["1", "3", "4", "5"]
