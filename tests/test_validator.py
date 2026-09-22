"""Tests for ValidadorNotarial."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.validator import ValidadorNotarial


class TestValidarSecuenciales:
    def setup_method(self):
        self.v = ValidadorNotarial()

    def test_empty_list_returns_error(self):
        result = self.v.validar_secuenciales([])
        assert 'error' in result

    def test_single_code(self):
        codigos = ['20251101007P00001']
        result = self.v.validar_secuenciales(codigos)
        assert result['total_encontrados'] == 1
        assert result['primer_secuencial'] == '00001'
        assert result['ultimo_secuencial'] == '00001'
        assert result['faltantes'] == []
        assert result['es_continuo'] is True

    def test_continuous_sequence(self):
        codigos = [
            '20251101007P00001',
            '20251101007P00002',
            '20251101007P00003',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['total_encontrados'] == 3
        assert result['faltantes'] == []
        assert result['es_continuo'] is True

    def test_sequence_with_gap(self):
        codigos = [
            '20251101007P00001',
            '20251101007P00002',
            '20251101007P00005',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['total_encontrados'] == 3
        assert result['faltantes'] == ['00003', '00004']
        assert result['es_continuo'] is False

    def test_duplicates(self):
        codigos = [
            '20251101007P00001',
            '20251101007P00001',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['total_encontrados'] == 2
        assert result['duplicados'] == ['00001']

    def test_unsorted_codes_are_sorted(self):
        codigos = [
            '20251101007P00005',
            '20251101007P00001',
            '20251101007P00003',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['primer_secuencial'] == '00001'
        assert result['ultimo_secuencial'] == '00005'
        assert result['faltantes'] == ['00002', '00004']

    def test_invalid_code_skipped(self):
        codigos = [
            '20251101007P00001',
            'INVALID',
            '20251101007P00002',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['total_encontrados'] == 2

    def test_range_output(self):
        codigos = [
            '20251101007P00010',
            '20251101007P00020',
        ]
        result = self.v.validar_secuenciales(codigos)
        assert result['rango_esperado'] == '00010 - 00020'
        assert result['faltantes'] == [f'{i:05d}' for i in range(11, 20)]
