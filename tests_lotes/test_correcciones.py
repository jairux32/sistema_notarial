"""Correcciones confirmadas por una persona: se guardan en un archivo y se aplican solas en los análisis siguientes."""
import json
from pathlib import Path

import pytest

from lotes import correcciones
from lotes.cli import main

from .sintetico import cod, crear_libro

A = 2026


def _mundo(tmp_path):
    raiz = tmp_path / "esc"
    mes = raiz / "2026" / "DILIGENCIAS" / "Enero"
    mes.mkdir(parents=True)
    pdf = mes / "dili 1 enero 2026.pdf"
    crear_libro(pdf, [{"codigo": cod(A, "D", 1)}, {}, {"codigo": cod(A, "D", 3)}, {}])   # la hoja 2 es el 2 (sin código legible)
    return raiz, pdf, raiz / ".separador"


def _ir(capsys, *args):
    rc = main([str(a) for a in args])
    sal = capsys.readouterr()
    return rc, sal.out, sal.err


# ------------------------------------------------------------------ el archivo
def test_sin_archivo_no_hay_correcciones(tmp_path):
    assert correcciones.cargar(tmp_path / "no.json") == {}


def test_agregar_y_cargar_y_no_pierde_lo_anterior(tmp_path):
    ruta = tmp_path / "d" / "correcciones.json"
    correcciones.agregar(ruta, "2025/P/a.pdf", {25: "20251101007P00004"}, "confirmado en el papel")
    correcciones.agregar(ruta, "2025/P/a.pdf", {33: "20251101007P00005"})
    correcciones.agregar(ruta, "2025/P/b.pdf", {7: "20251101007P00009"})
    assert correcciones.cargar(ruta) == {"2025/P/a.pdf": {25: "20251101007P00004", 33: "20251101007P00005"},
                                         "2025/P/b.pdf": {7: "20251101007P00009"}}
    guardado = json.loads(ruta.read_text(encoding="utf-8"))["2025/P/a.pdf"]["25"]
    assert guardado["nota"] == "confirmado en el papel" and guardado["fecha"]
    assert not list(ruta.parent.glob(".*.tmp"))                        # sin restos del archivo temporal


def test_un_archivo_dañado_es_un_error_y_no_se_pisa(tmp_path):
    ruta = tmp_path / "correcciones.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        correcciones.cargar(ruta)
    with pytest.raises(ValueError):
        correcciones.agregar(ruta, "x.pdf", {1: "20261101007D00001"})
    assert ruta.read_text(encoding="utf-8") == "{esto no es json"


# ------------------------------------------------------------------ en la línea de comandos
def test_corregir_y_luego_serie_aplica_la_correccion_sola(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    rc, out, _ = _ir(capsys, "serie", raiz, "--anio", 2026, "--tipo", "D", "--nice", 0, "--sin-recuperar")
    assert rc == 1 and "faltan 00002" in out
    rc, out, _ = _ir(capsys, "corregir", pdf, "2=2", "--raiz", raiz, "--datos", datos, "--nota", "visto en el papel")
    assert rc == 0 and "hoja 2" in out and (datos / "correcciones.json").is_file()
    rc, out, _ = _ir(capsys, "serie", raiz, "--anio", 2026, "--tipo", "D", "--nice", 0, "--sin-recuperar")
    assert rc == 0 and "faltan" not in out and "1 libros sin observaciones" in out


def test_corregir_rechaza_lo_que_no_sirve_y_no_crea_el_archivo(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    for malo in ("2", "x=2", "2=abc", "2=20251101007D00002", "0=2"):
        rc, _, err = _ir(capsys, "corregir", pdf, malo, "--raiz", raiz, "--datos", datos)
        assert rc == 2 and err
    assert not (datos / "correcciones.json").exists()


def test_serie_con_archivo_de_correcciones_dañado_se_detiene(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    datos.mkdir()
    (datos / "correcciones.json").write_text("{mal", encoding="utf-8")
    rc, _, err = _ir(capsys, "serie", raiz, "--anio", 2026, "--tipo", "D", "--nice", 0)
    assert rc == 2 and "correcciones" in err


def test_una_correccion_de_otro_tipo_se_rechaza_al_aplicarla(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    correcciones.agregar(datos / "correcciones.json", "2026/DILIGENCIAS/Enero/dili 1 enero 2026.pdf", {2: "20261101007P00002"})
    rc, _, err = _ir(capsys, "serie", raiz, "--anio", 2026, "--tipo", "D", "--nice", 0)
    assert rc == 2 and "tipo D" in err


def test_aplicar_libro_usa_las_correcciones_guardadas(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    base = ["aplicar-libro", pdf, "--raiz", raiz, "--datos", datos, "--nice", 0, "--si", "--sin-recuperar"]
    rc, out, _ = _ir(capsys, *base)
    assert rc == 1 and "NO SE COLOCÓ NADA" in out and pdf.is_file()
    assert _ir(capsys, "corregir", pdf, "2=2", "--raiz", raiz, "--datos", datos)[0] == 0
    rc, out, _ = _ir(capsys, *base)
    assert rc == 0 and "COLOCADO: 3 archivos" in out
    assert sorted(p.name for p in (raiz / "2026" / "DILIGENCIAS" / "Enero" / "libro 1").glob("*.pdf")) == [
        cod(A, "D", s) + ".pdf" for s in (1, 2, 3)]


def test_simular_usa_las_correcciones_solo_si_se_le_piden(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    correcciones.agregar(datos / "correcciones.json", "2026/DILIGENCIAS/Enero/dili 1 enero 2026.pdf", {2: cod(A, "D", 2)})
    base = ["simular", pdf, "--anio", 2026, "--tipo", "D", "--nice", 0, "--sin-recuperar"]
    assert _ir(capsys, *base)[0] == 1                                                              # sin pedirlas, no se aplican
    assert _ir(capsys, *base, "--raiz", raiz, "--correcciones", datos / "correcciones.json")[0] == 0


def test_se_puede_usar_otro_archivo_de_correcciones(tmp_path, capsys):
    raiz, pdf, datos = _mundo(tmp_path)
    otro = tmp_path / "mias.json"
    assert _ir(capsys, "corregir", pdf, "2=2", "--raiz", raiz, "--datos", datos, "--correcciones", otro)[0] == 0
    assert otro.is_file() and not (datos / "correcciones.json").exists()
    base = ["serie", raiz, "--anio", 2026, "--tipo", "D", "--nice", 0, "--sin-recuperar"]
    assert _ir(capsys, *base)[0] == 1                                       # el archivo de siempre no tiene nada
    assert _ir(capsys, *base, "--correcciones", otro)[0] == 0
