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
        assert columns == {"area", "nome", "status", "link", "ultima_atualizacao"}
        conn.close()

    def test_primary_key_is_composite(self, db_path):
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(editais)")
        pk_cols = [row[1] for row in cursor.fetchall() if row[5] > 0]
        conn.close()

        assert pk_cols == ["area", "nome"]


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
        pk_cols = [row[1] for row in cursor.fetchall() if row[5] > 0]
        cursor.execute("SELECT area FROM editais WHERE nome = 'ANTIGO'")
        area_val = cursor.fetchone()[0]
        conn.close()

        assert pk_cols == ["area", "nome"]
        assert area_val == "TI"

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


class TestConnectionLifecycle:
    def test_fechar_conexao_is_safe_to_call(self, db_path):
        db = DatabaseManager(area="TI", db_path=db_path)
        db.fechar_conexao()

    def test_creates_data_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "data" / "x.db"
        DatabaseManager(area="TI", db_path=str(nested)).fechar_conexao()
        assert nested.exists()
