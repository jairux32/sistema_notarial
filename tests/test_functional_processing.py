import os
import uuid
from unittest.mock import patch

import fitz
import pytest

from conftest import _flask_app, procesar_pdf, procesamiento_cache


class TestFullPipelineWithCodes:
    def test_success_with_three_codes(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'three_codes.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert result['success'] is True
        assert result['archivos_generados'] == 3
        assert len(result['codigos_encontrados']) == 3
        assert result['validacion']['faltantes'] == []
        assert len(result['hashes']) == 3
        assert isinstance(result['session_id'], str)
        uuid.UUID(result['session_id'])


class TestPipelineGapInSequence:
    def test_gap_detected(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00005',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'gap_codes.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert '00003' in result['validacion']['faltantes']
        assert '00004' in result['validacion']['faltantes']
        assert result['validacion']['es_continuo'] is False


class TestPipelineOutputFolderStructure:
    def test_output_dir(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'folder_test.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 3)

        assert '2026/DILIGENCIA/' in result['ruta_salida']


class TestPipelineStoresCache:
    def test_session_stored_in_cache(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'cache_test.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        session_id = result['session_id']
        assert session_id in procesamiento_cache
        cached = procesamiento_cache[session_id]
        assert cached['filepath'] == pdf_path
        assert cached['año'] == '2026'
        assert cached['mes'] == 'MARZO'
        assert cached['tipo_libro'] == 'D'
        assert cached['numero_libro'] == 1
        assert cached['codigos_encontrados'] == result['codigos_encontrados']
        assert len(cached['archivos_generados']) == 3


class TestPipelineGeneratesReport:
    def test_report_file_exists(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'report_test.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        report_path = result['reporte_path']
        assert os.path.exists(report_path)
        with open(report_path, 'rb') as f:
            header = f.read(5)
        assert header == b'%PDF-'


class TestPipelineCalculatesHashes:
    def test_hashes_dict_keys(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'hash_test.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert len(result['hashes']) == 3
        for key in result['hashes']:
            assert isinstance(key, str)
            assert key.endswith('.pdf')
            assert isinstance(result['hashes'][key], str)
            assert len(result['hashes'][key]) == 64


class TestPipelineNoCodesReturnsError:
    def test_blank_pdf_error(self, app_instance, tmp_dirs):
        pdf_path = os.path.join(tmp_dirs['upload'], 'blank.pdf')
        doc = fitz.open()
        for _ in range(3):
            doc.new_page(width=595, height=842)
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert 'error' in result


class TestPipelineSingleCode:
    def test_one_code(self, app_instance, tmp_dirs):
        codes = ['20261101007D00001']
        pdf_path = os.path.join(tmp_dirs['upload'], 'single_code.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        with app_instance.app_context():
            result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert result['success'] is True
        assert result['archivos_generados'] == 1
        assert result['validacion']['total_encontrados'] == 1
        assert result['validacion']['faltantes'] == []


class TestPipelineReusesSingleDocument:
    def test_fitz_open_called_once(self, app_instance, tmp_dirs):
        codes = [
            '20261101007D00001',
            '20261101007D00002',
            '20261101007D00003',
        ]
        pdf_path = os.path.join(tmp_dirs['upload'], 'reuse_test.pdf')
        doc = fitz.open()
        for code in codes:
            page = doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(50, 80), code, fontsize=14, fontname="helv")
        doc.save(pdf_path)
        doc.close()

        original_open = fitz.open
        file_opens = 0

        def counting_open(*args, **kwargs):
            nonlocal file_opens
            if args:
                file_opens += 1
            return original_open(*args, **kwargs)

        with app_instance.app_context():
            with patch('fitz.open', side_effect=counting_open):
                result = procesar_pdf(pdf_path, '2026', 'MARZO', 'D', 1)

        assert result['success'] is True
        assert file_opens == 1
