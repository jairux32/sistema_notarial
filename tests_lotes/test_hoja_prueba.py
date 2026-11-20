import io

import pymupdf as fitz
from PIL import Image, ImageFilter

from lotes import hoja_prueba as hp


def _escaneo_simulado(origen, destino, dpi=150, desenfoque=0.8):
    """Rasteriza cada hoja a gris, la desenfoca un poco y arma un PDF de solo imagen (como un escaneo)."""
    out = fitz.open()
    with fitz.open(str(origen)) as doc:
        for p in doc:
            pix = p.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
            img = Image.frombytes("L", (pix.width, pix.height), pix.samples).filter(ImageFilter.GaussianBlur(desenfoque))
            buf = io.BytesIO(); img.save(buf, "JPEG", quality=70)
            n = out.new_page(width=p.rect.width, height=p.rect.height)
            n.insert_image(n.rect, stream=buf.getvalue())
    out.save(str(destino)); out.close()


def test_libro_de_prueba_se_parte_como_se_espera(tmp_path):
    ruta = tmp_path / "libro.pdf"
    assert hp.generar(ruta) == 9
    assert hp.comprobar(ruta) == []


def test_sigue_leyendo_tras_imprimir_y_escanear(tmp_path):
    ruta, esc = tmp_path / "libro.pdf", tmp_path / "escaneo.pdf"
    hp.generar(ruta)
    _escaneo_simulado(ruta, esc)
    assert hp.comprobar(esc) == []


def test_el_resultado_esperado_nombra_cada_acto():
    t = hp.resultado_esperado()
    for _, _, cod in hp.ESPERADO:
        assert cod in t
    assert "2099" in t and "NO deben abrir acto" in t


def test_los_codigos_de_prueba_no_son_de_un_acto_real():
    assert all(cod.startswith("2099") for _, _, cod in hp.ESPERADO)
