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


class TestSchemaCreation:
    def test_creates_table_on_fresh_db(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='editais'")
        assert cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(editais)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == {
            "id", "area", "nome", "status", "link",
            "data_fim_inscricao", "status_hash", "estado_usuario",
            "ultima_atualizacao",
        }
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

    def test_link_igual_ao_indice_cai_no_fallback_de_nome(self, db):
        db.atualizar_concurso("CRM ES", "v1", self.URL_INDICE, url_indice=self.URL_INDICE)

        # Sem link especifico, nome diferente = registro novo.
        assert (
            db.buscar_status_antigo(
                "Concurso CRM ES", link=self.URL_INDICE, url_indice=self.URL_INDICE
            )
            is None
        )

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
