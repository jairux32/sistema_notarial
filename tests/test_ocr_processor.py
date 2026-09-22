"""Tests for OCR code detection and filtering."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.ocr_processor import ProcesadorOCR


class TestFiltrarCodigos:
    def setup_method(self):
        self.proc = ProcesadorOCR()

    def test_filters_by_type_letter(self):
        raw = [
            '20251101007P00001',
            '20251101007P00002',
            '20251101007D00001',  # wrong type letter (D != P)
        ]
        result = self.proc._filtrar_codigos(raw, '2025', 'P')
        assert '20251101007P00001' in result
        assert '20251101007P00002' in result
        assert '20251101007D00001' not in result

    def test_deduplicates(self):
        raw = ['20251101007P00001', '20251101007P00001']
        result = self.proc._filtrar_codigos(raw, '2025', 'P')
        assert result.count('20251101007P00001') == 1

    def test_invalid_length_rejected(self):
        raw = ['20251101007P0000', '20251101007P000012']
        result = self.proc._filtrar_codigos(raw, '2025', 'P')
        assert len(result) == 0

    def test_non_numeric_sequential_rejected(self):
        raw = ['20251101007PXXXXX']
        result = self.proc._filtrar_codigos(raw, '2025', 'P')
        assert len(result) == 0

    def test_sequential_above_999_rejected(self):
        raw = ['20251101007P01000']
        result = self.proc._filtrar_codigos(raw, '2025', 'P')
        assert len(result) == 0


class TestDetectarCodigosFaltantes:
    def setup_method(self):
        self.proc = ProcesadorOCR()

    def test_no_faltantes(self):
        codigos = ['20251101007P00001', '20251101007P00002', '20251101007P00003']
        faltantes = self.proc.detectar_codigos_faltantes(codigos, '2025', 'P')
        assert faltantes == []

    def test_one_faltante(self):
        codigos = ['20251101007P00001', '20251101007P00003']
        faltantes = self.proc.detectar_codigos_faltantes(codigos, '2025', 'P')
        assert '20251101007P00002' in faltantes

    def test_multiple_faltantes(self):
        codigos = ['20251101007P00001', '20251101007P00005']
        faltantes = self.proc.detectar_codigos_faltantes(codigos, '2025', 'P')
        assert len(faltantes) == 3
        assert '20251101007P00002' in faltantes
        assert '20251101007P00003' in faltantes
        assert '20251101007P00004' in faltantes

    def test_empty_codigos(self):
        faltantes = self.proc.detectar_codigos_faltantes([], '2025', 'P')
        assert faltantes == []
