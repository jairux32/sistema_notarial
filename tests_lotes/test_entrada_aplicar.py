import hashlib
import json
from pathlib import Path

import pytest

from lotes import entrada
from lotes.aplicar import Bloqueado, aplicar
from lotes.espacio import Espacio, carpeta_destino, proponer, validar_id

from .sintetico import cod, crear_libro

A = 2099


def _pag(sec=None):
    return {"codigo": cod(A, "P", sec), "titulo": True} if sec else {}


@pytest.fixture
def esp(tmp_path):
    return Espacio(tmp_path / "datos", tmp_path / "escaneo").asegurar()


def _lote(esp, nombre, paginas):
    crear_libro(esp.entrada / f"{nombre}.pdf", paginas)
    return nombre


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_validar_id_rechaza_rutas():
    for malo in ("../x", "a/b", "a\\b", "", "x" * 100, "a b", ".oculto"):
        with pytest.raises(ValueError):
            validar_id(malo)
    assert validar_id("escaneo_20991101_101010") == "escaneo_20991101_101010"


def test_preparar_detecta_serie_y_corta_sin_tocar_el_original(esp):
    _lote(esp, "l1", [_pag(1), _pag(), _pag(2), _pag()])
    antes = _sha(esp.entrada / "l1.pdf")
    info = entrada.preparar(esp, "l1")
    assert (info["anio"], info["tipo"]) == (A, "P")
    assert [(a["codigo"], a["inicio"], a["fin"]) for a in info["resultado"]["actos"]] == [
        (cod(A, "P", 1), 1, 2), (cod(A, "P", 2), 3, 4)]
    assert info["verificacion"]["correcta"] and info["puede_borrar_original"]
    assert _sha(esp.entrada / "l1.pdf") == antes
    assert sorted(p.name for p in (esp.preparacion / "l1").iterdir()) == sorted(
        [cod(A, "P", 1) + ".pdf", cod(A, "P", 2) + ".pdf", "informe.json"])


def test_preparar_sin_codigos_no_corta(esp):
    _lote(esp, "vacio", [_pag(), _pag()])
    info = entrada.preparar(esp, "vacio")
    assert info.get("sin_serie") and not (esp.preparacion / "vacio").exists()


def test_aplicar_guarda_copia_verificada_y_aparta_el_original(esp):
    _lote(esp, "l1", [_pag(1), _pag(), _pag(2)])
    entrada.preparar(esp, "l1")
    original_sha = _sha(esp.entrada / "l1.pdf")
    h = aplicar(esp, "l1", mes=3, libro=1)
    destino = esp.archivo / str(A) / "PROTOCOLOS" / "Marzo" / "libro 1"
    assert sorted(p.name for p in destino.iterdir()) == [cod(A, "P", 1) + ".pdf", cod(A, "P", 2) + ".pdf"]
    assert not (esp.entrada / "l1.pdf").exists()
    assert _sha(esp.espera / "l1.pdf") == original_sha, "el original se aparta intacto, no se borra"
    assert esp.ultimo(A, "P") == 2
    assert all(a["estado"] == "copiado" for a in h["archivos"])
    assert not list(destino.glob(".*.tmp")), "no quedan temporales"


def test_aplicar_es_repetible_sin_duplicar(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    h1 = aplicar(esp, "l1", 3, 1)
    h2 = aplicar(esp, "l1", 3, 1)
    assert h1["archivos"] == h2["archivos"] and len(list((esp.espera).glob("*.pdf"))) == 1


def test_reutiliza_las_carpetas_que_ya_existen_en_el_archivo(esp):
    existente = esp.archivo / str(A) / "PROTOCOLOS" / "3. Marzo" / "libro1"
    existente.mkdir(parents=True)
    assert carpeta_destino(esp, A, "P", 3, 1) == existente
    assert carpeta_destino(esp, A, "P", 4, 1) == esp.archivo / str(A) / "PROTOCOLOS" / "Abril" / "libro 1"
    assert proponer(esp, A, "P", hoy=__import__("datetime").date(A, 3, 10)) == (3, 1)
    (esp.archivo / str(A) / "PROTOCOLOS" / "3. Marzo" / "libro 7").mkdir()
    assert proponer(esp, A, "P", hoy=__import__("datetime").date(A, 3, 10)) == (3, 7)


@pytest.mark.parametrize("mes,libro", [(0, 1), (13, 1), (3, 0), (3, 1000)])
def test_destino_rechaza_valores_fuera_de_rango(esp, mes, libro):
    with pytest.raises(ValueError):
        carpeta_destino(esp, A, "P", mes, libro)


def test_no_pisa_un_archivo_distinto_y_deja_el_original_en_la_entrada(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    destino = esp.archivo / str(A) / "PROTOCOLOS" / "Marzo" / "libro 1"
    destino.mkdir(parents=True)
    (destino / (cod(A, "P", 1) + ".pdf")).write_bytes(b"otro contenido")
    with pytest.raises(Bloqueado) as e:
        aplicar(esp, "l1", 3, 1)
    assert "DISTINTO" in str(e.value)
    assert (esp.entrada / "l1.pdf").exists() and not (esp.preparacion / "l1" / "aplicado.json").exists()
    assert (destino / (cod(A, "P", 1) + ".pdf")).read_bytes() == b"otro contenido"


def test_bloquea_si_el_original_cambio_despues_de_analizar(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    crear_libro(esp.entrada / "l1.pdf", [_pag(1), _pag(), _pag(), _pag()])  # otro contenido, mismo nombre
    with pytest.raises(Bloqueado) as e:
        aplicar(esp, "l1", 3, 1)
    assert "cambió" in str(e.value)
    assert not esp.archivo.exists() or not any(esp.archivo.rglob("*.pdf"))


def test_bloquea_si_un_acto_cortado_se_dano(esp):
    _lote(esp, "l1", [_pag(1), _pag(), _pag(2)])
    entrada.preparar(esp, "l1")
    (esp.preparacion / "l1" / (cod(A, "P", 2) + ".pdf")).write_bytes(b"danado")
    with pytest.raises(Bloqueado):
        aplicar(esp, "l1", 3, 1)
    assert (esp.entrada / "l1.pdf").exists()


def test_lote_para_revisar_exige_aceptacion_expresa(esp):
    _lote(esp, "l1", [_pag(), _pag(1), _pag()])  # una página antes del primer código
    entrada.preparar(esp, "l1")
    with pytest.raises(Bloqueado) as e:
        aplicar(esp, "l1", 3, 1)
    assert "revisión" in str(e.value)
    assert (esp.entrada / "l1.pdf").exists()
    h = aplicar(esp, "l1", 3, 1, aceptar_revision=True)
    nombres = sorted(a["nombre"] for a in h["archivos"])
    assert nombres == [cod(A, "P", 1) + ".pdf", "SIN_CODIGO_l1.pdf"] and h["revision_aceptada"]


def test_segundo_lote_continua_la_numeracion_y_marca_repetidos(esp):
    _lote(esp, "l1", [_pag(1), _pag(2)])
    entrada.preparar(esp, "l1")
    aplicar(esp, "l1", 3, 1)
    _lote(esp, "l2", [_pag(3), _pag(), _pag(1)])  # el 1 repite un habilitante propio
    info = entrada.preparar(esp, "l2")
    assert info["ultimo_previo"] == 2
    assert [a["codigo"] for a in info["resultado"]["actos"]] == [cod(A, "P", 3)]
    assert any(c == cod(A, "P", 1) for _, c, _ in info["resultado"]["ajenos"])
    aplicar(esp, "l2", 3, 1)
    assert esp.ultimo(A, "P") == 3
    carpeta = esp.archivo / str(A) / "PROTOCOLOS" / "Marzo" / "libro 1"
    assert len(list(carpeta.glob("*.pdf"))) == 3


def test_rehacer_con_otro_anio_descarta_solo_la_preparacion(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    antes = _sha(esp.entrada / "l1.pdf")
    info = entrada.preparar(esp, "l1", anio=A, tipo="D", rehacer=True)  # el libro es P: con D no hay actos
    assert info.get("sin_actos")
    assert _sha(esp.entrada / "l1.pdf") == antes and not (esp.preparacion / "l1").exists()


def test_no_se_puede_rehacer_un_lote_ya_guardado(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    aplicar(esp, "l1", 3, 1)
    crear_libro(esp.entrada / "l1.pdf", [_pag(1)])
    with pytest.raises(ValueError):
        entrada.preparar(esp, "l1", rehacer=True)


def test_listar_ignora_ocultos_y_nombres_raros(esp):
    _lote(esp, "bueno", [_pag(1)])
    (esp.entrada / ".oculto.pdf").write_bytes(b"x")
    (esp.entrada / "con espacio.pdf").write_bytes(b"x")
    (esp.entrada / "nota.txt").write_text("x")
    assert [l["id"] for l in entrada.listar(esp)] == ["bueno"]


def test_jpegs_a_pdf_conserva_las_barras_legibles(esp, tmp_path):
    import io
    from PIL import Image
    from .sintetico import png_barras

    jpegs = []
    for sec in (1, None):
        hoja = Image.new("L", (2480, 3508), 255)
        if sec:
            barras = Image.open(io.BytesIO(png_barras(cod(A, "P", sec)))).convert("L")
            barras = barras.resize((900, 300))
            hoja.paste(barras, (1400, 150))
        b = io.BytesIO()
        hoja.save(b, "JPEG", quality=85)
        jpegs.append(b.getvalue())
    destino = esp.entrada / "escaneado.pdf"
    assert entrada.jpegs_a_pdf(jpegs, destino) == 2
    assert not list(esp.entrada.glob(".*.tmp"))
    info = entrada.preparar(esp, "escaneado")
    assert [a["codigo"] for a in info["resultado"]["actos"]] == [cod(A, "P", 1)]
    assert json.loads((esp.preparacion / "escaneado" / "informe.json").read_text())["verificacion"]["correcta"]


def test_bloquea_si_el_original_cambia_un_byte_sin_cambiar_su_tamano(esp):
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")
    ruta = esp.entrada / "l1.pdf"
    datos = ruta.read_bytes()
    assert datos.startswith(b"%PDF-1.")
    ruta.write_bytes(datos[:7] + (b"6" if datos[7:8] != b"6" else b"5") + datos[8:])  # mismo tamaño, otra huella
    with pytest.raises(Bloqueado) as e:
        aplicar(esp, "l1", 3, 1)
    assert "cambió" in str(e.value) and ruta.exists()


def test_una_copia_danada_no_queda_en_el_archivo(esp, monkeypatch):
    import shutil as _sh
    _lote(esp, "l1", [_pag(1), _pag()])
    entrada.preparar(esp, "l1")

    def copia_mala(origen, destino, *a, **k):
        Path(destino).write_bytes(b"copia incompleta")
        return destino

    monkeypatch.setattr("lotes.aplicar.shutil.copyfile", copia_mala)
    with pytest.raises(Bloqueado) as e:
        aplicar(esp, "l1", 3, 1)
    assert "no salió igual" in str(e.value)
    assert not list(esp.archivo.rglob("*.pdf")) and not list(esp.archivo.rglob(".*.tmp"))
    assert (esp.entrada / "l1.pdf").exists() and not (esp.preparacion / "l1" / "aplicado.json").exists()


def test_nuevo_id_nunca_repite_uno_ya_usado(esp):
    from datetime import datetime
    ahora = datetime(2099, 1, 1, 10, 0, 0)
    a = entrada.nuevo_id(ahora, esp)
    (esp.entrada / f"{a}.pdf").write_bytes(b"x")
    b = entrada.nuevo_id(ahora, esp)
    (esp.espera / f"{b}.pdf").write_bytes(b"x")          # ya apartado: tampoco se reutiliza
    c = entrada.nuevo_id(ahora, esp)
    assert len({a, b, c}) == 3 and a == "escaneo_20990101_100000" and entrada.nuevo_id(ahora) == a
    for x in (a, b, c):
        validar_id(x)
