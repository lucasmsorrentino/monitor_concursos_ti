"""Testes para src/database/manager.py — persistencia SQLite com PK (area, nome)."""
import sqlite3

import pytest

from src.database.manager import DatabaseManager


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_concursos.db")


@pytest.fixture
def db(db_path):
    manager = DatabaseManager(area="TI", db_path=db_path)
    yield manager
    manager.fechar_conexao()


# Oracle do schema v6: conjunto escrito a mao a partir da SPEC-001 (secao 3.5)
# e conferido por PRAGMA table_info, que e fonte independente do codigo de
# migracao.
COLUNAS_V6 = {
    "id", "area", "nome", "status", "link",
    "data_fim_inscricao", "status_hash", "fase", "estado_usuario",
    "fonte", "pci_id",                                        # v5
    "uf", "regiao", "esfera", "cargos_total", "salario_teto",  # v6
    "elegibilidade", "motivo_filtro",                          # v6
    "ultima_atualizacao",
}

COLUNAS_NOVAS_V6 = {
    "uf", "regiao", "esfera", "cargos_total", "salario_teto",
    "elegibilidade", "motivo_filtro",
}


def _criar_banco_v5(db_path):
    """Monta a mao um banco no formato que o v5 deixava, com duas linhas."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE editais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            nome TEXT NOT NULL,
            status TEXT NOT NULL,
            link TEXT,
            data_fim_inscricao TEXT,
            status_hash TEXT,
            fase TEXT,
            estado_usuario TEXT NOT NULL DEFAULT 'ativo',
            fonte TEXT,
            pci_id TEXT,
            ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, nome)
        )
        """
    )
    conn.execute(
        "INSERT INTO editais (area, nome, status, link, fonte, pci_id)"
        " VALUES ('TI', 'SEFIN RO', 'edital publicado', 'https://x/sefin-ro',"
        " 'pci', 'pci-123')"
    )
    conn.execute(
        "INSERT INTO editais (area, nome, status, link, fonte, fase, data_fim_inscricao)"
        " VALUES ('TI', 'TRF1', 'previsto', 'https://x/trf1', 'gran', 'previsto', '2026-12-31')"
    )
    conn.commit()
    conn.close()


class TestSchemaCreation:
    def test_creates_table_on_fresh_db(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='editais'")
        assert cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(editais)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == COLUNAS_V6
        conn.close()

    def test_primary_key_is_autoincrement_id(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(editais)")
        pk_cols = [row[1] for row in cursor.fetchall() if row[5] > 0]
        conn.close()

        assert pk_cols == ["id"]

    def test_area_nome_is_unique(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='editais'")
        schema_sql = cursor.fetchone()[0]
        conn.close()

        assert "UNIQUE(area, nome)" in schema_sql or "UNIQUE (area, nome)" in schema_sql


class TestCrud:
    def test_insert_new_concurso(self, db):
        db.atualizar_concurso("TRF1", "edital publicado", "https://x/1")

        assert db.buscar_status_antigo("TRF1") == "edital publicado"

    def test_update_replaces_existing(self, db):
        db.atualizar_concurso("TRF1", "v1", "https://x/1")
        db.atualizar_concurso("TRF1", "v2", "https://x/2")

        assert db.buscar_status_antigo("TRF1") == "v2"

    def test_missing_concurso_returns_none(self, db):
        assert db.buscar_status_antigo("INEXISTENTE") is None

    def test_area_isolation(self, db_path):
        """Mesmo nome em areas diferentes nao colide."""
        db_ti = DatabaseManager(area="TI", db_path=db_path)
        db_edu = DatabaseManager(area="EDU", db_path=db_path)

        db_ti.atualizar_concurso("MEC", "status TI", "")
        db_edu.atualizar_concurso("MEC", "status Educacao", "")

        assert db_ti.buscar_status_antigo("MEC") == "status TI"
        assert db_edu.buscar_status_antigo("MEC") == "status Educacao"

        db_ti.fechar_conexao()
        db_edu.fechar_conexao()


class TestMigration:
    def test_migrates_legacy_single_area_schema(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE editais (
                nome TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                link TEXT,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute(
            "INSERT INTO editais (nome, status, link) VALUES ('ANTIGO', 'v_antigo', 'https://old')"
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(area="TI", db_path=db_path)

        assert db.buscar_status_antigo("ANTIGO") == "v_antigo"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(editais)")
        cols_info = cursor.fetchall()
        pk_cols = [row[1] for row in cols_info if row[5] > 0]
        col_names = {row[1] for row in cols_info}
        cursor.execute("SELECT area, estado_usuario FROM editais WHERE nome = 'ANTIGO'")
        area_val, estado_val = cursor.fetchone()
        conn.close()

        assert pk_cols == ["id"]
        assert "estado_usuario" in col_names
        assert area_val == "TI"
        assert estado_val == "ativo"

        db.fechar_conexao()

    def test_migrates_v2_to_v3_adding_id_column(self, db_path):
        """v2 (PK composta area+nome) migra para v3 (id autoincrement)."""
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE editais (
                area TEXT NOT NULL,
                nome TEXT NOT NULL,
                status TEXT NOT NULL,
                link TEXT,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (area, nome)
            )
        ''')
        conn.execute(
            "INSERT INTO editais (area, nome, status) VALUES ('TI', 'TRF1', 'aberto')"
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(area="TI", db_path=db_path)

        registro = db.buscar_registro("TRF1")
        assert registro is not None
        assert registro["status"] == "aberto"
        assert registro["id"] >= 1
        assert registro["estado_usuario"] == "ativo"
        db.fechar_conexao()

    def test_migration_is_idempotent(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'editais%'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1


class TestSchemaV6:
    """Schema v6: sete colunas novas, nas duas pontas (banco novo e migrado)."""

    def test_banco_novo_tem_as_colunas_do_v6(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(editais)")
        colunas = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert COLUNAS_NOVAS_V6 <= colunas

    def test_migracao_do_v5_acrescenta_as_colunas(self, db_path):
        _criar_banco_v5(db_path)
        db = DatabaseManager(area="TI", db_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(editais)")
        colunas = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert COLUNAS_NOVAS_V6 <= colunas

        # Nada se perde: as duas linhas do v5 continuam la, com os valores
        # de fonte e pci_id intactos e as colunas novas NULL.
        reg_sefin = db.buscar_registro("SEFIN RO")
        reg_trf1 = db.buscar_registro("TRF1")
        assert reg_sefin is not None
        assert reg_trf1 is not None
        assert reg_sefin["status"] == "edital publicado"
        assert reg_sefin["fonte"] == "pci"
        assert reg_sefin["pci_id"] == "pci-123"
        assert reg_trf1["fonte"] == "gran"
        assert reg_trf1["fase"] == "previsto"
        assert reg_trf1["data_fim_inscricao"] == "2026-12-31"
        for coluna in COLUNAS_NOVAS_V6:
            assert reg_sefin[coluna] is None
            assert reg_trf1[coluna] is None

        db.fechar_conexao()

    def test_migracao_e_idempotente(self, db_path):
        _criar_banco_v5(db_path)

        colunas_por_abertura = []
        for _ in range(3):
            DatabaseManager(area="TI", db_path=db_path).fechar_conexao()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(editais)")
            colunas_por_abertura.append({row[1] for row in cursor.fetchall()})
            conn.close()

        # Da segunda para a terceira abertura nenhuma coluna muda...
        assert colunas_por_abertura[1] == colunas_por_abertura[2]
        # ...e o conjunto final e exatamente o do v6, completo.
        assert colunas_por_abertura[2] == COLUNAS_V6


class TestEstadoUsuario:
    def test_default_estado_is_ativo(self, db):
        id_ = db.atualizar_concurso("TRF1", "aberto", "https://x/1")
        reg = db.buscar_registro("TRF1")
        assert reg["estado_usuario"] == "ativo"
        assert reg["id"] == id_

    def test_atualizar_estado_usuario_aceita_estados_validos(self, db):
        id_ = db.atualizar_concurso("TRF1", "aberto", "https://x/1")
        for estado in ("seguindo", "ignorado", "ativo"):
            assert db.atualizar_estado_usuario(id_, estado) is True
            assert db.buscar_registro("TRF1")["estado_usuario"] == estado

    def test_atualizar_estado_usuario_rejeita_invalido(self, db):
        id_ = db.atualizar_concurso("TRF1", "aberto", "https://x/1")
        assert db.atualizar_estado_usuario(id_, "qualquer") is False
        assert db.buscar_registro("TRF1")["estado_usuario"] == "ativo"

    def test_atualizar_estado_usuario_id_inexistente(self, db):
        assert db.atualizar_estado_usuario(9999, "ignorado") is False


class TestGravacaoCamposV6:
    """Gravacao dos sete campos: descricao se preserva, decisao se renova."""

    def test_atualizar_concurso_grava_campos_novos(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "edital publicado", "https://x/sefaz-sc",
            uf="SC", regiao="Sul", esfera="estadual",
            cargos_total=42, salario_teto=18540.71,
            elegibilidade="filtrado", motivo_filtro="abaixo_do_corte",
        )

        reg = db.buscar_registro("SEFAZ SC")
        assert reg["uf"] == "SC"
        assert reg["regiao"] == "Sul"
        assert reg["esfera"] == "estadual"
        assert reg["cargos_total"] == 42
        assert reg["salario_teto"] == 18540.71
        assert reg["elegibilidade"] == "filtrado"
        assert reg["motivo_filtro"] == "abaixo_do_corte"

    def test_coalesce_preserva_uf_quando_vem_none(self, db):
        db.atualizar_concurso("SEFAZ SC", "v1", "https://x/sefaz-sc", uf="SC")
        # Fonte que nao conhece a UF (None) nao apaga o que a outra descobriu.
        db.atualizar_concurso("SEFAZ SC", "v2", "https://x/sefaz-sc", uf=None)
        assert db.buscar_registro("SEFAZ SC")["uf"] == "SC"

    def test_coalesce_preserva_salario_teto_quando_vem_none(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sefaz-sc", salario_teto=18540.71
        )
        db.atualizar_concurso(
            "SEFAZ SC", "v2", "https://x/sefaz-sc", salario_teto=None
        )
        assert db.buscar_registro("SEFAZ SC")["salario_teto"] == 18540.71

    def test_elegibilidade_e_sobrescrita_quando_vem_valor(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sefaz-sc", elegibilidade="filtrado"
        )
        # Decisao nova vence decisao velha: o edital saiu, o teto mudou.
        db.atualizar_concurso(
            "SEFAZ SC", "v2", "https://x/sefaz-sc", elegibilidade="elegivel"
        )
        assert db.buscar_registro("SEFAZ SC")["elegibilidade"] == "elegivel"

    def test_elegibilidade_e_preservada_quando_vem_none(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sefaz-sc", elegibilidade="filtrado"
        )
        # Rodada em que o filtro esta desligado nao apaga a decisao gravada.
        db.atualizar_concurso("SEFAZ SC", "v2", "https://x/sefaz-sc")
        assert db.buscar_registro("SEFAZ SC")["elegibilidade"] == "filtrado"

    def test_linha_pre_v6_nao_e_tocada(self, db_path):
        _criar_banco_v5(db_path)
        db = DatabaseManager(area="TI", db_path=db_path)

        # Gravacao que nao passa o campo: elegibilidade nulo segue nulo.
        db.atualizar_concurso("SEFIN RO", "fase nova")
        assert db.buscar_registro("SEFIN RO")["elegibilidade"] is None
        db.fechar_conexao()


class TestBuscarRegistroEdataFim:
    def test_retorna_todos_os_campos(self, db):
        db.atualizar_concurso(
            "TRF1", "aberto", "https://x/1",
            status_hash="abc123", data_fim_inscricao="2026-12-31",
        )
        reg = db.buscar_registro("TRF1")
        assert reg["nome"] == "TRF1"
        assert reg["status_hash"] == "abc123"
        assert reg["data_fim_inscricao"] == "2026-12-31"
        assert reg["estado_usuario"] == "ativo"
        assert reg["id"] >= 1

    def test_retorna_none_quando_inexistente(self, db):
        assert db.buscar_registro("INEXISTENTE") is None

    def test_id_preservado_entre_updates(self, db):
        """id nao muda entre atualizacoes — critico para callback_data do Telegram."""
        id1 = db.atualizar_concurso("TRF1", "v1", "https://x/1")
        id2 = db.atualizar_concurso("TRF1", "v2", "https://x/1")
        assert id1 == id2

    def test_busca_por_nome_ignora_capitalizacao(self, db):
        """LLM varia capitalizacao entre ciclos ('SEDUC AL' vs 'Seduc AL') —
        nao pode virar registro novo nem notificacao NOVO duplicada."""
        db.atualizar_concurso("Concurso SEDUC AL", "v1", "https://x/seduc-al/")
        reg = db.buscar_registro("Concurso Seduc AL", link="https://x/outro-link/")
        assert reg is not None
        assert reg["status"] == "v1"

    def test_upsert_por_nome_ignora_capitalizacao(self, db):
        """Upsert com nome em capitalizacao diferente atualiza a linha existente."""
        id1 = db.atualizar_concurso("Concurso SEDUC AL", "v1", "https://x/a/")
        id2 = db.atualizar_concurso("Concurso Seduc AL", "v2", "https://x/b/")
        assert id1 == id2


class TestLinkCanonicalIdentity:
    """Dedupe por link quando o LLM extrai variacoes do mesmo edital."""

    URL_INDICE = "https://blog.grancursosonline.com.br/concursos-ti/"
    LINK_EDITAL = "https://blog.grancursosonline.com.br/concurso-crm-es/"

    def test_link_especifico_serve_de_chave(self, db):
        db.atualizar_concurso(
            "CRM ES", "v1", self.LINK_EDITAL, url_indice=self.URL_INDICE
        )
        # LLM extrai o mesmo edital com nome diferente no proximo ciclo.
        status = db.buscar_status_antigo(
            "Concurso CRM ES - Conselho Regional de Medicina do ES",
            link=self.LINK_EDITAL,
            url_indice=self.URL_INDICE,
        )
        assert status == "v1"

    def test_upsert_por_link_sobrescreve_nome(self, db):
        db.atualizar_concurso(
            "CRM ES", "v1", self.LINK_EDITAL, url_indice=self.URL_INDICE
        )
        db.atualizar_concurso(
            "Concurso CRM ES - variacao longa",
            "v2",
            self.LINK_EDITAL,
            url_indice=self.URL_INDICE,
        )

        conn = sqlite3.connect(db.db_path)
        rows = conn.execute(
            "SELECT nome, status FROM editais WHERE link = ?", (self.LINK_EDITAL,)
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0] == ("Concurso CRM ES - variacao longa", "v2")

    def test_link_igual_ao_indice_casa_o_mesmo_orgao_por_entidade(self, db):
        """Sem link especifico, "Concurso CRM ES" e "CRM ES" sao o MESMO orgao.

        Ate 08/2026 isso virava uma linha nova, e o banco acumulava duplicatas
        do mesmo orgao com metade da historia em cada uma. A varredura de 08/08
        logou quatro casos reais (SEFIN RO, Seduc AL, IFFar, UEAP). O casamento
        por entidade em `buscar_registro` fecha esse buraco.
        """
        db.atualizar_concurso("CRM ES", "v1", self.URL_INDICE, url_indice=self.URL_INDICE)

        assert (
            db.buscar_status_antigo(
                "Concurso CRM ES", link=self.URL_INDICE, url_indice=self.URL_INDICE
            )
            == "v1"
        )

    def test_orgaos_parecidos_mas_distintos_nao_se_fundem(self, db):
        """Guarda-corpo do casamento por entidade: cidade diferente = orgao diferente."""
        db.atualizar_concurso("Prefeitura de Ponta Grossa - PR", "v1", "")

        assert db.buscar_status_antigo("Prefeitura de Ponta Porã - MS") is None
        assert db.buscar_status_antigo("Prefeitura de Ponta Grossa") == "v1"

    def test_sem_link_mantem_comportamento_legado(self, db):
        db.atualizar_concurso("TRF1", "v1", "")
        assert db.buscar_status_antigo("TRF1") == "v1"

    def test_update_por_link_nao_colide_com_nome_de_outra_linha(self, db):
        """Quando LLM da um nome que ja existe em outra linha, mantem o nome antigo.

        Cenario: row_A(link=/a, nome='Concurso X'), row_B(link=/b, nome='Concurso Y').
        LLM extrai nome='Concurso Y' com link='/a'. Sem protecao, o UPDATE por
        link colidiria com UNIQUE(area, nome) de row_B.
        """
        id_a = db.atualizar_concurso(
            "Concurso X", "v1", self.LINK_EDITAL, url_indice=self.URL_INDICE
        )
        outro_link = "https://blog.grancursosonline.com.br/concurso-b/"
        db.atualizar_concurso(
            "Concurso Y", "v1", outro_link, url_indice=self.URL_INDICE
        )

        # Colisao: nome='Concurso Y' chegando com link de row_A.
        id_retornado = db.atualizar_concurso(
            "Concurso Y", "v2-novo", self.LINK_EDITAL, url_indice=self.URL_INDICE
        )

        assert id_retornado == id_a  # mesmo id preservado
        reg_a = db.buscar_registro("Concurso X", link=self.LINK_EDITAL, url_indice=self.URL_INDICE)
        assert reg_a["nome"] == "Concurso X"  # nome antigo preservado
        assert reg_a["status"] == "v2-novo"  # status atualizado
        reg_b = db.buscar_registro("Concurso Y", link=outro_link, url_indice=self.URL_INDICE)
        assert reg_b is not None  # row_B intacta


class TestConnectionLifecycle:
    def test_fechar_conexao_is_safe_to_call(self, db_path):
        db = DatabaseManager(area="TI", db_path=db_path)
        db.fechar_conexao()

    def test_creates_data_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "data" / "x.db"
        DatabaseManager(area="TI", db_path=str(nested)).fechar_conexao()
        assert nested.exists()
