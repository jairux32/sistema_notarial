"""Libros viejos: dividir, colocar cada acto en su carpeta y apartar el original sin borrarlo."""
import hashlib
from pathlib import Path

import pymupdf as fitz
import pytest

from lotes import antiguos
from lotes.aplicar import Bloqueado
from lotes.cli import main
from lotes.espacio import Espacio, validar_id

from .sintetico import cod, crear_libro

A = 2099


def _pag(sec=None):
    return {"codigo": cod(A, "P", sec), "titulo": True} if sec else {}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _arbol(p):
    return sorted(str(x.relative_to(p)) for x in Path(p).rglob("*"))


@pytest.fixture
def mundo(tmp_path):
    raiz = tmp_path / "escaneo"
    mes = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo"
    mes.mkdir(parents=True)
    pdf = mes / "proto 1 marzo 2099.pdf"
    crear_libro(pdf, [_pag(1), _pag(), _pag(2), _pag(), _pag(), _pag(3)])
    return {"raiz": raiz, "datos": tmp_path / "datos", "pdf": pdf, "mes": mes, "tmp": tmp_path}


def _ir(capsys, mundo, *extra, pdf=None):
    rc = main(["aplicar-libro", str(pdf or mundo["pdf"]), "--raiz", str(mundo["raiz"]), "--datos", str(mundo["datos"]),
               "--nice", "0", *map(str, extra)])
    sal = capsys.readouterr()
    return rc, sal.out, sal.err


def _paginas(p):
    with fitz.open(str(p)) as d:
        return d.page_count


@pytest.mark.parametrize("nombre,esperado", [
    ("proto 6 abril 2026.pdf", 6), ("dilli 3 julio 2026.pdf", 3), ("prot 1 enero 2025.pdf", 1), ("dili 2 agosto 2026 .pdf", 2),
    ("otros enero junio 2026.pdf", None), ("libro 3 y 4 marzo 2026.pdf", None), ("2026.pdf", None),
])
def test_libro_probable(nombre, esperado):
    assert antiguos.libro_probable(nombre) == esperado


def test_el_id_es_valido_y_estable():
    a = antiguos.id_de("2026/PROTOCOLOS/Abril/proto 1 abril 2026.pdf")
    assert validar_id(a) == a and a == antiguos.id_de("2026/PROTOCOLOS/Abril/proto 1 abril 2026.pdf")
    assert a != antiguos.id_de("2026/PROTOCOLOS/Abril/proto 2 abril 2026.pdf")


def test_sin_si_solo_muestra_el_plan_y_no_escribe_nada(mundo, capsys):
    antes = _arbol(mundo["tmp"])
    rc, out, _ = _ir(capsys, mundo)
    assert rc == 0 and "PLAN (no se escribió nada)" in out and "libro 1" in out and "--si" in out
    assert _arbol(mundo["tmp"]) == antes


def test_con_si_coloca_cada_acto_y_aparta_el_original_sin_borrarlo(mundo, capsys):
    sha = _sha(mundo["pdf"])
    rc, out, _ = _ir(capsys, mundo, "--si")
    assert rc == 0 and "COLOCADO: 3 archivos" in out
    dest = mundo["mes"] / "libro 1"                      # reutiliza «PROTOCOLOS 2099» y «3. Marzo»
    nombres = sorted(p.name for p in dest.glob("*.pdf"))
    assert nombres == [cod(A, "P", s) + ".pdf" for s in (1, 2, 3)]
    assert [_paginas(dest / n) for n in nombres] == [2, 3, 1]
    apartado = mundo["datos"] / "espera" / "originales" / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "proto 1 marzo 2099.pdf"
    assert not mundo["pdf"].exists() and apartado.is_file() and _sha(apartado) == sha   # apartado, idéntico
    assert Espacio(mundo["datos"], mundo["raiz"]).ultimo(A, "P") == 3


def test_libro_con_hueco_no_se_coloca_sin_aceptarlo(mundo, capsys):
    crear_libro(mundo["pdf"], [_pag(1), _pag(), _pag(4)])             # faltan 2 y 3
    sha = _sha(mundo["pdf"])
    rc, out, _ = _ir(capsys, mundo, "--si")
    assert rc == 1 and "NO SE COLOCÓ NADA" in out and "no se aceptó expresamente" in out
    assert mundo["pdf"].is_file() and _sha(mundo["pdf"]) == sha and not (mundo["mes"] / "libro 1").exists()
    rc, out, _ = _ir(capsys, mundo, "--si", "--aceptar-revision")
    assert rc == 0 and (mundo["mes"] / "libro 1" / (cod(A, "P", 4) + ".pdf")).is_file() and not mundo["pdf"].exists()


def test_no_pisa_un_archivo_distinto_que_ya_estaba(mundo, capsys):
    dest = mundo["mes"] / "libro 1"
    dest.mkdir()
    (dest / (cod(A, "P", 2) + ".pdf")).write_bytes(b"otro contenido")
    rc, out, _ = _ir(capsys, mundo, "--si")
    assert rc == 1 and "es DISTINTO" in out
    assert (dest / (cod(A, "P", 2) + ".pdf")).read_bytes() == b"otro contenido"
    assert mundo["pdf"].is_file()                                       # el original sigue en su sitio


def test_si_el_original_cambia_despues_de_prepararlo_no_se_coloca(mundo):
    esp = Espacio(mundo["datos"], mundo["raiz"]).asegurar()
    info = antiguos.preparar(esp, mundo["pdf"], A, "P")
    with open(mundo["pdf"], "ab") as f:
        f.write(b"\n% cambio\n")
    with pytest.raises(Bloqueado) as e:
        antiguos.aplicar(esp, info["lote"], 3, 1)
    assert any("original cambió" in m for m in e.value.motivos)
    assert mundo["pdf"].is_file() and not (mundo["mes"] / "libro 1").exists()


def test_si_se_corta_antes_de_apartar_el_original_repetir_lo_termina(mundo, monkeypatch):
    esp = Espacio(mundo["datos"], mundo["raiz"]).asegurar()
    info = antiguos.preparar(esp, mundo["pdf"], A, "P")
    real = antiguos._apartar_original
    monkeypatch.setattr(antiguos, "_apartar_original", lambda *a, **k: (_ for _ in ()).throw(OSError("corte")))
    with pytest.raises(OSError):
        antiguos.aplicar(esp, info["lote"], 3, 1)
    assert mundo["pdf"].is_file() and len(list((mundo["mes"] / "libro 1").glob("*.pdf"))) == 3
    monkeypatch.setattr(antiguos, "_apartar_original", real)
    hecho = antiguos.aplicar(esp, info["lote"], 3, 1)                   # repetir termina el trabajo
    assert not mundo["pdf"].exists() and hecho["original_en_espera"].endswith("proto 1 marzo 2099.pdf")
    assert len(list((mundo["mes"] / "libro 1").glob("*.pdf"))) == 3     # sin duplicar nada


def test_libro_sin_codigos_no_hace_nada(mundo, capsys):
    crear_libro(mundo["pdf"], [_pag(), _pag()])
    rc, out, _ = _ir(capsys, mundo, "--si")
    assert rc == 1 and "No se encontró ningún código" in out and mundo["pdf"].is_file()


def test_pide_el_libro_si_el_nombre_no_lo_dice(mundo, capsys):
    otro = mundo["mes"] / "otros marzo 2099.pdf"
    otro.write_bytes(mundo["pdf"].read_bytes())
    rc, _, err = _ir(capsys, mundo, pdf=otro)
    assert rc == 2 and "--libro" in err
    rc, out, _ = _ir(capsys, mundo, "--libro", 7, pdf=otro)
    assert rc == 0 and "libro 7" in out


def test_fuera_del_archivo_o_de_esquema_se_rechaza(mundo, capsys):
    suelto = mundo["tmp"] / "suelto.pdf"
    suelto.write_bytes(mundo["pdf"].read_bytes())
    rc, _, err = _ir(capsys, mundo, pdf=suelto)
    assert rc == 2 and "no se pudo ubicar" in err


def test_auto_siguiente_reconoce_el_suelto_del_final(mundo, capsys):
    crear_libro(mundo["pdf"], [_pag(1), _pag(), _pag(2), _pag(), _pag(90)])           # el 90 está suelto
    (mundo["mes"] / "proto 2 marzo 2099.pdf").unlink(missing_ok=True)
    crear_libro(mundo["mes"] / "proto 2 marzo 2099.pdf", [_pag(3), _pag(), _pag(4)])
    rc, out, _ = _ir(capsys, mundo, "--auto-siguiente")
    assert "fuera de orden" in out and "00090" in out and "faltan" not in out


def test_si_el_mes_no_esta_en_la_ruta_hay_que_indicarlo(mundo, capsys):
    directo = mundo["raiz"] / str(A) / f"PROTOCOLOS {A}" / "proto 5 2099.pdf"
    directo.write_bytes(mundo["pdf"].read_bytes())
    rc, _, err = _ir(capsys, mundo, pdf=directo)
    assert rc == 2 and "--mes" in err
    rc, out, _ = _ir(capsys, mundo, "--mes", 4, pdf=directo)
    assert rc == 0 and "Abril" in out or "abril" in out.lower()


def test_dos_rutas_que_se_parecen_no_comparten_preparacion():
    # mismas letras y números tras quitar signos: sin la huella en el identificador chocarían
    assert antiguos.id_de("2026/P/Abril/proto 1.pdf") != antiguos.id_de("2026/P/Abril/proto-1.pdf")
    assert antiguos.id_de("2026/P/" + "a" * 80 + "x.pdf") != antiguos.id_de("2026/P/" + "a" * 80 + "y.pdf")
