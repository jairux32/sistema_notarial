"""Edge case functional tests: scanned PDFs (real OCR), corrupted files, empty PDFs."""
import io
import os
import tempfile
import shutil
import pytest
import fitz
from PIL import Image, ImageDraw, ImageFont

from conftest import _flask_app, procesar_pdf


def _make_scanned_pdf(path, codes):
    """Create a PDF where codes are rendered as images (no text layer).
    Forces the OCR fallback path in _buscar_en_pdf."""
    doc = fitz.open()
    for code in codes:
        page = doc.new_page(width=595, height=842)
        img = Image.new('RGB', (595, 842), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((80, 100), code, fill='black', font=font)
        draw.text((80, 150), f"Documento notarial escaneado {code}", fill='black', font=font)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        page.insert_image(page.rect, stream=img_bytes.read())
    doc.save(path)
    doc.close()


def _make_mixed_pdf(path, text_codes, scanned_codes):
    """Create a PDF with some text-layer pages and some image-only pages."""
    doc = fitz.open()
    for code in text_codes:
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
    for code in scanned_codes:
        page = doc.new_page(width=595, height=842)
        img = Image.new('RGB', (595, 842), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((80, 100), code, fill='black', font=font)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        page.insert_image(page.rect, stream=img_bytes.read())
    doc.save(path)
    doc.close()


@pytest.fixture
def tmp_dirs():
    upload_dir = tempfile.mkdtemp()
    processed_dir = tempfile.mkdtemp()
    _flask_app.config['UPLOAD_FOLDER'] = os.path.abspath(upload_dir)
    _flask_app.config['PROCESSED_FOLDER'] = os.path.abspath(processed_dir)
    yield {'upload': upload_dir, 'processed': processed_dir}
    shutil.rmtree(upload_dir, ignore_errors=True)
    shutil.rmtree(processed_dir, ignore_errors=True)


class TestScannedPDFWithOCR:
    def test_ocr_finds_code_in_scanned_page(self, tmp_dirs):
        codes = ['20251101007P00001']
        pdf_path = os.path.join(tmp_dirs['upload'], 'scanned.pdf')
        _make_scanned_pdf(pdf_path, codes)

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert result.get('success') is True
        assert '20251101007P00001' in result['codigos_encontrados']

    def test_ocr_finds_multiple_codes_in_scanned_pages(self, tmp_dirs):
        codes = ['20251101007P00001', '20251101007P00002', '20251101007P00003']
        pdf_path = os.path.join(tmp_dirs['upload'], 'scanned_multi.pdf')
        _make_scanned_pdf(pdf_path, codes)

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert result.get('success') is True
        assert len(result['codigos_encontrados']) == 3

    def test_ocr_split_produces_files(self, tmp_dirs):
        codes = ['20251101007P00001', '20251101007P00002']
        pdf_path = os.path.join(tmp_dirs['upload'], 'scanned_split.pdf')
        _make_scanned_pdf(pdf_path, codes)

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert result.get('success') is True
        assert result['archivos_generados'] == 2

        output_dir = os.path.join(tmp_dirs['processed'], '2025', 'ENERO', 'PROTOCOLO', 'LIBRO_1')
        assert os.path.isdir(output_dir)
        files = os.listdir(output_dir)
        assert len(files) == 2


class TestMixedTextAndScanned:
    def test_mixed_pdf_finds_all_codes(self, tmp_dirs):
        text_codes = ['20251101007P00001', '20251101007P00002']
        scanned_codes = ['20251101007P00003']
        pdf_path = os.path.join(tmp_dirs['upload'], 'mixed.pdf')
        _make_mixed_pdf(pdf_path, text_codes, scanned_codes)

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert result.get('success') is True
        found = set(result['codigos_encontrados'])
        assert '20251101007P00001' in found
        assert '20251101007P00002' in found
        assert '20251101007P00003' in found


class TestCorruptedPDFs:
    def test_truncated_pdf_returns_error(self, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'truncated.pdf')
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4 truncated content here')

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert 'error' in result

    def test_empty_file_returns_error(self, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'empty_file.pdf')
        with open(pdf_path, 'wb') as f:
            f.write(b'')

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert 'error' in result

    def test_non_pdf_content_returns_error(self, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'not_pdf.pdf')
        with open(pdf_path, 'wb') as f:
            f.write(b'This is just a text file masquerading as PDF')

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert 'error' in result


class TestEmptyAndBlankPDFs:
    def test_single_blank_page_no_codes(self, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'single_blank.pdf')
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()

        result = procesar_pdf(pdf_path, '2025', 'ENERO', 'P', 1)
        assert 'error' in result


class TestUploadEdgeCases:
    def test_upload_truncated_pdf_returns_error(self, client, tmp_dirs):
        data = {
            'pdf_file': (io.BytesIO(b'%PDF-1.4 broken'), 'truncated.pdf'),
            'año': '2025',
            'mes': 'ENERO',
            'tipo_libro': 'P',
            'numero_libro': '1',
        }
        resp = client.post('/upload', data=data, content_type='multipart/form-data')
        body = resp.get_json()
        assert 'error' in body

    def test_upload_pdf_with_only_whitespace_text(self, client, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'whitespace.pdf')
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 80), "   \n\t  ", fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with open(pdf_path, 'rb') as f:
            content = f.read()

        data = {
            'pdf_file': (io.BytesIO(content), 'whitespace.pdf'),
            'año': '2025',
            'mes': 'ENERO',
            'tipo_libro': 'P',
            'numero_libro': '1',
        }
        resp = client.post('/upload', data=data, content_type='multipart/form-data')
        body = resp.get_json()
        assert 'error' in body
