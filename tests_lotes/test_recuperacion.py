"""Códigos que el primer paso no leyó: recuperación dirigida en los huecos y códigos puestos a mano."""
from pathlib import Path

import pymupdf as fitz
import pytest

from lotes import analisis
from lotes.cli import _manuales, main
from lotes.reglas import DeteccionPagina, armar_actos

from .sintetico import cod, crear_libro

A, T = 2026, "D"


def c(sec, anio=A, tipo=T):
    return f"{anio}1101007{tipo}{sec:05d}"


def libro(secuencia, paso=3):
    dets = [DeteccionPagina(pagina=1 + i * paso, barras=(c(s),)) for i, s in enumerate(secuencia)]
    return dets, 1 + len(secuencia) * paso


def secs(res):
    return [a.codigo.secuencial for a in res.actos]


# ------------------------------------------------------------------ reglas: manuales y recuperados
def test_un_codigo_a_mano_abre_el_acto_y_lo_dice():
    dets, total = libro([1, 2, 4, 5])  # hojas 1, 4, 7, 10; falta el 3, que está en la hoja 5 (entre el 2 y el 4)
    res = armar_actos(dets, total, A, T, manuales={5: c(3)})
    assert secs(res) == [1, 2, 3, 4, 5] and not res.saltos and not res.requiere_revision
    acto = next(a for a in res.actos if a.codigo.secuencial == 3)
    assert acto.avisos == ["el código de la hoja 5 lo puso una persona"]
    assert (res.actos[1].inicio, res.actos[1].fin) == (4, 4) and (acto.inicio, acto.fin) == (5, 6)


def test_lo_manual_manda_sobre_lo_leido_en_esa_hoja():
    dets = [DeteccionPagina(1, (c(1),)), DeteccionPagina(4, (c(2),)), DeteccionPagina(7, (c(2),)), DeteccionPagina(10, (c(4),))]
    # la hoja 7 se leyó como 2 (repetido) pero la persona dice que es el 3
    res = armar_actos(dets, 12, A, T, manuales={7: c(3)})
    assert secs(res) == [1, 2, 3, 4]


def test_un_codigo_recuperado_se_acepta_pero_deja_el_libro_para_revisar():
    dets, total = libro([1, 2, 4])  # hojas 1, 4, 7
    res = armar_actos(dets, total, A, T, recuperados={5: c(3)})
    assert secs(res) == [1, 2, 3, 4] and not res.saltos
    assert res.requiere_revision and any("se recuperó" in a and "hoja 5" in a for a in res.avisos)


def test_los_huecos_traen_sus_hojas():
    dets, total = libro([1, 2, 5])
    res = armar_actos(dets, total, A, T)
    assert res.huecos == [(3, 4, 5, 6)]    # faltan 3 y 4; pueden estar en las hojas 5 y 6 (entre el acto 2 y el 5)


# ------------------------------------------------------------------ analizar con lector falso
class Lector:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = respuestas, []

    def __call__(self, pagina, esperados):
        self.llamadas.append((pagina, set(esperados)))
        return self.respuestas.get(pagina)


def _analizar(dets, total, lector, **kw):
    return analisis.analizar(Path("no_se_abre.pdf"), A, T, leido=(total, dets), lector=lector, **kw)


def test_recupera_solo_dentro_del_hueco_y_cierra_el_hueco():
    dets, total = libro([1, 2, 4, 5])
    lector = Lector({6: c(3)})
    res = _analizar(dets, total, lector)
    assert secs(res) == [1, 2, 3, 4, 5] and not res.saltos
    assert [p for p, _ in lector.llamadas] == [5, 6]             # solo las hojas del hueco: entre el acto 2 (hoja 4) y el 4 (hoja 7)
    assert res.requiere_revision and any("se recuperó" in a for a in res.avisos)


def test_no_acepta_un_codigo_que_no_es_de_los_que_faltan():
    dets, total = libro([1, 2, 4])
    lector = Lector({5: c(900)})            # un código cualquiera: se ignora
    res = _analizar(dets, total, lector)
    assert secs(res) == [1, 2, 4] and res.saltos


def test_si_no_hay_hueco_no_se_vuelve_a_leer_nada():
    dets, total = libro([1, 2, 3])
    lector = Lector({})
    _analizar(dets, total, lector)
    assert lector.llamadas == []


def test_sin_recuperar_no_lee_de_nuevo():
    dets, total = libro([1, 2, 4])
    lector = Lector({5: c(3)})
    res = _analizar(dets, total, lector, recuperar=False)
    assert lector.llamadas == [] and res.saltos


def test_hueco_enorme_no_se_busca():
    dets = [DeteccionPagina(1, (c(1),)), DeteccionPagina(2000, (c(3),))]
    lector = Lector({})
    _analizar(dets, 2010, lector)
    assert lector.llamadas == []


def test_dos_faltantes_en_el_mismo_hueco():
    dets, total = libro([1, 4], paso=5)       # faltan 2 y 3, hojas 2 a 5 del hueco
    lector = Lector({3: c(2), 5: c(3)})
    res = _analizar(dets, total, lector)
    assert secs(res) == [1, 2, 3, 4] and not res.saltos


def test_lo_manual_no_se_pisa_con_lo_recuperado():
    dets, total = libro([1, 2, 5])
    lector = Lector({})
    res = _analizar(dets, total, lector, manuales={5: c(3)})      # la persona ya dijo que la hoja 5 es el 3
    assert 5 not in [p for p, _ in lector.llamadas] and secs(res) == [1, 2, 3, 5]


# ------------------------------------------------------------------ lector real sobre páginas sintéticas
def test_lector_a_fondo_lee_el_codigo_esperado_y_rechaza_los_demas(tmp_path):
    pdf = tmp_path / "l.pdf"
    crear_libro(pdf, [{"codigo": cod(A, "D", 7), "titulo": True}, {"codigo": cod(A, "D", 8)}, {}])
    with fitz.open(str(pdf)) as doc:
        leer = analisis.lector_a_fondo(doc, A, "D")
        assert leer(1, {7}) == cod(A, "D", 7)
        assert leer(1, {9}) is None           # hay código pero no es de los esperados
        assert leer(3, {7, 8}) is None        # hoja sin código
        assert leer(99, {7}) is None          # hoja que no existe: no revienta


# ------------------------------------------------------------------ línea de comandos
def test_manuales_acepta_solo_el_numero_o_el_codigo_entero():
    assert _manuales(["769=1181"], A, T) == {769: c(1181)}
    assert _manuales([f"5={c(7)}"], A, T) == {5: c(7)}
    assert _manuales(None, A, T) == {}


@pytest.mark.parametrize("malo", ["769", "x=1181", "0=5", "5=abc", f"5={c(7, tipo='P')}", f"5={c(7, anio=2025)}", "5=20261101009D00007"])
def test_manuales_rechaza_lo_que_no_sirve(malo):
    with pytest.raises(ValueError):
        _manuales([malo], A, T)


def test_simular_con_codigo_manual_cierra_el_hueco(tmp_path, capsys):
    base = tmp_path / "esc" / "2026" / "DILIGENCIAS" / "Enero"
    base.mkdir(parents=True)
    pdf = base / "dili 1 enero 2026.pdf"
    paginas = [{"codigo": cod(A, "D", 1)}, {}, {"codigo": cod(A, "D", 3)}, {}]    # el 2 está en la hoja 2 sin código legible
    crear_libro(pdf, paginas)
    rc = main(["simular", str(pdf), "--anio", "2026", "--tipo", "D", "--nice", "0", "--sin-recuperar"])
    assert rc == 1 and "faltan 00002" in capsys.readouterr().out
    rc = main(["simular", str(pdf), "--anio", "2026", "--tipo", "D", "--nice", "0", "--sin-recuperar", "--codigo-manual", "2=2"])
    out = capsys.readouterr().out
    assert rc == 0 and "faltan" not in out and "00002" in out
    rc = main(["simular", str(pdf), "--anio", "2026", "--tipo", "D", "--nice", "0", "--codigo-manual", "2=7x"])
    assert rc == 2


def test_aplicar_libro_con_codigo_manual_rehace_la_preparacion_y_coloca(tmp_path, capsys):
    raiz = tmp_path / "esc"
    mes = raiz / "2026" / "DILIGENCIAS" / "Enero"
    mes.mkdir(parents=True)
    pdf = mes / "dili 1 enero 2026.pdf"
    crear_libro(pdf, [{"codigo": cod(A, "D", 1)}, {}, {"codigo": cod(A, "D", 3)}, {}])
    base = ["aplicar-libro", str(pdf), "--raiz", str(raiz), "--datos", str(tmp_path / "datos"), "--nice", "0", "--si",
            "--sin-recuperar"]
    assert main(base) == 1 and "NO SE COLOCÓ NADA" in capsys.readouterr().out and pdf.is_file()   # hay un hueco
    assert main(base + ["--codigo-manual", "2=2"]) == 0                                           # con el 2 a mano, sí
    nombres = sorted(p.name for p in (mes / "libro 1").glob("*.pdf"))
    assert nombres == [cod(A, "D", s) + ".pdf" for s in (1, 2, 3)] and not pdf.exists()


def test_lo_manual_manda_sobre_lo_recuperado_en_la_misma_hoja():
    dets, total = libro([1, 2, 5])  # hojas 1, 4, 7
    res = armar_actos(dets, total, A, T, manuales={5: c(3)}, recuperados={5: c(4)})
    assert next(a for a in res.actos if a.inicio == 5).codigo.secuencial == 3


def test_un_codigo_leido_que_no_es_de_los_que_faltan_no_cuenta_aunque_el_lector_lo_devuelva():
    dets, total = libro([1, 2, 5])  # faltan 3 y 4
    res = _analizar(dets, total, Lector({5: c(6)}))
    assert secs(res) == [1, 2, 5] and not res.avisos


def test_simular_recupera_por_defecto_y_no_con_sin_recuperar(tmp_path, capsys, monkeypatch):
    base = tmp_path / "esc" / "2026" / "DILIGENCIAS" / "Enero"
    base.mkdir(parents=True)
    pdf = base / "dili 1 enero 2026.pdf"
    crear_libro(pdf, [{"codigo": cod(A, "D", 1)}, {}, {"codigo": cod(A, "D", 3)}, {}])
    monkeypatch.setattr(analisis, "lector_a_fondo", lambda doc, anio, tipo: (lambda p, esperados: cod(A, "D", 2) if p == 2 else None))
    argumentos = ["simular", str(pdf), "--anio", "2026", "--tipo", "D", "--nice", "0"]
    assert main(argumentos + ["--sin-recuperar"]) == 1 and "faltan 00002" in capsys.readouterr().out
    rc = main(argumentos)
    out = capsys.readouterr().out
    assert rc == 1 and "se recuperó" in out and "faltan" not in out
