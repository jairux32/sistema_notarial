"""Tests for PDFSplitter."""
import os
import sys
import tempfile
import fitz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.pdf_splitter import PDFSplitter


def _make_test_pdf(path, num_pages=3):
    """Create a minimal test PDF with num_pages blank pages."""
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page()
    doc.save(path)
    doc.close()


class TestPDFSplitterOwnsDoc:
    """Test that the splitter opens/closes its own document correctly."""

    def test_splits_with_own_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, 'input.pdf')
            _make_test_pdf(pdf_path, 5)

            splitter = PDFSplitter()
            codigos = ['20251101007P00001', '20251101007P00002']
            output_dir = os.path.join(tmpdir, 'output')

            archivos = splitter.dividir_por_codigos(
                pdf_path, codigos, '2025', '1', 'P', '1', output_dir,
                codigo_a_pagina={'20251101007P00001': 0, '20251101007P00002': 2}
            )
            assert len(archivos) == 2
            for a in archivos:
                assert os.path.exists(a)

    def test_reuses_passed_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, 'input.pdf')
            _make_test_pdf(pdf_path, 5)

            # Open document externally
            external_doc = fitz.open(pdf_path)

            splitter = PDFSplitter()
            codigos = ['20251101007P00001']
            output_dir = os.path.join(tmpdir, 'output')

            archivos = splitter.dividir_por_codigos(
                pdf_path, codigos, '2025', '1', 'P', '1', output_dir,
                codigo_a_pagina={'20251101007P00001': 0},
                pdf_document=external_doc,
            )
            assert len(archivos) == 1
            # Document should NOT be closed (we don't own it)
            assert len(external_doc) == 5
            external_doc.close()

    def test_does_not_close_external_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, 'input.pdf')
            _make_test_pdf(pdf_path, 3)

            external_doc = fitz.open(pdf_path)
            splitter = PDFSplitter()

            splitter.dividir_por_codigos(
                pdf_path, ['20251101007P00001'], '2025', '1', 'P', '1',
                os.path.join(tmpdir, 'output'),
                codigo_a_pagina={'20251101007P00001': 0},
                pdf_document=external_doc,
            )
            # If it wasn't closed, we can still read it
            assert len(external_doc) == 3
            external_doc.close()


class TestPDFSplitterManual:
    def test_manual_split_reuses_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, 'input.pdf')
            _make_test_pdf(pdf_path, 4)

            external_doc = fitz.open(pdf_path)
            splitter = PDFSplitter()

            archivos = splitter.dividir_por_codigos_con_manual(
                pdf_path,
                codigos=['20251101007P00001'],
                codigos_manuales=[('20251101007P00003', 2)],
                año='2025', mes='1', tipo='P', numero_libro='1',
                base_output_dir=os.path.join(tmpdir, 'output'),
                pdf_document=external_doc,
            )
            assert len(archivos) >= 1
            assert len(external_doc) == 4
            external_doc.close()
