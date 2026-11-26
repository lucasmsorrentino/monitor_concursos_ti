"""Testes para src/database/manager.py — persistencia SQLite com PK (area, nome)."""
import logging
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

    def test_area_nome_is_unique(self, db_path, caplog):
        """(area, nome) e unico entre linhas SEM pci_id; o pci_id separa editais.

        Ate a SPEC-003 a unicidade era o UNIQUE(area, nome) de tabela, que
        impedia dois editais do mesmo orgao. Agora e o indice unico
        (area, nome, COALESCE(pci_id, '')): o nome repetido sem pci_id continua
        barrado, e dois pci_id distintos com o mesmo nome coexistem.

        A rejeicao e observada pela escrita publica. A busca de identidade ja
        evita a colisao que ela enxerga, entao o cenario a planta com um
        gatilho: o "outro escritor" grava a linha repetida entre a busca e o
        INSERT. O que se afirma e o que o indice faz com ela: NULL com NULL,
        NULL com '' (os dois sao ausencia de chave) e a mesma chave colidem;
        chaves distintas coexistem.
        """
        DatabaseManager(area="TI", db_path=db_path).fechar_conexao()
        conn = sqlite3.connect(db_path)
        # Cada gatilho dispara so para o seu nome e planta a linha repetida com
        # a chave do caso. Ele nao dispara para a propria linha plantada (o
        # status dela e outro), e o SQLite nao tem gatilho recursivo por padrao.
        for nome, chave_plantada in (
            ("TRF1", "NULL"), ("TRF2", "''"), ("IFSP", "NEW.pci_id"),
        ):
            conn.execute(
                f"""
                CREATE TRIGGER outro_escritor_{nome} BEFORE INSERT ON editais
                WHEN NEW.nome = '{nome}' AND NEW.status = 'repetido'
                BEGIN
                    INSERT INTO editais (area, nome, status, pci_id)
                    VALUES (NEW.area, NEW.nome, 'outro escritor', {chave_plantada});
                END
                """
            )
        conn.commit()
        conn.close()

        db = DatabaseManager(area="TI", db_path=db_path)
        try:
            id_a = db.atualizar_concurso("IFSP", "a", pci_id="296044")
            id_b = db.atualizar_concurso("IFSP", "b", pci_id="296538")
            assert id_a > 0 and id_b > 0 and id_a != id_b

            with caplog.at_level("ERROR", logger="DatabaseManager"):
                rejeitados = {
                    "NULL com NULL": db.atualizar_concurso("TRF1", "repetido"),
                    "NULL com ''": db.atualizar_concurso("TRF2", "repetido", pci_id=""),
                    "mesma chave": db.atualizar_concurso("IFSP", "repetido", pci_id="297000"),
                }

            assert rejeitados == {"NULL com NULL": 0, "NULL com ''": 0, "mesma chave": 0}
            erros = [r.getMessage().lower() for r in caplog.records if r.levelname == "ERROR"]
            assert len([m for m in erros if "colisao de identidade" in m]) == 3
            assert db.buscar_registro("TRF1") is None
            assert db.buscar_registro("TRF2") is None
            assert db.buscar_registro("", pci_id="297000") is None
            a = db.buscar_registro("", pci_id="296044")
            b = db.buscar_registro("", pci_id="296538")
            assert (a["id"], a["status"]) == (id_a, "a")
            assert (b["id"], b["status"]) == (id_b, "b")
        finally:
            db.fechar_conexao()


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
        fundir apagaria a linha (e a estrela) do substituto. E o nome esta
        ocupado, entao o tecnico fica com o nome que ja tinha (R-99).
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
        assert (tecnico["id"], tecnico["nome"]) == (id_tecnico, IFSP_NOME_SEM_UF)

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

    @pytest.mark.parametrize("fallback", ["link", "nome", "entidade"])
    def test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks(self, db, fallback):
        """Nulo e so NULL ou '': qualquer outro valor gravado e chave de outro edital.

        A linha legada tem pci_id " " (gravado antes de a escrita normalizar).
        Nao e vazio, entao e chave, e um item com outro pci_id nao casa com ela
        por nenhum fallback. Um criterio de nulidade na busca e outro na fusao
        e o que permitia descartar uma chave canonica valida.

        Cada caso alcanca o SEU fallback e nao escorrega para o seguinte. No de
        nome, o nome e ASCII de proposito: o COLLATE NOCASE do SQLite so dobra
        ASCII, e um nome acentuado em maiusculas nao casaria por nome, so por
        entidade.
        """
        nome_gravado, busca = {
            "link": (IFSP_NOME, dict(
                nome="Outro nome", link=IFSP_SUBSTITUTO_LINK, url_indice=URL_INDICE_PCI)),
            "nome": ("IFSP", dict(nome="ifsp")),
            "entidade": (IFSP_NOME, dict(nome=IFSP_NOME_SEM_UF)),
        }[fallback]
        conn = sqlite3.connect(db.db_path)
        conn.execute(
            "INSERT INTO editais (area, nome, status, link, fonte, pci_id) "
            "VALUES ('TI', ?, 'legado', ?, 'pci', ' ')",
            (nome_gravado, IFSP_SUBSTITUTO_LINK),
        )
        conn.commit()
        conn.close()

        assert db.buscar_registro(**busca, pci_id=IFSP_TECNICO_PCI) is None
        legada = db.buscar_registro("", pci_id=" ")
        assert (legada["id"], legada["nome"], legada["status"]) == (1, nome_gravado, "legado")

    def test_chave_com_espaco_no_fim_e_outro_edital_na_unicidade(self, db):
        """So NULL e '' contam como ausencia de chave, tambem para o indice.

        "296538 " (espaco no fim) nao e nula nem e "296538": e outra chave, e
        os dois editais de mesmo nome coexistem. Um indice que tirasse o espaco
        os faria colidir, e a segunda escrita se perderia.
        """
        id_limpa = db.atualizar_concurso(IFSP_NOME, "chave limpa", pci_id="296538")
        id_espaco = db.atualizar_concurso(IFSP_NOME, "chave com espaco", pci_id="296538 ")

        assert id_limpa > 0 and id_espaco > 0 and id_limpa != id_espaco
        limpa = db.buscar_registro("", pci_id="296538")
        espaco = db.buscar_registro("", pci_id="296538 ")
        assert (limpa["id"], limpa["status"]) == (id_limpa, "chave limpa")
        assert (espaco["id"], espaco["status"]) == (id_espaco, "chave com espaco")

    def test_atualizacao_sem_pci_id_preserva_as_duas_linhas_e_as_duas_chaves(self, db):
        """A linha legada de pci_id " " nao absorve a linha de outro pci_id.

        "IFSP" (pci_id " ", casada pelo link) assume o nome "IFSP - SP", que e
        o da linha do 296044. Sao o mesmo orgao, mas as chaves discordam: sao
        dois editais, e os dois sobrevivem com id e pci_id intactos.
        """
        link_gran = "https://blog.grancursosonline.com.br/concurso-ifsp/"
        url_gran = "https://blog.grancursosonline.com.br/concursos-ti/"
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (area, nome, status, link, fonte, pci_id) "
            "VALUES ('TI', ?, ?, ?, ?, ?)",
            [("IFSP", "legado", link_gran, "gran", " "),
             ("IFSP - SP", "substituto", None, "pci_mcp", IFSP_SUBSTITUTO_PCI)],
        )
        conn.commit()
        conn.close()

        assert db.atualizar_concurso("IFSP - SP", "novo", link_gran, url_indice=url_gran) == 1

        substituto = db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI)
        assert substituto is not None, "o pci_id gravado se perdeu"
        assert (substituto["id"], substituto["status"]) == (2, "substituto")
        legada = db.buscar_registro("", link=link_gran, url_indice=url_gran)
        assert (legada["id"], legada["pci_id"], legada["status"]) == (1, " ", "novo")

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

    def test_colisao_na_escrita_deixa_as_duas_linhas_como_estavam(self, db, caplog):
        """R-86: a escrita perdida sai nomeada e nao deixa o banco pela metade.

        Duas grafias do Gran do mesmo orgao. A atualizacao pelo link disputa o
        nome "IFSP" e a escrita final falha (o gatilho faz o papel da colisao
        que o codigo nao previu). O erro sai nomeado e o banco continua com as
        duas linhas como estavam.
        """
        link_gran = "https://blog.grancursosonline.com.br/concurso-ifsp/"
        url_gran = "https://blog.grancursosonline.com.br/concursos-ti/"
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (area, nome, status, link, fonte) VALUES ('TI', ?, ?, ?, 'gran')",
            [("IFSP - SP", "casada", link_gran), ("IFSP", "grafia", None)],
        )
        conn.execute(
            """
            CREATE TRIGGER escrita_final_falha BEFORE UPDATE ON editais
            WHEN NEW.status = 'novo'
            BEGIN
                SELECT RAISE(ABORT, 'UNIQUE constraint failed: editais.nome (simulado)');
            END
            """
        )
        conn.commit()
        conn.close()

        with caplog.at_level("ERROR", logger="DatabaseManager"):
            id_ = db.atualizar_concurso("IFSP", "novo", link_gran, url_indice=url_gran)

        assert id_ == 0
        erros = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert any("colisao de identidade" in m.lower() for m in erros)
        assert db.contar_por_fonte("gran") == 2
        casada = db.buscar_registro("", link=link_gran, url_indice=url_gran)
        assert (casada["id"], casada["nome"], casada["status"]) == (1, "IFSP - SP", "casada")
        grafia = db.buscar_registro("IFSP")
        assert (grafia["id"], grafia["nome"], grafia["status"]) == (2, "IFSP", "grafia")


# ---------------------------------------------------------------------------
# R-99: o nome novo so vence quando ninguem o ocupa, e nada se funde
# ---------------------------------------------------------------------------
#
# Oraculo: SPEC-003, R-99. Enquanto a regra de nome nao for escrita como
# tabela (R-100), havendo QUALQUER outra linha da area com o nome novo (sem
# diferenca de caixa), a linha casada mantem o nome atual e o conflito vai
# para o log. Nenhuma linha e fundida nem apagada.

URL_INDICE_GRAN = "https://blog.grancursosonline.com.br/concursos-ti/"
LINK_GRAN_A = "https://blog.grancursosonline.com.br/concurso-ifsp-a/"
LINK_GRAN_C = "https://blog.grancursosonline.com.br/concurso-ifsp-c/"
LINK_GRAN_D = "https://blog.grancursosonline.com.br/concurso-ifsp-d/"
TJPR_NOME = "TJPR - Tribunal de Justiça do Paraná"
TJPR_LINK = "https://www.pciconcursos.com.br/noticias/tjpr-abre-concurso-publico"


def _plantar(db_path, linhas):
    """Monta o estado do banco que a API nao produz sozinha.

    Duas grafias do mesmo orgao sem chave, por exemplo, sao linhas legadas de
    antes do casamento por entidade: o `atualizar_concurso` de hoje casaria a
    segunda com a primeira. Cada linha e (id, nome, status, link, fonte, pci_id).
    """
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO editais (id, area, nome, status, link, fonte, pci_id) "
        "VALUES (?, 'TI', ?, ?, ?, ?, ?)",
        linhas,
    )
    conn.commit()
    conn.close()


def _id_pela_chave(db, link, pci_id):
    """O id da linha achada pela chave mais forte que ela tem, ou None."""
    if pci_id:
        registro = db.buscar_registro("", pci_id=pci_id)
    else:
        registro = db.buscar_registro("", link=link, url_indice=URL_INDICE_GRAN)
    return registro["id"] if registro else None


def _avisos_de_colisao(caplog, *nomes):
    return [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and all(n in r.getMessage() for n in nomes)
    ]


class TestNomeConservador:
    """R-99: o nome so muda quando nenhuma outra linha da area o ocupa."""

    def test_nome_novo_vence_quando_ninguem_ocupa(self, db):
        """O unico caminho em que o nome muda: o nome novo esta livre na area."""
        id_ifsp = db.atualizar_concurso(
            "IFSP - SP", "antes", LINK_GRAN_A, url_indice=URL_INDICE_GRAN, fonte="gran"
        )
        id_tjpr = db.atualizar_concurso(
            TJPR_NOME, "tribunal", TJPR_LINK, url_indice=URL_INDICE_GRAN, fonte="gran"
        )

        id_ = db.atualizar_concurso(
            IFSP_NOME, "depois", LINK_GRAN_A, url_indice=URL_INDICE_GRAN
        )

        assert id_ == id_ifsp
        ifsp = db.buscar_registro("", link=LINK_GRAN_A, url_indice=URL_INDICE_GRAN)
        assert (ifsp["id"], ifsp["nome"], ifsp["status"]) == (id_ifsp, IFSP_NOME, "depois")
        tjpr = db.buscar_registro(TJPR_NOME)
        assert (tjpr["id"], tjpr["status"]) == (id_tjpr, "tribunal")

    @pytest.mark.parametrize(
        "nome_do_conflito",
        ["IFSP", TJPR_NOME],
        ids=["mesmo_orgao", "outro_orgao"],
    )
    def test_nome_em_conflito_mantem_o_nome_atual_e_loga(self, db, caplog, nome_do_conflito):
        """Mesmo orgao ou outro, o resultado e o mesmo: o nome atual fica.

        A linha 1 e casada pelo link e chega com o nome da linha 2. Sem a
        tabela de decisao do nome, saber se a linha 2 e o mesmo orgao nao
        autoriza nada: ela continua no banco, com o nome e o status dela.
        """
        _plantar(db.db_path, [
            (1, "IFSP - SP", "casada", LINK_GRAN_A, "gran", None),
            (2, nome_do_conflito, "conflito", LINK_GRAN_C, "gran", None),
        ])

        with caplog.at_level("WARNING", logger="DatabaseManager"):
            id_ = db.atualizar_concurso(
                nome_do_conflito, "novo", LINK_GRAN_A, url_indice=URL_INDICE_GRAN
            )

        assert id_ == 1
        casada = db.buscar_registro("", link=LINK_GRAN_A, url_indice=URL_INDICE_GRAN)
        assert (casada["id"], casada["nome"], casada["status"]) == (1, "IFSP - SP", "novo")
        conflito = db.buscar_registro("", link=LINK_GRAN_C, url_indice=URL_INDICE_GRAN)
        assert (conflito["id"], conflito["nome"], conflito["status"]) == (
            2, nome_do_conflito, "conflito"
        )
        assert _avisos_de_colisao(caplog, nome_do_conflito, "IFSP - SP")

    def test_nome_em_conflito_so_de_caixa_tambem_mantem_o_nome_atual(self, db):
        """COLLATE NOCASE: "ifsp" ocupa o nome "IFSP"."""
        _plantar(db.db_path, [
            (1, "IFSP - SP", "casada", LINK_GRAN_A, "gran", None),
            (2, "ifsp", "conflito", LINK_GRAN_C, "gran", None),
        ])

        assert db.atualizar_concurso("IFSP", "novo", LINK_GRAN_A, url_indice=URL_INDICE_GRAN) == 1

        casada = db.buscar_registro("", link=LINK_GRAN_A, url_indice=URL_INDICE_GRAN)
        assert (casada["nome"], casada["status"]) == ("IFSP - SP", "novo")
        assert db.buscar_registro("IFSP")["id"] == 2

    # Cada cenario: linhas plantadas e a atualizacao (nome, link, pci_id).
    CENARIOS_SEM_FUSAO = {
        "duas_grafias_sem_chave": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "gran", None),
             (2, "IFSP", "b", LINK_GRAN_C, "gran", None)],
            ("IFSP", LINK_GRAN_A, None),
        ),
        "tres_grafias_sem_chave": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "gran", None),
             (2, "ifsp", "b", LINK_GRAN_C, "gran", None),
             (3, "IFSP", "c", LINK_GRAN_D, "gran", None)],
            ("IFSP", LINK_GRAN_A, None),
        ),
        "casada_com_chave_e_grafia_sem_chave": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "pci_mcp", IFSP_TECNICO_PCI),
             (2, "IFSP", "b", LINK_GRAN_C, "gran", None)],
            ("IFSP", LINK_GRAN_A, None),
        ),
        "casada_sem_chave_e_grafia_com_chave": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "gran", None),
             (2, "IFSP", "b", LINK_GRAN_C, "pci_mcp", IFSP_TECNICO_PCI)],
            ("IFSP", LINK_GRAN_A, None),
        ),
        "rechave_com_nome_de_outro_edital": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "gran", None),
             (2, "IFSP", "b", LINK_GRAN_C, "pci_mcp", IFSP_SUBSTITUTO_PCI)],
            ("IFSP", LINK_GRAN_A, IFSP_TECNICO_PCI),
        ),
        "nome_de_outro_orgao": (
            [(1, "IFSP - SP", "a", LINK_GRAN_A, "pci_mcp", IFSP_TECNICO_PCI),
             (2, TJPR_NOME, "b", TJPR_LINK, "pci_mcp", IFSP_SUBSTITUTO_PCI)],
            (TJPR_NOME, LINK_GRAN_A, None),
        ),
    }

    @pytest.mark.parametrize("cenario", list(CENARIOS_SEM_FUSAO))
    def test_nenhum_caminho_funde_ou_apaga_linha(self, db, cenario):
        linhas, (nome, link, pci_id) = self.CENARIOS_SEM_FUSAO[cenario]
        _plantar(db.db_path, linhas)
        fontes = {linha[4] for linha in linhas}
        contagem_antes = {f: db.contar_por_fonte(f) for f in fontes}

        id_ = db.atualizar_concurso(
            nome, "novo", link, url_indice=URL_INDICE_GRAN, pci_id=pci_id
        )

        assert id_ == 1
        assert {f: db.contar_por_fonte(f) for f in fontes} == contagem_antes
        # A linha 1 pode ter ganho a chave do item (rechave): procura por ela.
        chave_da_linha_1 = pci_id or linhas[0][5]
        assert _id_pela_chave(db, linhas[0][3], chave_da_linha_1) == 1
        for id_esperado, _, status, link_da_linha, _, pci_da_linha in linhas[1:]:
            registro = db.buscar_registro(
                "", link=link_da_linha, url_indice=URL_INDICE_GRAN, pci_id=pci_da_linha or ""
            )
            assert (registro["id"], registro["status"]) == (id_esperado, status)

    def test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5(self, db):
        """A regressao do quarto defeito, pelo cenario exato do parecer.

        O IFSP (296538, link /a) e o TJPR (296044, link /b) tem chaves
        distintas. Uma atualizacao sem chave chega com o nome do TJPR e o link
        do IFSP: casa com o IFSP pelo link, mas o nome do TJPR esta ocupado.
        O IFSP continua IFSP, e a busca sem chave por TJPR acha o TJPR.
        """
        id_ifsp = db.atualizar_concurso(
            "IFSP - SP", "A antes", IFSP_TECNICO_LINK, url_indice=URL_INDICE_PCI,
            fonte="pci_mcp", pci_id=IFSP_TECNICO_PCI,
        )
        id_tjpr = db.atualizar_concurso(
            "TJPR", "B antes", TJPR_LINK, url_indice=URL_INDICE_PCI,
            fonte="pci_mcp", pci_id=IFSP_SUBSTITUTO_PCI,
        )
        assert (id_ifsp, id_tjpr) == (1, 2)

        id_ = db.atualizar_concurso(
            "TJPR", "A depois", IFSP_TECNICO_LINK, url_indice=URL_INDICE_PCI
        )

        assert id_ == 1
        ifsp = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
        assert (ifsp["id"], ifsp["nome"], ifsp["status"]) == (1, "IFSP - SP", "A depois")
        tjpr = db.buscar_registro("TJPR")
        assert (tjpr["id"], tjpr["nome"], tjpr["status"]) == (2, "TJPR", "B antes")


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


# Empate nas buscas: duas linhas da mesma area que a mesma busca alcanca.
#
# O banco de producao NAO tem empate hoje (medido em 26/11/2026, 1.725 linhas:
# zero grupos de nome por area, os dois grupos de link sao paginas-indice que a
# busca por link recusa, e nenhum pci_id repetido dentro de uma area). Estes
# testes nao descrevem producao: afirmam a regra de desempate, que e
# deterministica por escolha. A linha mais antiga (menor id) vence, em vez da
# primeira que o indice escolhido pelo planejador devolver.
#
# Os ids estao de proposito na ordem OPOSTA a das duas ordens que o planejador
# ja produziu: o id 1 tem o nome que vem depois em BINARY ("ifsp" > "IFSP", a
# ordem do UNIQUE(area, nome) do v6) e o pci_id que vem depois no
# idx_editais_pci ("296538" > "296044"). So o desempate explicito acerta o id 1.

LINK_IFSP_GRAN = "https://blog.grancursosonline.com.br/concurso-ifsp/"
URL_INDICE_GRAN = "https://blog.grancursosonline.com.br/concursos-ti/"


def _criar_banco_v6_com_duas_grafias(db_path):
    """Banco v6 (UNIQUE(area, nome) de tabela) com dois editais do IFSP que
    empatam no link, no nome sem caixa e na entidade."""
    _criar_banco_com_unique_area_nome(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM editais")
    conn.executemany(
        "INSERT INTO editais (id, area, nome, status, link, fonte, pci_id) "
        "VALUES (?, 'TI', ?, ?, ?, 'pci_mcp', ?)",
        [(1, "ifsp", "tecnico original", LINK_IFSP_GRAN, IFSP_TECNICO_PCI),
         (2, "IFSP", "substituto original", LINK_IFSP_GRAN, IFSP_SUBSTITUTO_PCI)],
    )
    conn.commit()
    conn.close()


class TestDesempateDasBuscas:
    """Busca que alcanca mais de uma linha escolhe a de menor id."""

    BUSCA_SEM_CHAVE = {
        "link": dict(nome="Concurso do instituto", link=LINK_IFSP_GRAN, url_indice=URL_INDICE_GRAN),
        "nome": dict(nome="Ifsp"),
        "entidade": dict(nome="IFSP - SP"),
    }

    @pytest.mark.parametrize("fallback", ["link", "nome", "entidade"])
    def test_busca_sem_chave_empatada_escolhe_a_linha_mais_antiga(self, db_path, fallback):
        _criar_banco_v6_com_duas_grafias(db_path)
        db = DatabaseManager(area="TI", db_path=db_path)
        try:
            registro = db.buscar_registro(**self.BUSCA_SEM_CHAVE[fallback])

            assert registro is not None
            assert registro["id"] == 1
        finally:
            db.fechar_conexao()

    @pytest.mark.parametrize("fallback", ["link", "nome", "entidade"])
    def test_atualizacao_sem_chave_empatada_grava_so_na_linha_mais_antiga(self, db_path, fallback):
        _criar_banco_v6_com_duas_grafias(db_path)
        db = DatabaseManager(area="TI", db_path=db_path)
        try:
            id_ = db.atualizar_concurso(status="novo", **self.BUSCA_SEM_CHAVE[fallback])

            assert id_ == 1
            tecnico = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)
            substituto = db.buscar_registro("", pci_id=IFSP_SUBSTITUTO_PCI)
            assert (tecnico["id"], tecnico["status"]) == (1, "novo")
            assert (substituto["id"], substituto["status"]) == (2, "substituto original")
        finally:
            db.fechar_conexao()

    def test_busca_pelo_pci_id_empatada_escolhe_a_linha_mais_antiga(self, db):
        """Desde o v7, duas linhas de nomes diferentes podem ter o mesmo pci_id."""
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (id, area, nome, status, fonte, pci_id) "
            "VALUES (?, 'TI', ?, ?, 'pci_mcp', ?)",
            [(2, "IFSP", "mais nova", IFSP_TECNICO_PCI),
             (1, "Instituto Federal de Sao Paulo", "mais antiga", IFSP_TECNICO_PCI)],
        )
        conn.commit()
        conn.close()

        registro = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)

        assert (registro["id"], registro["status"]) == (1, "mais antiga")

    def test_busca_pelo_pci_id_empatada_nao_depende_do_indice(self, db):
        """O desempate vale mesmo com um indice que guarda a ordem contraria.

        O indice abaixo cobre a busca pelo pci_id e guarda as linhas em id
        decrescente: sem o desempate explicito, a primeira linha que ele
        devolve e a mais nova.
        """
        conn = sqlite3.connect(db.db_path)
        conn.executemany(
            "INSERT INTO editais (id, area, nome, status, fonte, pci_id) "
            "VALUES (?, 'TI', ?, ?, 'pci_mcp', ?)",
            [(1, "Instituto Federal de Sao Paulo", "mais antiga", IFSP_TECNICO_PCI),
             (2, "IFSP", "mais nova", IFSP_TECNICO_PCI)],
        )
        conn.execute("CREATE INDEX idx_ordem_contraria ON editais (area, pci_id, id DESC)")
        conn.commit()
        conn.close()

        registro = db.buscar_registro("", pci_id=IFSP_TECNICO_PCI)

        assert (registro["id"], registro["status"]) == (1, "mais antiga")
