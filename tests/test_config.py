"""Tests for config mappings."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import MAPEO_TIPOS, MAPEO_TIPOS_INVERSO


class TestMapeoTipos:
    def test_all_letters_mapped(self):
        assert set(MAPEO_TIPOS.keys()) == {'P', 'D', 'C', 'O', 'A'}

    def test_all_names_mapped(self):
        expected_names = {'PROTOCOLO', 'DILIGENCIA', 'CERTIFICACIONES', 'OTROS', 'ARRIENDOS'}
        assert set(MAPEO_TIPOS.values()) == expected_names

    def test_inverse_mapping_roundtrip(self):
        for letter, name in MAPEO_TIPOS.items():
            assert MAPEO_TIPOS_INVERSO[name] == letter

    def test_inverse_is_automatic(self):
        assert MAPEO_TIPOS_INVERSO == {v: k for k, v in MAPEO_TIPOS.items()}

    def test_specific_mappings(self):
        assert MAPEO_TIPOS['P'] == 'PROTOCOLO'
        assert MAPEO_TIPOS['D'] == 'DILIGENCIA'
        assert MAPEO_TIPOS['C'] == 'CERTIFICACIONES'
        assert MAPEO_TIPOS['O'] == 'OTROS'
        assert MAPEO_TIPOS['A'] == 'ARRIENDOS'
