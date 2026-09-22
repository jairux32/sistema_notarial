import sys
import os
import io
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from utils.ocr_processor import ProcesadorOCR


def make_scanned_pdf(path, num_pages):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        img = Image.new('RGB', (595, 842), 'white')
        draw = ImageDraw.Draw(img)
        code = f"20251101007P{i+1:05d}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        draw.text((80, 100), code, fill='black', font=font)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        page.insert_image(page.rect, stream=img_bytes.getvalue())
    doc.save(path)
    doc.close()


def make_text_pdf(path, num_pages):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        code = f"20251101007P{i+1:05d}"
        page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
    doc.save(path)
    doc.close()


def serial_ocr(pdf_path):
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text('blocks')
        texto_superior = ""
        for b in blocks:
            x0, y0, x1, y1 = b[:4]
            content = b[4]
            if y0 < 150 and not content.startswith('<image:'):
                texto_superior += content + "\n"
        if len(texto_superior.strip()) < 10:
            rect = page.rect
            top_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(rect.y0 + 200, rect.y1))
            pix = page.get_pixmap(clip=top_rect)
            temp_img = tempfile.mktemp(suffix='.png')
            pix.save(temp_img)
            pytesseract.image_to_string(Image.open(temp_img), lang='spa')
            os.unlink(temp_img)
    doc.close()


def parallel_ocr(pdf_path):
    procesador = ProcesadorOCR()
    procesador._buscar_en_pdf(pdf_path, '2025', 'P')


def bench_text_layer(pdf_path):
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text('blocks')
        texto_superior = ""
        for b in blocks:
            x0, y0, x1, y1 = b[:4]
            content = b[4]
            if y0 < 150 and not content.startswith('<image:'):
                texto_superior += content + "\n"
        _ = texto_superior.strip()
    doc.close()


def run_benchmarks():
    tmpdir = tempfile.mkdtemp(prefix='ocr_bench_')
    sizes = [10, 50, 100]
    results = {}

    try:
        for size in sizes:
            scanned_path = os.path.join(tmpdir, f"scanned_{size}.pdf")
            text_path = os.path.join(tmpdir, f"text_{size}.pdf")
            make_scanned_pdf(scanned_path, size)
            make_text_pdf(text_path, size)

            t0 = time.perf_counter()
            serial_ocr(scanned_path)
            serial_time = time.perf_counter() - t0

            t0 = time.perf_counter()
            parallel_ocr(scanned_path)
            parallel_time = time.perf_counter() - t0

            t0 = time.perf_counter()
            bench_text_layer(text_path)
            text_time = time.perf_counter() - t0

            speedup = serial_time / parallel_time if parallel_time > 0 else 0
            results[size] = {
                'serial': serial_time,
                'parallel': parallel_time,
                'speedup': speedup,
                'text': text_time,
            }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("=== OCR Performance Benchmark ===")
    print()
    print("Scanned PDF (image-only, forces OCR):")
    for size in sizes:
        r = results[size]
        print(f"  {size:>3} pages:  Serial={r['serial']:.2f}s  Parallel={r['parallel']:.2f}s  Speedup={r['speedup']:.2f}x")
    print()
    print("Text-layer PDF (no OCR needed):")
    for size in sizes:
        r = results[size]
        print(f"  {size:>3} pages:  {r['text']:.2f}s")


if __name__ == '__main__':
    run_benchmarks()
