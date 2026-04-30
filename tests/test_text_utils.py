"""Testes para src/utils/text.py — normalizacao e fingerprint do status."""
from src.utils.text import status_fingerprint


class TestStatusFingerprint:
    def test_identico_gera_mesmo_hash(self):
        assert status_fingerprint("Edital aberto") == status_fingerprint("Edital aberto")

    def test_case_nao_importa(self):
        assert status_fingerprint("Edital Aberto") == status_fingerprint("edital aberto")

    def test_acentos_normalizados(self):
        assert status_fingerprint("inscrições") == status_fingerprint("inscricoes")

    def test_whitespace_colapsado(self):
        assert (
            status_fingerprint("edital   publicado")
            == status_fingerprint("edital publicado")
        )
        assert (
            status_fingerprint("edital\npublicado")
            == status_fingerprint("edital publicado")
        )

    def test_pontuacao_de_borda_removida(self):
        assert (
            status_fingerprint("edital publicado.")
            == status_fingerprint("edital publicado")
        )

    def test_texto_completamente_diferente_gera_hashes_diferentes(self):
        assert (
            status_fingerprint("edital publicado")
            != status_fingerprint("resultado divulgado")
        )

    def test_vazio_retorna_string_vazia(self):
        assert status_fingerprint("") == ""
        assert status_fingerprint(None) == ""

    def test_hash_tem_16_caracteres(self):
        h = status_fingerprint("qualquer coisa")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)
