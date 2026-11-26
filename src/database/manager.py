"""Persistencia SQLite para o monitor de concursos.

Schema v7 (atual):
    editais(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area TEXT NOT NULL,
        nome TEXT NOT NULL,
        status TEXT NOT NULL,
        link TEXT,
        data_fim_inscricao TEXT,       -- ISO YYYY-MM-DD ou NULL
        status_hash TEXT,              -- fingerprint do status (legado; ver fase)
        fase TEXT,                     -- fase do concurso (vocabulario controlado)
        estado_usuario TEXT NOT NULL DEFAULT 'ativo',  -- ativo|ignorado|seguindo
        fonte TEXT,                    -- 'gran' | 'pci'  (v5)
        pci_id TEXT,                   -- id da noticia no PCI, chave canonica (v5)
        uf TEXT,                       -- sigla da UF do orgao (v6)
        regiao TEXT,                   -- Sul | NACIONAL | ... (v6)
        esfera TEXT,                   -- federal|estadual|distrital|municipal|conselho_profissional (v6)
        cargos_total INTEGER,          -- quantos cargos o edital inteiro tem (v6)
        salario_teto REAL,             -- teto do concurso, o maior salario do edital (v6)
        elegibilidade TEXT,            -- decisao do bot: 'filtrado' | 'elegivel' | NULL = pre-v6 (v6)
        motivo_filtro TEXT,            -- motivo do corte, conjunto fechado (v6)
        ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    UNIQUE INDEX idx_editais_identidade ON editais(area, nome, COALESCE(pci_id, ''))
    INDEX idx_editais_pci ON editais(area, pci_id)

Historico de migracoes:
    v1: PK em `nome` apenas (modo single-area).
    v2: PK composta `(area, nome)` — linhas v1 taggueadas como `TI`.
    v3: adiciona `id AUTOINCREMENT` (necessario para callback_data do Telegram),
        `data_fim_inscricao`, `status_hash`, `estado_usuario`.
        `(area, nome)` mantem uniqueness via UNIQUE constraint.
    v4: adiciona `fase` (vocabulario controlado). A deteccao de mudanca passa a
        comparar fase + data_fim_inscricao em vez do hash do texto livre, que
        variava a cada reescrita da LLM e gerava falsos positivos. Linhas
        legadas (fase NULL) sao backfilled silenciosamente na 1a varredura.
    v5: adiciona `fonte` e `pci_id`, quando o PCI Concursos entrou como segunda
        fonte ao lado do blog do Gran. Linhas anteriores sao backfilled com
        fonte='gran', que e de fato a unica origem que existia ate entao.
    v6: adiciona `uf`, `regiao`, `esfera`, `cargos_total`, `salario_teto`,
        `elegibilidade` e `motivo_filtro`. Aditiva e SEM backfill: linha
        anterior ao v6 fica com `elegibilidade` NULL e conta como elegivel —
        ja foi notificada, nao se renotifica, nao se reavalia e nao se apaga.
    v7: a unicidade sai do UNIQUE(area, nome) de tabela para o indice unico
        (area, nome, COALESCE(pci_id, '')), para que dois editais do mesmo
        orgao na mesma area coexistam. Unica migracao que recria a tabela
        (decisao do dono, ADR-0005): uma transacao, todas as colunas copiadas
        com o `id`, `sqlite_sequence` preservado, nenhuma linha apagada,
        fundida ou dividida. O COALESCE mantem barrado o nome repetido entre
        linhas sem `pci_id` (Gran e portas de HTML).

Ordem de identidade (do mais forte pro mais fraco, ADR-0005):
    1. `pci_id` — id da noticia no PCI, estavel entre rodadas.
    2. link especifico (diferente da URL-indice do scraper).
    3. `(area, nome)` COLLATE NOCASE.
    4. `mesma_entidade` sobre os tokens do nome — e o unico passo que cruza
       fontes, porque Gran e PCI escrevem o mesmo orgao de formas diferentes
       ("Prefeitura de Ponta Grossa - PR" x "Concurso Prefeitura Ponta Grossa").

A chave canonica que discorda vence o nome: item com `pci_id` so casa nos
passos 2 a 4 com linha SEM `pci_id` (e a rechaveia); linha com outro `pci_id`
e outro edital, ainda que do mesmo orgao e com o mesmo nome. Item sem
`pci_id` segue a ordem acima sem restricao. `pci_id` vazio conta como nulo em
toda parte (busca, escrita, indice) e e gravado como NULL.

Na troca de nome, o nome novo so vence quando nenhuma outra linha da area o
ocupa (sem diferenca de caixa); havendo conflito, a linha mantem o nome atual
e o conflito e logado como `COLISAO DE NOME`. Nenhum caminho funde ou apaga
linha (SPEC-003, R-99): a regra de fusao espera a tabela de decisao do R-100
na ADR-0005. Escrita que, mesmo assim, bate na unicidade (uma linha gravada
por outro escritor entre a busca e a escrita) e logada como
`COLISAO DE IDENTIDADE`, nunca engolida.

Preservar o `id` importa: ele vai no `callback_data` dos botoes do Telegram,
entao trocar de id invalida os botoes de mensagens ja enviadas.
"""
import logging
import os
import sqlite3

from src.utils.text import mesma_entidade

_ESTADOS_VALIDOS = ("ativo", "ignorado", "seguindo")

# Unicidade da tabela editais desde o v7: (area, nome, COALESCE(pci_id, '')).
_INDICE_IDENTIDADE = "idx_editais_identidade"

# O criterio unico de nulidade do `pci_id`: nulo e so NULL ou ''. Qualquer
# outro valor, mesmo so de espacos, e chave. Ele tem uma forma em Python
# (`_pci_id_ou_none`) e uma em SQL (`_PCI_ID_SQL`), e o indice de unicidade
# (`COALESCE(pci_id, '')`) e a imagem dele. As tres tem de concordar em todo
# valor: quando uma camada le um valor como ausente e a outra como presente, o
# que uma autoriza a outra barra, e uma chave canonica valida se perde (foi o
# que aconteceu com a fusao, antes de ela sair). Nao acrescente `strip()` so
# num lado.
_PCI_ID_SQL = "NULLIF(pci_id, '')"


# Desempate de toda busca de identidade: quando mais de uma linha da area casa,
# vence a de menor id. A linha mais antiga e a de historia mais longa, e por
# isso a que provavelmente carrega a estrela do Lucas. E, sobretudo, o
# resultado fica explicito: sem ORDER BY, a "primeira linha" e a primeira do
# indice que o planejador escolheu, e trocar de indice (como a migracao do v7
# fez) muda em silencio o edital que recebe a escrita. O banco de producao nao
# tem empate hoje (medido em 26/11/2026); a regra e garantia, nao
# compatibilidade. Nao tire.
_DESEMPATE = " ORDER BY id"


def _pci_id_ou_none(valor: str | None) -> str | None:
    """`pci_id` nulo (None ou '') vira None; qualquer outro valor e chave.

    Linha legada com `pci_id` vazio e linha SEM chave canonica, rechaveavel.
    """
    if valor is None or str(valor) == "":
        return None
    return valor


REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH_PADRAO = os.path.join(REPO_DIR, "data", "concursos.db")


class DatabaseManager:
    """Gerencia a tabela `editais` para uma area especifica."""

    def __init__(self, area: str = "TI", db_path: str | None = None):
        """Abre (ou cria) o banco SQLite e garante o schema atualizado.

        Args:
            area: Slug da area monitorada (ex: `TI`, `EDUCACAO`).
            db_path: Caminho do arquivo SQLite. Padrao ancorado na raiz do repo
                via `__file__`. Antes era o relativo "data/concursos.db", que so
                funcionava porque o run_daily.sh faz `cd` antes — rodar o
                main.py de outra pasta criava um banco vazio e renotificava tudo.
        """
        db_path = db_path or DB_PATH_PADRAO
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.area = area
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        """Cria a tabela atual ou migra esquemas antigos, de forma idempotente.

        As migracoes de coluna sao aditivas (`ALTER TABLE ... ADD COLUMN`
        guardado por `PRAGMA table_info`). A unica excecao e o v7, em
        `_abrir_unicidade`, que recria a tabela uma vez para trocar a
        unicidade: excecao aberta pelo dono em `kanban/REGRAS.md`, com escopo
        de um caso so, e registrada na ADR-0005.
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='editais'"
            )
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                self._create_v3_table(cursor)
                self.conn.commit()
                return

            cursor.execute("PRAGMA table_info(editais)")
            columns_info = cursor.fetchall()
            column_names = {col[1] for col in columns_info}
            has_id = "id" in column_names
            has_area = "area" in column_names

            if not has_id:
                # v1 ou v2 → migra para v3 (copia dados, tag 'TI' se v1).
                self._migrate_to_v3(cursor, has_area=has_area)

            # Idempotente: garante colunas novas mesmo se `id` ja existia.
            cursor.execute("PRAGMA table_info(editais)")
            column_names = {col[1] for col in cursor.fetchall()}

            if "data_fim_inscricao" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN data_fim_inscricao TEXT")
            if "status_hash" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN status_hash TEXT")
            if "estado_usuario" not in column_names:
                cursor.execute(
                    "ALTER TABLE editais ADD COLUMN estado_usuario TEXT NOT NULL DEFAULT 'ativo'"
                )
            if "fase" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN fase TEXT")
            if "fonte" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN fonte TEXT")
                # Tudo que existe hoje veio do Gran: era a unica fonte ate v5.
                cursor.execute("UPDATE editais SET fonte = 'gran' WHERE fonte IS NULL")
            if "pci_id" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN pci_id TEXT")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_editais_pci ON editais(area, pci_id)"
                )
            # v6: contexto do concurso e a decisao de elegibilidade. Migracao
            # aditiva e sem backfill — linha anterior ao v6 fica NULL e conta
            # como elegivel (nao se renotifica, nao se reavalia, nao se apaga).
            if "uf" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN uf TEXT")
            if "regiao" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN regiao TEXT")
            if "esfera" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN esfera TEXT")
            if "cargos_total" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN cargos_total INTEGER")
            if "salario_teto" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN salario_teto REAL")
            if "elegibilidade" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN elegibilidade TEXT")
            if "motivo_filtro" not in column_names:
                cursor.execute("ALTER TABLE editais ADD COLUMN motivo_filtro TEXT")

            self.conn.commit()
            self._abrir_unicidade(cursor)
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Erro ao criar/migrar tabela: {e}")

    def _abrir_unicidade(self, cursor: sqlite3.Cursor) -> None:
        """Troca o UNIQUE(area, nome) de tabela pelo indice com o pci_id (v7).

        O UNIQUE de tabela impedia dois editais do mesmo orgao na mesma area.
        Em SQLite ele so sai recriando a tabela: criar a nova, copiar, trocar
        os nomes, tudo numa transacao so. Copia coluna a coluna, com o `id`, e
        devolve ao `sqlite_sequence` o maior id ja emitido, para que um id de
        linha apagada (que pode estar num botao do Telegram) nao volte.

        Idempotente: sem o UNIQUE de tabela nao recria nada, e o indice so e
        criado se ainda nao existe.
        """
        unique_de_tabela = any(
            row["origin"] == "u"
            for row in cursor.execute("PRAGMA index_list(editais)").fetchall()
        )
        if unique_de_tabela:
            cursor.execute("BEGIN")
            seq = cursor.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'editais'"
            ).fetchone()
            colunas = ", ".join(
                row["name"] for row in cursor.execute("PRAGMA table_info(editais)").fetchall()
            )
            self._criar_tabela_editais(cursor, "editais_v7")
            cursor.execute(
                f"INSERT INTO editais_v7 ({colunas}) SELECT {colunas} FROM editais"
            )
            cursor.execute("DROP TABLE editais")
            cursor.execute("ALTER TABLE editais_v7 RENAME TO editais")
            if seq is not None:
                cursor.execute(
                    "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'editais'",
                    (seq["seq"],),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        "INSERT INTO sqlite_sequence (name, seq) VALUES ('editais', ?)",
                        (seq["seq"],),
                    )

        if not self.conn.in_transaction:
            existe = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
                (_INDICE_IDENTIDADE,),
            ).fetchone()
            if existe:
                return
            cursor.execute("BEGIN")
        self._criar_indices(cursor)
        self.conn.commit()

    @staticmethod
    def _criar_indices(cursor: sqlite3.Cursor) -> None:
        # COALESCE: em SQLite NULL nao colide com NULL numa chave unica. Sem ele
        # duas linhas do Gran com o mesmo nome passariam, que e a duplicata que
        # o _resolver_nome_sem_colisao existe para matar. `COALESCE(pci_id, '')`
        # e o criterio de nulidade de `_PCI_ID_SQL` visto pelo indice.
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_INDICE_IDENTIDADE} "
            "ON editais(area, nome, COALESCE(pci_id, ''))"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_editais_pci ON editais(area, pci_id)"
        )

    @staticmethod
    def _create_v3_table(cursor: sqlite3.Cursor) -> None:
        DatabaseManager._criar_tabela_editais(cursor, "editais")
        DatabaseManager._criar_indices(cursor)

    @staticmethod
    def _criar_tabela_editais(cursor: sqlite3.Cursor, nome_tabela: str) -> None:
        """Tabela no formato atual. A unicidade fica no indice, nao aqui."""
        cursor.execute(
            f"""
            CREATE TABLE {nome_tabela} (
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
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    @staticmethod
    def _migrate_to_v3(cursor: sqlite3.Cursor, has_area: bool) -> None:
        """Copia dados v1/v2 para v3 preservando status/link/ultima_atualizacao."""
        cursor.execute(
            """
            CREATE TABLE editais_v3 (
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
        area_expr = "area" if has_area else "'TI'"
        cursor.execute(
            f"""
            INSERT INTO editais_v3 (area, nome, status, link, ultima_atualizacao)
            SELECT {area_expr}, nome, status, link, COALESCE(ultima_atualizacao, CURRENT_TIMESTAMP)
            FROM editais
            """
        )
        cursor.execute("DROP TABLE editais")
        cursor.execute("ALTER TABLE editais_v3 RENAME TO editais")

    @staticmethod
    def _link_e_especifico(link: str, url_indice: str) -> bool:
        """Decide se `link` aponta pra um edital individual (nao a pagina-indice)."""
        if not link:
            return False
        if not url_indice:
            return True
        return link.rstrip("/") != url_indice.rstrip("/")

    def buscar_registro(
        self, nome: str, link: str = "", url_indice: str = "", pci_id: str = ""
    ) -> dict | None:
        """Retorna o registro completo deste edital como dict, ou None.

        Aplica a ordem de identidade documentada no topo do modulo: pci_id,
        link especifico, (area, nome) e por fim casamento de entidade entre
        fontes.

        A chave canonica que discorda vence o nome: item com `pci_id` que nao
        achou a sua linha so casa, pelos fallbacks, com linha SEM `pci_id` (a
        rechave da ADR-0001). Linha com outro `pci_id` e outro edital, ainda
        que do mesmo orgao e com o mesmo nome. Item sem `pci_id` segue a ordem
        de sempre.

        Empate dentro de um passo (duas linhas casam): vence a de menor `id`
        (ver `_DESEMPATE`).
        """
        cursor = self.conn.cursor()
        pci_id = _pci_id_ou_none(pci_id)

        if pci_id:
            row = cursor.execute(
                "SELECT * FROM editais WHERE area = ? AND pci_id = ?" + _DESEMPATE,
                (self.area, pci_id),
            ).fetchone()
            if row:
                return dict(row)

        so_sem_pci_id = f" AND {_PCI_ID_SQL} IS NULL" if pci_id else ""

        if self._link_e_especifico(link, url_indice):
            row = cursor.execute(
                "SELECT * FROM editais WHERE area = ? AND link = ?" + so_sem_pci_id + _DESEMPATE,
                (self.area, link),
            ).fetchone()
            if row:
                return dict(row)

        # COLLATE NOCASE: o LLM varia capitalizacao entre execucoes
        # ("SEDUC AL" vs "Seduc AL") — nao pode virar concurso "novo".
        row = cursor.execute(
            "SELECT * FROM editais WHERE area = ? AND nome = ? COLLATE NOCASE"
            + so_sem_pci_id + _DESEMPATE,
            (self.area, nome),
        ).fetchone()
        if row:
            return dict(row)

        return self._buscar_por_entidade(cursor, nome, pci_id=pci_id or "")

    def _buscar_por_entidade(
        self, cursor: sqlite3.Cursor, nome: str, pci_id: str = ""
    ) -> dict | None:
        """Ultimo recurso: casa o mesmo orgao escrito de formas diferentes.

        E o passo que evita que um concurso ja conhecido pelo Gran entre de novo
        como "novo" quando o PCI o traz com outra grafia. Varre so a area atual;
        sao dezenas de linhas por area, entao o custo e irrelevante. Com
        `pci_id`, pula linha que ja tem outro: mesmo orgao nao e mesmo edital.
        """
        if not nome:
            return None
        for row in cursor.execute(
            "SELECT * FROM editais WHERE area = ?" + _DESEMPATE, (self.area,)
        ).fetchall():
            if pci_id and _pci_id_ou_none(row["pci_id"]):
                continue
            if mesma_entidade(nome, row["nome"]):
                self.logger.info(
                    f"Casou por entidade: {nome!r} = {row['nome']!r} (id={row['id']})."
                )
                return dict(row)
        return None

    def buscar_status_antigo(
        self, nome: str, link: str = "", url_indice: str = ""
    ) -> str | None:
        """Wrapper de conveniencia — retorna apenas o campo `status`."""
        registro = self.buscar_registro(nome, link=link, url_indice=url_indice)
        return registro["status"] if registro else None

    def contar_por_fonte(self, fonte: str) -> int:
        """Quantas linhas desta area vieram de `fonte`.

        Usado para detectar a primeira carga do PCI sem guardar flag em arquivo:
        zero linhas com fonte='pci' significa que o PCI nunca rodou nesta area.
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT COUNT(*) AS n FROM editais WHERE area = ? AND fonte = ?",
            (self.area, fonte),
        ).fetchone()
        return row["n"] if row else 0

    def listar_filtrados(self, desde: str) -> list[dict]:
        """Lista os concursos que o filtro silenciou nesta area, do `desde` em diante.

        E o que o resumo semanal le: so linhas com `elegibilidade = 'filtrado'`
        e `ultima_atualizacao >= desde`, ordenadas por `salario_teto`
        decrescente com NULL no fim. Linha pre-v6 (`elegibilidade` NULL) conta
        como elegivel e nunca aparece aqui.

        Returns:
            list[dict]: um dict por linha, com ao menos `nome`, `uf`,
            `salario_teto`, `motivo_filtro` e `link`.
        """
        # `ultima_atualizacao >= desde` compara TEXTO de proposito: as duas
        # pontas sao AAAA-MM-DD HH:MM:SS (CURRENT_TIMESTAMP do SQLite), formato
        # em que ordem lexicografica e ordem cronologica. Nao "melhore" para
        # conversao de data.
        # `salario_teto IS NULL` primeiro no ORDER BY deixa o NULL no fim.
        cursor = self.conn.cursor()
        rows = cursor.execute(
            """
            SELECT nome, uf, salario_teto, motivo_filtro, link
              FROM editais
             WHERE area = ?
               AND elegibilidade = 'filtrado'
               AND ultima_atualizacao >= ?
             ORDER BY salario_teto IS NULL, salario_teto DESC
            """,
            (self.area, desde),
        ).fetchall()
        return [dict(row) for row in rows]

    def atualizar_concurso(
        self,
        nome: str,
        status: str,
        link: str = "",
        url_indice: str = "",
        status_hash: str | None = None,
        data_fim_inscricao: str | None = None,
        fase: str | None = None,
        fonte: str | None = None,
        pci_id: str | None = None,
        uf: str | None = None,
        regiao: str | None = None,
        esfera: str | None = None,
        cargos_total: int | None = None,
        salario_teto: float | None = None,
        elegibilidade: str | None = None,
        motivo_filtro: str | None = None,
    ) -> int:
        """Insere novo concurso ou atualiza existente, preservando `id`.

        A identidade sai de :meth:`buscar_registro`, entao busca e escrita usam
        exatamente a mesma regra. Preservar o `id` e obrigatorio: ele viaja no
        callback_data dos botoes do Telegram de mensagens ja enviadas.

        Os campos do v6 (`uf` a `salario_teto`, `elegibilidade`, `motivo_filtro`)
        sao opcionais: quem nao conhece o valor passa `None` e nao apaga o que
        ja esta gravado. `elegibilidade` e `motivo_filtro` seguem a mesma regra
        com uma diferenca de leitura: sao decisao, nao descricao — valor novo e
        decisao nova, que vence a velha; `None` e rodada que nao avaliou, que
        preserva a decisao gravada.

        Returns:
            int: `id` da linha (nova ou existente), ou 0 em erro.
        """
        # Vazio entra como NULL: gravar "" poria na linha um pci_id que a busca
        # le como ausente, e o COALESCE do UPDATE apagaria o pci_id gravado.
        pci_id = _pci_id_ou_none(pci_id)
        cursor = self.conn.cursor()
        try:
            existente = self.buscar_registro(
                nome, link=link, url_indice=url_indice, pci_id=pci_id or ""
            )

            if existente:
                id_ = existente["id"]
                nome_final = self._resolver_nome_sem_colisao(
                    cursor, id_, existente["nome"], nome
                )
                # COALESCE em todo campo opcional: uma fonte que nao conhece o
                # prazo (PCI de concurso so previsto) nao pode apagar o prazo
                # que a outra ja tinha descoberto.
                cursor.execute(
                    """
                    UPDATE editais
                       SET nome = ?,
                           status = ?,
                           link = COALESCE(NULLIF(?, ''), link),
                           status_hash = COALESCE(?, status_hash),
                           data_fim_inscricao = COALESCE(?, data_fim_inscricao),
                           fase = COALESCE(?, fase),
                           fonte = COALESCE(?, fonte),
                           pci_id = COALESCE(?, pci_id),
                           uf = COALESCE(?, uf),
                           regiao = COALESCE(?, regiao),
                           esfera = COALESCE(?, esfera),
                           cargos_total = COALESCE(?, cargos_total),
                           salario_teto = COALESCE(?, salario_teto),
                           -- Decisao (nao descricao): valor novo vence o velho,
                           -- rodada sem avaliacao (None) preserva o gravado.
                           elegibilidade = COALESCE(?, elegibilidade),
                           motivo_filtro = COALESCE(?, motivo_filtro),
                           ultima_atualizacao = CURRENT_TIMESTAMP
                     WHERE id = ?
                    """,
                    (nome_final, status, link, status_hash, data_fim_inscricao,
                     fase, fonte, pci_id, uf, regiao, esfera, cargos_total,
                     salario_teto, elegibilidade, motivo_filtro, id_),
                )
                self.conn.commit()
                return id_

            cursor.execute(
                """
                INSERT INTO editais
                    (area, nome, status, link, status_hash, data_fim_inscricao,
                     fase, fonte, pci_id,
                     uf, regiao, esfera, cargos_total, salario_teto,
                     elegibilidade, motivo_filtro, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        CURRENT_TIMESTAMP)
                """,
                (self.area, nome, status, link, status_hash, data_fim_inscricao,
                 fase, fonte, pci_id, uf, regiao, esfera, cargos_total,
                 salario_teto, elegibilidade, motivo_filtro),
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            # A regra de identidade escolheu uma linha (ou nenhuma) e a escrita
            # ainda assim bateu na unicidade: o codigo nao soube resolver. Erro
            # com nome proprio, para nao se confundir com falha de disco.
            self.conn.rollback()
            self.logger.error(
                f"COLISAO DE IDENTIDADE nao resolvida na area {self.area}: "
                f"nome={nome!r} pci_id={pci_id!r} link={link!r}. "
                f"O concurso NAO foi gravado nesta rodada. ({e})"
            )
            return 0
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Erro ao salvar dados no banco ({nome!r}): {e}")
            return 0

    def _resolver_nome_sem_colisao(
        self,
        cursor: sqlite3.Cursor,
        id_existente: int,
        nome_atual: str,
        nome_novo: str,
    ) -> str:
        """Decide o `nome` da linha casada, sem fundir nem apagar linha nenhuma.

        Conservadora de proposito (SPEC-003, R-99): o nome novo so vence quando
        nenhuma outra linha da area o ocupa, sem diferenca de caixa. Havendo
        qualquer conflito, a linha fica com o nome atual e o conflito vai para
        o log, seja a outra linha o mesmo orgao, outro edital do mesmo orgao ou
        outro orgao. Decidir entre esses casos (fundir, herdar chave, trocar o
        nome) exige a tabela de decisao do R-100, que ainda nao existe: sem
        ela, cada guarda acrescentada aqui errou um caso diferente.

        O custo e conhecido: duplicata legada do mesmo orgao continua no banco,
        que e o estado de producao desde 15/09/2026, a ultima fusao do log.

        Returns:
            O nome final da linha.
        """
        if not nome_novo or nome_novo == nome_atual:
            return nome_atual

        conflito = cursor.execute(
            "SELECT id, nome FROM editais"
            " WHERE area = ? AND nome = ? COLLATE NOCASE AND id != ?" + _DESEMPATE,
            (self.area, nome_novo, id_existente),
        ).fetchone()
        if conflito is None:
            return nome_novo

        self.logger.warning(
            f"COLISAO DE NOME na area {self.area}: {nome_novo!r} ja e o nome de "
            f"id={conflito['id']} ({conflito['nome']!r}); mantendo {nome_atual!r} "
            f"em id={id_existente}. Nenhuma linha foi fundida."
        )
        return nome_atual

    def atualizar_estado_usuario(self, id_: int, estado: str) -> bool:
        """Marca o concurso com um dos tres estados validos.

        Returns:
            bool: True se a linha foi atualizada, False se estado invalido ou id inexistente.
        """
        if estado not in _ESTADOS_VALIDOS:
            self.logger.error(f"Estado invalido: {estado!r} (validos: {_ESTADOS_VALIDOS})")
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE editais SET estado_usuario = ? WHERE id = ?",
                (estado, id_),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Erro ao atualizar estado_usuario: {e}")
            return False

    def fechar_conexao(self):
        """Fecha a conexão com o banco de forma segura."""
        if self.conn:
            self.conn.close()
