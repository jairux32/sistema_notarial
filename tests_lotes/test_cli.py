import hashlib
import json
import os
from pathlib import Path

import pytest

from lotes.cli import main

from .sintetico import cod, crear_libro

A = 2099


def _pag(sec=None, titulo=True):
    return {"codigo": cod(A, "P", sec), "titulo": titulo} if sec else {}


@pytest.fixture
def raiz(tmp_path):
    """Archivo de juguete: dos libros del mismo año/tipo con un hueco de numeración entre ellos."""
    base = tmp_path / "escaneo" / str(A) / f"PROTOCOLOS {A}" / "3. Marzo"
    (base / "libro1").mkdir(parents=True)
    (base / "libro2").mkdir(parents=True)
    crear_libro(base / "libro1" / "l1.pdf", [_pag(1), _pag(), _pag(2), _pag(), _pag()])
    crear_libro(base / "libro2" / "l2.pdf", [_pag(5), _pag(), _pag(6)])      # faltan 3 y 4
    return tmp_path / "escaneo"


def _ejecutar(capsys, *args):
    cmd = [str(a) for a in args]
    if args[0] in ("simular", "serie", "dividir"):
        cmd += ["--nice", "0"]
    rc = main(cmd)
    sal = capsys.readouterr()
    return rc, sal.out, sal.err


def _hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _arbol(p):
    return sorted(str(x.relative_to(p)) for x in Path(p).rglob("*"))


def test_inventario_no_abre_los_pdf(raiz, capsys):
    malo = raiz / str(A) / f"PROTOCOLOS {A}" / "1. Enero" / "libro1"
    malo.mkdir(parents=True)
    (malo / "dañado.pdf").write_bytes(b"esto no es un pdf")
    rc, out, _ = _ejecutar(capsys, "inventario", raiz)
    assert rc == 0 and "no se abrió ningún PDF" in out
    assert "TOTAL: 3 PDF" in out and str(A) in out


def test_inventario_con_paginas_abre_y_avisa_del_dañado(raiz, capsys):
    malo = raiz / str(A) / f"PROTOCOLOS {A}" / "1. Enero" / "libro1"
    malo.mkdir(parents=True)
    (malo / "dañado.pdf").write_bytes(b"esto no es un pdf")
    rc, out, _ = _ejecutar(capsys, "inventario", raiz, "--paginas")
    assert rc == 1 and "no se pudo abrir" in out and "dañado.pdf" in out


def test_inventario_lista_irregulares_y_ignora_otros_archivos(raiz, capsys):
    (raiz / "suelto.pdf").write_bytes(b"x")
    (raiz / str(A) / "PAPELES").mkdir()
    (raiz / str(A) / "PAPELES" / "y.pdf").write_bytes(b"x")
    (raiz / str(A) / "Thumbs.db").write_bytes(b"x")
    (raiz / "lost+found").mkdir()
    (raiz / "lost+found" / "z.pdf").write_bytes(b"x")
    rc, out, _ = _ejecutar(capsys, "inventario", raiz)
    assert rc == 1
    assert "IRREGULARES (2)" in out and "suelto.pdf" in out and "PAPELES/y.pdf" in out
    assert "db: 1" in out and "lost+found" not in out


def test_simular_no_escribe_nada_y_dice_los_actos(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    antes = _arbol(raiz)
    rc, out, _ = _ejecutar(capsys, "simular", pdf, "--raiz", raiz)
    assert rc == 0 and cod(A, "P", 1) in out and cod(A, "P", 2) in out
    assert "páginas 1-2" in out and "páginas 3-5" in out
    assert _arbol(raiz) == antes


def test_simular_pide_anio_y_tipo_si_no_puede_deducirlos(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    rc, _, err = _ejecutar(capsys, "simular", pdf)
    assert rc == 2 and "--anio" in err


def test_tipo_invalido(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    rc, _, err = _ejecutar(capsys, "simular", pdf, "--anio", A, "--tipo", "Z")
    assert rc == 2 and "P, D, C, A u O" in err


def test_serie_encadena_la_numeracion_y_marca_el_hueco(raiz, capsys):
    rc, out, _ = _ejecutar(capsys, "serie", raiz, "--anio", A, "--tipo", "P")
    assert rc == 1
    assert "faltan 00003–00004 antes de" in out
    assert "libro1" in out and "libro2" in out and out.index("libro1") < out.index("libro2")


def test_serie_sin_hueco_sale_limpia(raiz, capsys):
    base = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro2" / "l2.pdf"
    crear_libro(base, [_pag(3), _pag(), _pag(4)])                      # ahora continúa 3,4
    rc, out, _ = _ejecutar(capsys, "serie", raiz, "--anio", A, "--tipo", "P")
    assert rc == 0 and "2 libros sin observaciones" in out


def test_dividir_genera_informe_y_no_toca_el_original(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    h0 = _hash(pdf)
    rc, out, _ = _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    prep = pdf.parent / "_division_l1"
    assert rc == 0 and (prep / f"{cod(A, 'P', 1)}.pdf").is_file() and (prep / f"{cod(A, 'P', 2)}.pdf").is_file()
    assert "VERIFICACIÓN: CORRECTA" in out and "previa aprobación de una persona" in out
    assert _hash(pdf) == h0 and pdf.is_file()                          # el original sigue igual
    info = json.loads((prep / "informe.json").read_text(encoding="utf-8"))
    assert info["puede_borrar_original"] is True and len(info["generados"]) == 2
    assert not list(prep.glob(".*.tmp"))                                # sin temporales


def test_dividir_no_pisa_una_preparacion_existente(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    assert _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)[0] == 0
    rc, _, err = _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    assert rc == 2 and "no se sobrescribe" in err


def test_dividir_libro_sin_codigos_no_escribe_nada(tmp_path, capsys):
    pdf = tmp_path / "sin.pdf"
    crear_libro(pdf, [{}, {}, {}])
    rc, out, _ = _ejecutar(capsys, "dividir", pdf, "--anio", A, "--tipo", "P")
    assert rc == 1 and "ningún código" in out and not (tmp_path / "_division_sin").exists()


def test_dividir_con_hueco_se_divide_pero_no_permite_borrar(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro2" / "l2.pdf"
    rc, out, _ = _ejecutar(capsys, "dividir", pdf, "--raiz", raiz, "--ultimo-previo", 2)
    assert rc == 1 and "NO" in out and "faltan 00003–00004" in out
    assert (pdf.parent / "_division_l2" / f"{cod(A, 'P', 5)}.pdf").is_file()


def test_verificar_correcta_y_luego_detecta_un_archivo_dañado(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    prep = pdf.parent / "_division_l1"
    rc, out, _ = _ejecutar(capsys, "verificar", prep)
    assert rc == 0 and "CORRECTA" in out
    with open(prep / f"{cod(A, 'P', 1)}.pdf", "ab") as f:             # corrupción silenciosa
        f.write(b"basura")
    rc, out, _ = _ejecutar(capsys, "verificar", prep)
    assert rc == 1 and "sha256" in out and "NO" in out.split("¿SE PUEDE BORRAR")[1]


def test_verificar_detecta_que_el_original_cambio(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    with open(pdf, "ab") as f:
        f.write(b"x")
    rc, out, _ = _ejecutar(capsys, "verificar", pdf.parent / "_division_l1")
    assert rc == 1 and "cambió su contenido" in out


def test_verificar_detecta_que_el_original_ya_no_esta(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    os.remove(pdf)
    rc, out, _ = _ejecutar(capsys, "verificar", pdf.parent / "_division_l1")
    assert rc == 1 and "ya no está" in out


def test_informe_se_puede_releer_y_aclara_que_no_borra(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    rc, out, _ = _ejecutar(capsys, "informe", pdf.parent / "_division_l1")
    assert rc == 0 and cod(A, "P", 2) in out and "nunca borra el original" in out


def test_informe_de_carpeta_sin_informe(tmp_path, capsys):
    rc, _, err = _ejecutar(capsys, "informe", tmp_path)
    assert rc == 2 and "no se pudo leer" in err


def test_verificar_detecta_un_cambio_del_original_del_mismo_tamaño(raiz, capsys):
    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    datos = bytearray(pdf.read_bytes())
    datos[-3] ^= 0x01                                                   # un bit distinto, mismo tamaño
    pdf.write_bytes(bytes(datos))
    rc, out, _ = _ejecutar(capsys, "verificar", pdf.parent / "_division_l1")
    assert rc == 1 and "cambió su contenido" in out


def test_dividir_avisa_si_el_original_cambia_mientras_se_divide(raiz, capsys, monkeypatch):
    import lotes.cli as cli

    pdf = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo" / "libro1" / "l1.pdf"
    real = cli.dividir

    def dividir_y_tocar(ruta, resultado, carpeta):
        generados = real(ruta, resultado, carpeta)
        with open(ruta, "ab") as f:
            f.write(b"%trailing")
        return generados

    monkeypatch.setattr(cli, "dividir", dividir_y_tocar)
    rc, out, _ = _ejecutar(capsys, "dividir", pdf, "--raiz", raiz)
    assert rc == 1 and "cambió mientras se dividía" in out


def test_serie_no_pierde_el_libro_siguiente_por_un_codigo_suelto_al_final_del_anterior(raiz, capsys):
    base = raiz / str(A) / f"PROTOCOLOS {A}" / "3. Marzo"
    crear_libro(base / "libro1" / "l1.pdf", [_pag(1), _pag(), _pag(2), _pag(), _pag(90)])   # el 90 está suelto
    crear_libro(base / "libro2" / "l2.pdf", [_pag(3), _pag(), _pag(4)])
    rc, out, _ = _ejecutar(capsys, "serie", raiz, "--anio", A, "--tipo", "P")
    assert "l2.pdf: 3 pág., 2 actos (00003–00004)" in out          # antes salía «sin actos»
    assert "fuera de orden" in out and rc == 1                      # y el suelto queda a la vista
