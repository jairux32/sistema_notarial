import json

import pymupdf as fitz
import pytest

from lotes import libro
from lotes.aplicar import Bloqueado
from lotes.entrada import marcar_aviso
from lotes.espacio import Espacio

from .sintetico import cod, crear_libro

A = 2099


def _pag(sec=None):
    return {"codigo": cod(A, "P", sec), "titulo": True} if sec else {}


@pytest.fixture
def esp(tmp_path):
    return Espacio(tmp_path / "datos", tmp_path / "escaneo").asegurar()


def _tanda(esp, nombre, paginas):
    crear_libro(esp.entrada / f"{nombre}.pdf", paginas)
    return nombre


def _destino(esp, mes="Marzo", libro_n=1):
    return esp.archivo / str(A) / "PROTOCOLOS" / mes / f"libro {libro_n}"


def _paginas(p):
    with fitz.open(str(p)) as d:
        return d.page_count


def _nombres(carpeta):
    return sorted(p.name for p in carpeta.glob("*.pdf"))


def _abrir(esp):
    return libro.abrir_libro(esp, A, "P", 3, 1)


def test_abrir_libro_una_sola_vez(esp):
    _abrir(esp)
    with pytest.raises(ValueError, match="ya hay un libro abierto"):
        _abrir(esp)


def test_abrir_libro_valida_mes_y_numero(esp):
    with pytest.raises(ValueError):
        libro.abrir_libro(esp, A, "P", 13, 1)
    with pytest.raises(ValueError):
        libro.abrir_libro(esp, A, "P", 3, 0)
    assert libro.estado(esp) is None


def test_sin_libro_abierto_no_se_procesa(esp):
    _tanda(esp, "t1", [_pag(1)])
    with pytest.raises(ValueError, match="no hay un libro abierto"):
        libro.procesar(esp, "t1")


def test_un_acto_se_cierra_al_aparecer_el_siguiente_y_el_ultimo_queda_abierto(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2), _pag()])
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "guardado" and r["guardados"] == [cod(A, "P", 1)] and r["abierto"] == cod(A, "P", 2)
    assert _nombres(_destino(esp)) == [cod(A, "P", 1) + ".pdf"]
    assert _paginas(_destino(esp) / (cod(A, "P", 1) + ".pdf")) == 2
    s = libro.estado(esp)
    assert s["acto_abierto"] == {"codigo": cod(A, "P", 2), "paginas": 2} and s["ultimo_antes_abierto"] == 1
    assert not (esp.entrada / "t1.pdf").exists() and (esp.espera / "t1.pdf").exists()


def test_un_acto_partido_entre_dos_tandas_sale_completo(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2), _pag()])           # el 2 queda abierto con 2 páginas
    libro.procesar(esp, "t1")
    _tanda(esp, "t2", [_pag(), _pag(), _pag(3), _pag()])            # 2 hojas más del acto 2, y abre el 3
    r = libro.procesar(esp, "t2")
    assert r["estado"] == "guardado" and r["guardados"] == [cod(A, "P", 2)] and r["abierto"] == cod(A, "P", 3)
    assert _paginas(_destino(esp) / (cod(A, "P", 2) + ".pdf")) == 4, "2 de la primera tanda + 2 de la segunda"
    assert libro.estado(esp)["ultimo_antes_abierto"] == 2


def test_una_tanda_sin_codigos_solo_alarga_el_acto_abierto(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag()])
    libro.procesar(esp, "t1")
    _tanda(esp, "t2", [_pag(), _pag()])
    r = libro.procesar(esp, "t2")
    assert r["estado"] == "guardado" and r["guardados"] == [] and r["abierto"] == cod(A, "P", 1)
    assert libro.estado(esp)["acto_abierto"]["paginas"] == 4
    assert not _destino(esp).exists() or not list(_destino(esp).glob("*.pdf"))


def test_fin_de_libro_guarda_el_acto_abierto(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2), _pag(), _pag()])
    libro.procesar(esp, "t1")
    r = libro.cerrar_libro(esp)
    assert r["actos"] == 2 and r["ultimo"]["codigo"] == cod(A, "P", 2)
    assert _nombres(_destino(esp)) == [cod(A, "P", 1) + ".pdf", cod(A, "P", 2) + ".pdf"]
    assert _paginas(_destino(esp) / (cod(A, "P", 2) + ".pdf")) == 3
    assert libro.estado(esp) is None and esp.ultimo(A, "P") == 2
    assert list((esp.datos / "libro" / "historial").glob("*.json"))
    libro.abrir_libro(esp, A, "P", 3, 2)  # se puede abrir el libro siguiente


def test_un_salto_de_numeracion_queda_por_revisar_y_no_guarda_nada(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(3), _pag()])  # falta el 2
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "revision" and any("faltan" in m for m in r["motivos"]) and r["puede_aceptar"]
    assert not _destino(esp).exists() and (esp.entrada / "t1.pdf").exists()
    assert libro.estado(esp)["tandas"] == 0 and libro.estado(esp)["acto_abierto"] is None


def test_aprobar_una_tanda_dudosa_la_guarda(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(3), _pag()])
    libro.procesar(esp, "t1")
    r = libro.procesar(esp, "t1", aceptar=True)
    assert r["estado"] == "guardado" and r["guardados"] == [cod(A, "P", 1)] and r["abierto"] == cod(A, "P", 3)
    assert json.loads((esp.preparacion / "t1" / "aplicado.json").read_text())["revision_aceptada"] is True


def test_paginas_antes_del_primer_codigo_exigen_revision(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(), _pag(1), _pag(2)])
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "revision" and any("antes del primer código" in m for m in r["motivos"])
    r = libro.procesar(esp, "t1", aceptar=True)
    assert _nombres(_destino(esp)) == [cod(A, "P", 1) + ".pdf", "SIN_CODIGO_t1.pdf"] and r["abierto"] == cod(A, "P", 2)


def test_tanda_sin_ningun_codigo_en_libro_nuevo_no_se_puede_aceptar(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(), _pag()])
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "revision" and r["puede_aceptar"] is False
    r = libro.procesar(esp, "t1", aceptar=True)
    assert r["estado"] == "revision", "aceptar no sirve sin ningún código: hay que descartar y volver a escanear"
    assert (esp.entrada / "t1.pdf").exists() and not _destino(esp).exists()


def test_aviso_de_hojas_pegadas_exige_revision(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    marcar_aviso(esp, "t1", "Usted indicó 4 hojas y el escáner entregó 3.")
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "revision" and any("indicó 4" in m for m in r["motivos"])


def test_codigo_ajeno_y_repetido_no_abren_acto_ni_piden_revision(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), {"ajenos": [cod(A, "P", 1)]}, {"ajenos": [cod(A, "P", 555, notaria="1101010")]}, _pag(2)])
    r = libro.procesar(esp, "t1")
    assert r["estado"] == "guardado" and r["guardados"] == [cod(A, "P", 1)]
    assert _paginas(_destino(esp) / (cod(A, "P", 1) + ".pdf")) == 3


def test_repetir_la_orden_no_duplica(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    libro.procesar(esp, "t1")
    antes = libro.estado(esp)
    r = libro.procesar(esp, "t1")  # el PDF ya no está, pero la tanda consta como procesada
    assert r["estado"] == "guardado" and r.get("repetido") and libro.estado(esp) == antes


def test_corte_antes_de_apartar_el_original_se_termina_sin_duplicar(esp, monkeypatch):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    original = (esp.entrada / "t1.pdf").read_bytes()

    def falla(*a, **k):
        raise RuntimeError("corte de luz")

    monkeypatch.setattr("lotes.libro._terminar_aparte", falla)
    with pytest.raises(RuntimeError):
        libro.procesar(esp, "t1")
    assert (esp.entrada / "t1.pdf").exists() and libro.estado(esp)["tandas"] == 1  # el estado ya avanzó
    monkeypatch.undo()
    r = libro.procesar(esp, "t1")
    assert r.get("repetido") and (esp.espera / "t1.pdf").read_bytes() == original
    assert libro.estado(esp)["tandas"] == 1 and _nombres(_destino(esp)) == [cod(A, "P", 1) + ".pdf"]


def test_no_pisa_un_archivo_distinto_del_archivo(esp):
    _abrir(esp)
    _destino(esp).mkdir(parents=True)
    (_destino(esp) / (cod(A, "P", 1) + ".pdf")).write_bytes(b"otro")
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    with pytest.raises(Bloqueado):
        libro.procesar(esp, "t1")
    assert (esp.entrada / "t1.pdf").exists() and libro.estado(esp)["tandas"] == 0
    assert (_destino(esp) / (cod(A, "P", 1) + ".pdf")).read_bytes() == b"otro"


def test_pendientes_y_procesar_en_orden_se_detiene_en_la_primera_dudosa(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    _tanda(esp, "t2", [_pag(4), _pag()])         # salta el 3: dudosa
    _tanda(esp, "t3", [_pag(5)])
    res = libro.procesar_pendientes(esp)
    assert [r["estado"] for r in res] == ["guardado", "revision"]
    assert [l["id"] for l in libro.pendientes(esp)] == ["t2", "t3"]


def test_no_se_cierra_el_libro_con_tandas_por_revisar(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(3)])
    libro.procesar(esp, "t1")
    with pytest.raises(Bloqueado, match="por revisar"):
        libro.cerrar_libro(esp)


def test_descartar_aparta_sin_borrar_y_no_cambia_el_libro(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(3)])
    libro.procesar(esp, "t1")
    antes = libro.estado(esp)
    destino = libro.descartar(esp, "t1")
    assert destino.exists() and not (esp.entrada / "t1.pdf").exists() and libro.estado(esp) == antes
    assert not (esp.preparacion / "t1").exists()
    _tanda(esp, "t1b", [_pag(2), _pag()])
    assert libro.procesar(esp, "t1b")["estado"] == "guardado"


def test_no_se_descarta_una_tanda_ya_guardada(esp):
    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    libro.procesar(esp, "t1")
    with pytest.raises(ValueError):
        libro.descartar(esp, "t1")


def test_libro_grande_en_tandas_de_cinco_hojas(esp):
    """Escenario reducido: 12 actos de 4-5 hojas escaneados en tandas de 5, con actos partidos entre tandas."""
    _abrir(esp)
    todo = []
    for n in range(1, 13):
        todo += [_pag(n)] + [_pag() for _ in range(3 + n % 2)]
    for i in range(0, len(todo), 5):
        _tanda(esp, f"t{i // 5:02d}", todo[i:i + 5])
    res = libro.procesar_pendientes(esp)
    assert all(r["estado"] == "guardado" for r in res)
    libro.cerrar_libro(esp)
    carpeta = _destino(esp)
    assert _nombres(carpeta) == [cod(A, "P", n) + ".pdf" for n in range(1, 13)]
    assert sum(_paginas(carpeta / f) for f in _nombres(carpeta)) == len(todo)
    for n in range(1, 13):
        assert _paginas(carpeta / (cod(A, "P", n) + ".pdf")) == 4 + n % 2


def test_si_la_verificacion_del_corte_falla_no_se_guarda_ni_se_puede_aceptar(esp, monkeypatch):
    from lotes.division import Verificacion

    _abrir(esp)
    _tanda(esp, "t1", [_pag(1), _pag(), _pag(2)])
    monkeypatch.setattr("lotes.libro.verificar", lambda *a, **k: Verificacion(problemas=["una página no coincide"]))
    for aceptar in (False, True):
        r = libro.procesar(esp, "t1", aceptar=aceptar)
        assert r["estado"] == "error" and "no coincide" in r["motivos"][0]
    assert (esp.entrada / "t1.pdf").exists() and not _destino(esp).exists() and libro.estado(esp)["tandas"] == 0
