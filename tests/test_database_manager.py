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
        """(area, nome) e unico entre linhas SEM pci_id; o pci_id separa editais.

        Ate a SPEC-003 a unicidade era o UNIQUE(area, nome) de tabela, que
        impedia dois editais do mesmo orgao. Agora e o indice unico
        (area, nome, COALESCE(pci_id, '')): o nome repetido sem pci_id continua
        barrado, e dois pci_id distintos com o mesmo nome coexistem.
        """
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO editais (area, nome, status, pci_id) VALUES ('TI', 'IFSP', 'a', '296044')"
            )
            conn.execute(
                "INSERT INTO editais (area, nome, status, pci_id) VALUES ('TI', 'IFSP', 'b', '296538')"
            )
            conn.execute("INSERT INTO editais (area, nome, status) VALUES ('TI', 'TRF1', 'a')")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO editais (area, nome, status) VALUES ('TI', 'TRF1', 'b')")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO editais (area, nome, status, pci_id) VALUES ('TI', 'IFSP', 'c', '296044')"
                )
        finally:
            conn.close()


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


class TestListarFiltrados:
    """listar_filtrados: o que o resumo semanal le da area."""

    DESDE_ANTIGO = "2000-01-01 00:00:00"

    def test_listar_filtrados_so_traz_filtrado(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sc", uf="SC", salario_teto=9000.0,
            elegibilidade="filtrado", motivo_filtro="abaixo_do_corte",
        )
        db.atualizar_concurso(
            "SEFAZ PR", "v1", "https://x/pr", uf="PR", elegibilidade="elegivel",
        )
        # Linha sem decisao gravada (pre-v6): conta como elegivel, nao lista.
        db.atualizar_concurso("SEFAZ RS", "v1", "https://x/rs", uf="RS")

        lista = db.listar_filtrados(self.DESDE_ANTIGO)

        assert [r["nome"] for r in lista] == ["SEFAZ SC"]
        unico = lista[0]
        assert unico["uf"] == "SC"
        assert unico["salario_teto"] == 9000.0
        assert unico["motivo_filtro"] == "abaixo_do_corte"
        assert unico["link"] == "https://x/sc"

    def test_listar_filtrados_respeita_desde(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sc", elegibilidade="filtrado"
        )
        db.atualizar_concurso(
            "SEFAZ PR", "v1", "https://x/pr", elegibilidade="filtrado"
        )
        # ultima_atualizacao nao vem pela interface publica; o arranjo das
        # datas entra por SQL direto, so para montar o cenario.
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            "UPDATE editais SET ultima_atualizacao = ? WHERE nome = 'SEFAZ SC'",
            ("2026-11-10 08:00:00",),
        )
        conn.execute(
            "UPDATE editais SET ultima_atualizacao = ? WHERE nome = 'SEFAZ PR'",
            ("2026-11-20 08:00:00",),
        )
        conn.commit()
        conn.close()

        lista = db.listar_filtrados("2026-11-15 00:00:00")

        assert [r["nome"] for r in lista] == ["SEFAZ PR"]

    def test_listar_filtrados_nao_vaza_area(self, db_path):
        db_ti = DatabaseManager(area="TI", db_path=db_path)
        db_edu = DatabaseManager(area="EDUCACAO", db_path=db_path)
        db_ti.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sc", elegibilidade="filtrado"
        )
        db_edu.atualizar_concurso(
            "Prefeitura de X", "v1", "https://x/pref", elegibilidade="filtrado"
        )

        nomes_ti = [r["nome"] for r in db_ti.listar_filtrados(self.DESDE_ANTIGO)]
        nomes_edu = [r["nome"] for r in db_edu.listar_filtrados(self.DESDE_ANTIGO)]

        assert nomes_ti == ["SEFAZ SC"]
        assert nomes_edu == ["Prefeitura de X"]

        db_ti.fechar_conexao()
        db_edu.fechar_conexao()

    def test_listar_filtrados_ordena_por_teto_desc_com_null_no_fim(self, db):
        db.atualizar_concurso(
            "Teto Medio", "v1", "https://x/m", uf="SC",
            salario_teto=3000.0, elegibilidade="filtrado",
        )
        db.atualizar_concurso(
            "Teto Alto", "v1", "https://x/a", uf="SC",
            salario_teto=12000.0, elegibilidade="filtrado",
        )
        db.atualizar_concurso(
            "Sem Teto", "v1", "https://x/s", uf="SC", elegibilidade="filtrado",
        )

        lista = db.listar_filtrados(self.DESDE_ANTIGO)

        assert [(r["nome"], r["salario_teto"]) for r in lista] == [
            ("Teto Alto", 12000.0),
            ("Teto Medio", 3000.0),
            ("Sem Teto", None),
        ]

    def test_listar_filtrados_futuro_vazio(self, db):
        db.atualizar_concurso(
            "SEFAZ SC", "v1", "https://x/sc", elegibilidade="filtrado"
        )
        assert db.listar_filtrados("2099-01-01 00:00:00") == []


class TestConnectionLifecycle:
    def test_fechar_conexao_is_safe_to_call(self, db_path):
        db = DatabaseManager(area="TI", db_path=db_path)
        db.fechar_conexao()

    def test_creates_data_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "data" / "x.db"
        DatabaseManager(area="TI", db_path=str(nested)).fechar_conexao()
        assert nested.exists()


# ---------------------------------------------------------------------------
# Identidade do concurso: o pci_id que discorda vence o nome (SPEC-003, 3.1)
# ---------------------------------------------------------------------------
#
# Oraculo: os dois editais reais do IFSP que dividiam uma linha so em
# 25/11/2026. O 296044 (professor substituto) esta em
# docs/CONTABILIDADE-POS-DEPLOY.md; o 296538 (tecnico-administrativo, prazo
# 2027-01-04) esta na fixture tests/fixtures/pci_mcp/tools_call_tecnico_em_
# informatica.json. O prazo do 296044 foi escrito a mao: o que importa e que
# os dois prazos sao distintos.

IFSP_NOME = "IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo - SP"
IFSP_NOME_SEM_UF = "IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo"

IFSP_SUBSTITUTO_PCI = "296044"
IFSP_SUBSTITUTO_LINK = (
    "https://www.pciconcursos.com.br/noticias/"
    "ifsp-sp-abre-processo-seletivo-para-professor-substituto-com-salarios-de-ate-8340"
)
IFSP_SUBSTITUTO_PRAZO = "2026-12-05"

IFSP_TECNICO_PCI = "296538"
IFSP_TECNICO_LINK = (
    "https://www.pciconcursos.com.br/noticias/"
    "ifsp-abre-concurso-publico-para-cargos-tecnico-administrativos"
)
IFSP_TECNICO_PRAZO = "2027-01-04"

URL_INDICE_PCI = "https://mcp.pciconcursos.com.br/mcp"


def _gravar_substituto(db, nome=IFSP_NOME, link=IFSP_SUBSTITUTO_LINK):
    return db.atualizar_concurso(
        nome, "Professor substituto", link, url_indice=URL_INDICE_PCI,
        data_fim_inscricao=IFSP_SUBSTITUTO_PRAZO, fase="inscricoes_abertas",
        fonte="pci_mcp", pci_id=IFSP_SUBSTITUTO_PCI,
    )


def _gravar_tecnico(db, nome=IFSP_NOME, link=IFSP_TECNICO_LINK):
    return db.atualizar_concurso(
        nome, "Tecnico-administrativo", link, url_indice=URL_INDICE_PCI,
        data_fim_inscricao=IFSP_TECNICO_PRAZO, fase="inscricoes_abertas",
        fonte="pci_mcp", pci_id=IFSP_TECNICO_PCI,
    )


class TestIdentidadePeloPciId:
    """R-80 a R-83: item com pci_id nao casa com linha de outro pci_id."""

    def test_pci_id_diferente_nao_casa_por_nome(self, db):
        _gravar_substituto(db, link="")

        assert db.buscar_registro(IFSP_NOME, pci_id=IFSP_TECNICO_PCI) is None

    def test_pci_id_diferente_nao_casa_por_link(self, db):
        _gravar_substituto(db, link=IFSP_SUBSTITUTO_LINK)

        assert db.buscar_registro(
            IFSP_NOME, link=IFSP_SUBSTITUTO_LINK, url_indice=URL_INDICE_PCI,
            pci_id=IFSP_TECNICO_PCI,
        ) is None

    def test_pci_id_diferente_nao_casa_por_entidade(self, db):
        # Sem o " - SP" o nome nao casa por (area, nome), so por entidade.
        _gravar_substituto(db, link="")

        assert db.buscar_registro(IFSP_NOME_SEM_UF, pci_id=IFSP_TECNICO_PCI) is None

    def test_pci_id_casa_com_linha_sem_pci_id_e_rechaveia(self, db):
        """R-81, ADR-0001: linha legada sem pci_id e rechaveada, nao duplicada."""
        id_legado = db.atualizar_concurso(
            IFSP_NOME, "legado das portas de HTML", IFSP_TECNICO_LINK,
            url_indice=URL_INDICE_PCI, fonte="pci",
        )

        id_mcp = _gravar_tecnico(db, link="")

        assert id_mcp == id_legado
        registro = db.buscar_registro("nome qualquer", pci_id=IFSP_TECNICO_PCI)
        assert registro["id"] == id_legado
        assert registro["pci_id"] == IFSP_TECNICO_PCI

    def test_item_sem_pci_id_mantem_a_ordem_de_hoje(self, db):
        """R-82: Gran e portas de HTML casam por link, nome e entidade como antes."""
        id_ = _gravar_substituto(db)

        por_link = db.buscar_registro(
            "Concurso IFSP", link=IFSP_SUBSTITUTO_LINK, url_indice=URL_INDICE_PCI
        )
        por_nome = db.buscar_registro(IFSP_NOME.upper())
        por_entidade = db.buscar_registro(IFSP_NOME_SEM_UF)

        assert por_link["id"] == por_nome["id"] == por_entidade["id"] == id_

    def test_dois_editais_do_mesmo_orgao_viram_duas_linhas(self, db):
        """R-83: o segundo edital entra; nao vira INSERT que bate na unicidade."""
        id_substituto = _gravar_substituto(db)
        id_tecnico = _gravar_tecnico(db)

        assert id_substituto > 0
        assert id_tecnico > 0
        assert id_tecnico != id_substituto
        substituto = db.buscar_registro(IFSP_NOME, pci_id=IFSP_SUBSTITUTO_PCI)
        tecnico = db.buscar_registro(IFSP_NOME, pci_id=IFSP_TECNICO_PCI)
        assert (substituto["id"], substituto["data_fim_inscricao"], substituto["fase"]) == (
            id_substituto, IFSP_SUBSTITUTO_PRAZO, "inscricoes_abertas"
        )
        assert (tecnico["id"], tecnico["data_fim_inscricao"], tecnico["fase"]) == (
            id_tecnico, IFSP_TECNICO_PRAZO, "inscricoes_abertas"
        )

    def test_segunda_linha_nao_sobrescreve_o_prazo_da_primeira(self, db):
        """O caso exato do IFSP em 25/11: varreduras seguidas, prazo estavel.

        Antes, cada varredura gravava o prazo de um edital na linha do outro, e
        a matriz de decisao via "prazo mudou" duas vezes por varredura.
        """
        for _ in range(3):
            antes_substituto = db.buscar_registro(IFSP_NOME, pci_id=IFSP_SUBSTITUTO_PCI)
            _gravar_substituto(db)
            antes_tecnico = db.buscar_registro(IFSP_NOME, pci_id=IFSP_TECNICO_PCI)
            _gravar_tecnico(db)

            if antes_substituto is not None:
                assert antes_substituto["data_fim_inscricao"] == IFSP_SUBSTITUTO_PRAZO
            if antes_tecnico is not None:
                assert antes_tecnico["data_fim_inscricao"] == IFSP_TECNICO_PRAZO

        assert db.buscar_registro(IFSP_NOME, pci_id=IFSP_SUBSTITUTO_PCI)[
            "data_fim_inscricao"] == IFSP_SUBSTITUTO_PRAZO
        assert db.buscar_registro(IFSP_NOME, pci_id=IFSP_TECNICO_PCI)[
            "data_fim_inscricao"] == IFSP_TECNICO_PRAZO

    def test_renomear_para_o_nome_do_outro_edital_nao_funde_as_linhas(self, db):
        """Mesmo orgao, dois concursos: o terceiro caso da colisao de nome.

        O tecnico entra com o nome sem UF e depois volta com o nome exato do
        substituto. Os nomes sao a mesma entidade, mas os pci_id discordam:
        fundir apagaria a linha (e a estrela) do substituto.
        """
        id_substituto = _gravar_substituto(db)
        db.atualizar_estado_usuario(id_substituto, "seguindo")
        id_tecnico = _gravar_tecnico(db, nome=IFSP_NOME_SEM_UF)

        assert _gravar_tecnico(db, nome=IFSP_NOME) == id_tecnico

        substituto = db.buscar_registro(IFSP_NOME, pci_id=IFSP_SUBSTITUTO_PCI)
        assert substituto["id"] == id_substituto
        assert substituto["estado_usuario"] == "seguindo"
        assert substituto["data_fim_inscricao"] == IFSP_SUBSTITUTO_PRAZO
        tecnico = db.buscar_registro(IFSP_NOME, pci_id=IFSP_TECNICO_PCI)
        assert (tecnico["id"], tecnico["nome"]) == (id_tecnico, IFSP_NOME)

    def test_item_sem_pci_id_funde_todas_as_grafias_do_nome_novo(self, db):
        """R-82: linhas legadas do mesmo orgao em varias grafias viram uma so.

        Tres linhas do Gran sem pci_id: "IFSP - SP" (casada pelo link),
        "ifsp" e "IFSP" (a unicidade compara byte a byte e aceita as duas). A
        atualizacao pelo link assume o nome "IFSP": todas sao o mesmo orgao e
        nenhuma e outro edital, entao todas se fundem na linha casada. Fundir so
        uma deixava a outra ocupando o nome e a escrita batia na unicidade.
        """
        link_gran = "https://blog.grancursosonline.com.br/concurso-ifsp/"
        url_gran = "https://blog.grancursosonline.com.br/concursos-ti/"
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (area, nome, status, link, fonte) VALUES ('TI', ?, 'x', ?, 'gran')",
            [("IFSP - SP", link_gran), ("ifsp", None), ("IFSP", None)],
        )
        conn.commit()
        conn.close()

        id_ = db.atualizar_concurso("IFSP", "novo", link_gran, url_indice=url_gran)

        assert id_ == 1
        registro = db.buscar_registro("IFSP")
        assert (registro["id"], registro["nome"], registro["status"]) == (1, "IFSP", "novo")
        assert db.contar_por_fonte("gran") == 1

    def test_fusao_pelo_nome_nao_junta_dois_editais_de_pci_id_distintos(self, db):
        """A linha sem pci_id que assume o nome absorve UM edital, nunca dois.

        "IFSP" (296044) e "ifsp" (296538) sao dois editais. A linha do Gran,
        casada pelo link, assume o nome "IFSP": funde-se com o de nome exato e
        herda o pci_id dele; o outro, agora de pci_id diferente, fica.
        """
        link_gran = "https://blog.grancursosonline.com.br/concurso-ifsp/"
        url_gran = "https://blog.grancursosonline.com.br/concursos-ti/"
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (area, nome, status, link, fonte, pci_id) "
            "VALUES ('TI', ?, 'x', ?, ?, ?)",
            [("IFSP - SP", link_gran, "gran", None),
             ("ifsp", None, "pci_mcp", IFSP_TECNICO_PCI),
             ("IFSP", None, "pci_mcp", IFSP_SUBSTITUTO_PCI)],
        )
        conn.commit()
        conn.close()

        assert db.atualizar_concurso("IFSP", "novo", link_gran, url_indice=url_gran) == 1

        substituto = db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI)
        tecnico = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
        assert (substituto["id"], substituto["nome"], substituto["status"]) == (1, "IFSP", "novo")
        assert (tecnico["id"], tecnico["nome"]) == (2, "ifsp")

    def test_pci_id_rechaveia_pelo_link_com_nome_de_outra_entidade(self, db):
        """R-81 pelo link: o nome legado nao casaria nem por nome nem por entidade."""
        id_legado = db.atualizar_concurso(
            "Concurso técnico-administrativo 2026", "legado", IFSP_TECNICO_LINK,
            url_indice=URL_INDICE_PCI, fonte="pci",
        )

        id_mcp = _gravar_tecnico(db)

        assert id_mcp == id_legado
        registro = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
        assert (registro["id"], registro["pci_id"]) == (id_legado, IFSP_TECNICO_PCI)

    def test_pci_id_rechaveia_por_entidade_sem_link_especifico(self, db):
        """R-81 por entidade: outro nome do mesmo orgao, nenhum link especifico."""
        id_legado = db.atualizar_concurso(
            IFSP_NOME_SEM_UF, "legado", "", fonte="gran",
        )

        id_mcp = _gravar_tecnico(db, link="")

        assert id_mcp == id_legado
        registro = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
        assert (registro["id"], registro["pci_id"]) == (id_legado, IFSP_TECNICO_PCI)

    def test_pci_id_vazio_grava_como_nulo(self, db):
        """Vazio e nulo sao a mesma coisa para a chave canonica (SPEC-003, 3.1)."""
        db.atualizar_concurso("TRF1", "previsto", "", fonte="gran", pci_id="")

        assert db.buscar_registro("TRF1")["pci_id"] is None

    def test_pci_id_vazio_nao_apaga_o_pci_id_gravado(self, db):
        """Chamada com pci_id vazio e chamada sem pci_id: preserva o gravado."""
        id_tecnico = _gravar_tecnico(db)

        id_ = db.atualizar_concurso(
            IFSP_NOME, "sem chave", IFSP_TECNICO_LINK, url_indice=URL_INDICE_PCI, pci_id="",
        )

        assert id_ == id_tecnico
        registro = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
        assert registro is not None, "o pci_id gravado se perdeu"
        assert (registro["id"], registro["status"]) == (id_tecnico, "sem chave")

    def test_linha_legada_com_pci_id_vazio_e_rechaveada(self, db):
        """R-81: linha legada com pci_id vazio e linha sem pci_id."""
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            "INSERT INTO editais (area, nome, status, fonte, pci_id) "
            "VALUES ('TI', ?, 'legado', 'pci', '')",
            (IFSP_NOME,),
        )
        conn.commit()
        conn.close()

        assert _gravar_tecnico(db, link="") == 1
        assert db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)["id"] == 1

    def test_linha_legada_com_pci_id_vazio_herda_o_pci_id_na_fusao(self, db):
        """A linha de pci_id vazio que absorve um edital fica com o pci_id dele."""
        link_gran = "https://blog.grancursosonline.com.br/concurso-ifsp/"
        url_gran = "https://blog.grancursosonline.com.br/concursos-ti/"
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (area, nome, status, link, fonte, pci_id) "
            "VALUES ('TI', ?, 'x', ?, ?, ?)",
            [("IFSP - SP", link_gran, "gran", ""),
             ("IFSP", None, "pci_mcp", IFSP_SUBSTITUTO_PCI)],
        )
        conn.commit()
        conn.close()

        assert db.atualizar_concurso("IFSP", "novo", link_gran, url_indice=url_gran) == 1

        registro = db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI)
        assert registro is not None, "o pci_id gravado se perdeu"
        assert (registro["id"], registro["status"]) == (1, "novo")

    def test_colisao_irresolvivel_vira_erro_no_log_nao_silencio(self, db, caplog):
        """R-86: a escrita que bate na unicidade sai no log como erro nomeado.

        A regra de identidade resolve toda colisao que ela consegue ver. A que
        sobra e a linha que aparece entre a busca e a escrita: outro escritor
        no mesmo arquivo. O gatilho abaixo faz esse papel, gravando o mesmo
        edital imediatamente antes do INSERT.
        """
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            """
            CREATE TRIGGER outro_escritor BEFORE INSERT ON editais
            WHEN NEW.pci_id = '296538'
            BEGIN
                INSERT INTO editais (area, nome, status, pci_id, fonte)
                VALUES (NEW.area, NEW.nome, 'gravado por outro processo', NEW.pci_id, 'pci_mcp');
            END
            """
        )
        conn.commit()
        conn.close()

        with caplog.at_level("ERROR", logger="DatabaseManager"):
            id_ = _gravar_tecnico(db)

        assert id_ == 0
        erros = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert any(
            "colisao de identidade" in m.lower() and IFSP_TECNICO_PCI in m for m in erros
        )


# Linhas do banco anterior a abertura da unicidade, escritas a mao com todos os
# campos preenchidos, inclusive uma estrela do Lucas.
LINHA_IFSP_ANTIGA = {
    "id": 1, "area": "TI", "nome": IFSP_NOME,
    "status": "Professor substituto", "link": IFSP_SUBSTITUTO_LINK,
    "data_fim_inscricao": IFSP_SUBSTITUTO_PRAZO, "status_hash": "a1b2c3d4e5f60718",
    "fase": "inscricoes_abertas", "estado_usuario": "seguindo",
    "fonte": "pci_mcp", "pci_id": IFSP_SUBSTITUTO_PCI,
    "uf": "SP", "regiao": "SUDESTE", "esfera": "federal",
    "cargos_total": 12, "salario_teto": 8340.0,
    "elegibilidade": "elegivel", "motivo_filtro": None,
    "ultima_atualizacao": "2026-11-25 03:20:11",
}
LINHA_TRF1_ANTIGA = {
    "id": 2, "area": "TI", "nome": "TRF1",
    "status": "previsto", "link": "https://blog.grancursosonline.com.br/concurso-trf1/",
    "data_fim_inscricao": None, "status_hash": None,
    "fase": "previsto", "estado_usuario": "ignorado",
    "fonte": "gran", "pci_id": None,
    "uf": None, "regiao": None, "esfera": None,
    "cargos_total": None, "salario_teto": None,
    "elegibilidade": None, "motivo_filtro": "abaixo_do_corte",
    "ultima_atualizacao": "2026-08-08 03:00:00",
}


def _criar_banco_com_unique_area_nome(db_path):
    """Banco no formato v6, com o UNIQUE(area, nome) de tabela.

    A linha 3 e criada e apagada (como faz uma fusao), entao o proximo id
    livre e 4: id ja usado em botao do Telegram nao pode voltar.
    """
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
            uf TEXT,
            regiao TEXT,
            esfera TEXT,
            cargos_total INTEGER,
            salario_teto REAL,
            elegibilidade TEXT,
            motivo_filtro TEXT,
            ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(area, nome)
        )
        """
    )
    for linha in (LINHA_IFSP_ANTIGA, LINHA_TRF1_ANTIGA):
        colunas = ", ".join(linha)
        marcas = ", ".join("?" for _ in linha)
        conn.execute(f"INSERT INTO editais ({colunas}) VALUES ({marcas})", tuple(linha.values()))
    conn.execute(
        "INSERT INTO editais (id, area, nome, status, fonte) "
        "VALUES (3, 'TI', 'Prefeitura de Blumenau - SC', 'x', 'pci_mcp')"
    )
    conn.execute("DELETE FROM editais WHERE id = 3")
    conn.commit()
    conn.close()


class TestMigracaoDaUnicidade:
    """R-84, R-85 e idempotencia da troca de UNIQUE(area, nome) pelo indice."""

    def test_migracao_preserva_id_estado_usuario_e_contagem(self, db_path):
        _criar_banco_com_unique_area_nome(db_path)

        db = DatabaseManager(area="TI", db_path=db_path)
        try:
            assert db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI) == LINHA_IFSP_ANTIGA
            assert db.buscar_registro("TRF1") == LINHA_TRF1_ANTIGA
            assert db.contar_por_fonte("pci_mcp") == 1
            assert db.contar_por_fonte("gran") == 1
        finally:
            db.fechar_conexao()

    def test_migracao_abre_a_unicidade_para_o_segundo_edital(self, db_path):
        """Depois da migracao, o tecnico do IFSP entra como linha propria.

        E entra com id 4: o 3 foi de uma linha apagada e nao volta a circular.
        """
        _criar_banco_com_unique_area_nome(db_path)

        db = DatabaseManager(area="TI", db_path=db_path)
        try:
            id_tecnico = _gravar_tecnico(db)

            assert id_tecnico == 4
            assert db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI) == LINHA_IFSP_ANTIGA
        finally:
            db.fechar_conexao()

    def test_migracao_rodada_duas_vezes_nao_muda_nada(self, db_path):
        _criar_banco_com_unique_area_nome(db_path)
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()
        with open(db_path, "rb") as f:
            depois_da_primeira = f.read()

        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()
        with open(db_path, "rb") as f:
            depois_da_segunda = f.read()

        assert depois_da_segunda == depois_da_primeira

    def test_nome_repetido_sem_pci_id_volta_para_a_mesma_linha(self, db):
        """Item sem pci_id repetido nao vira linha nova (o COALESCE do indice
        guarda o banco; quem guarda o fluxo e a busca por nome)."""
        id_ = db.atualizar_concurso("TRF1", "v1", "", fonte="gran")

        assert db.atualizar_concurso("trf1", "v2", "", fonte="gran") == id_
        assert db.contar_por_fonte("gran") == 1
        assert db.buscar_registro("TRF1")["status"] == "v2"
