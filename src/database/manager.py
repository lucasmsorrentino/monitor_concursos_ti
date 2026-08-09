"""Persistencia SQLite para o monitor de concursos.

Schema v5 (atual):
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
        ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(area, nome)
    )

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

Ordem de identidade (do mais forte pro mais fraco):
    1. `pci_id` — id da noticia no PCI, estavel entre rodadas.
    2. link especifico (diferente da URL-indice do scraper).
    3. `(area, nome)` COLLATE NOCASE.
    4. `mesma_entidade` sobre os tokens do nome — e o unico passo que cruza
       fontes, porque Gran e PCI escrevem o mesmo orgao de formas diferentes
       ("Prefeitura de Ponta Grossa - PR" x "Concurso Prefeitura Ponta Grossa").

Preservar o `id` importa: ele vai no `callback_data` dos botoes do Telegram,
entao trocar de id invalida os botoes de mensagens ja enviadas.
"""
import logging
import os
import sqlite3

from src.utils.fases import fase_mais_avancada
from src.utils.text import mesma_entidade

_ESTADOS_VALIDOS = ("ativo", "ignorado", "seguindo")

# Prioridade ao fundir duas linhas do mesmo orgao: o que o Lucas marcou a mao
# nunca pode ser perdido por causa de uma fusao automatica.
_PRIORIDADE_ESTADO = {"seguindo": 2, "ignorado": 1, "ativo": 0}

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
        """Cria a tabela v3 ou migra esquemas antigos (v1, v2) para v3."""
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

            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Erro ao criar/migrar tabela: {e}")

    @staticmethod
    def _create_v3_table(cursor: sqlite3.Cursor) -> None:
        cursor.execute(
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
        """
        cursor = self.conn.cursor()

        if pci_id:
            row = cursor.execute(
                "SELECT * FROM editais WHERE area = ? AND pci_id = ?",
                (self.area, pci_id),
            ).fetchone()
            if row:
                return dict(row)

        if self._link_e_especifico(link, url_indice):
            row = cursor.execute(
                "SELECT * FROM editais WHERE area = ? AND link = ?",
                (self.area, link),
            ).fetchone()
            if row:
                return dict(row)

        # COLLATE NOCASE: o LLM varia capitalizacao entre execucoes
        # ("SEDUC AL" vs "Seduc AL") — nao pode virar concurso "novo".
        row = cursor.execute(
            "SELECT * FROM editais WHERE area = ? AND nome = ? COLLATE NOCASE",
            (self.area, nome),
        ).fetchone()
        if row:
            return dict(row)

        return self._buscar_por_entidade(cursor, nome)

    def _buscar_por_entidade(self, cursor: sqlite3.Cursor, nome: str) -> dict | None:
        """Ultimo recurso: casa o mesmo orgao escrito de formas diferentes.

        E o passo que evita que um concurso ja conhecido pelo Gran entre de novo
        como "novo" quando o PCI o traz com outra grafia. Varre so a area atual;
        sao dezenas de linhas por area, entao o custo e irrelevante.
        """
        if not nome:
            return None
        for row in cursor.execute(
            "SELECT * FROM editais WHERE area = ?", (self.area,)
        ).fetchall():
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
    ) -> int:
        """Insere novo concurso ou atualiza existente, preservando `id`.

        A identidade sai de :meth:`buscar_registro`, entao busca e escrita usam
        exatamente a mesma regra. Preservar o `id` e obrigatorio: ele viaja no
        callback_data dos botoes do Telegram de mensagens ja enviadas.

        Returns:
            int: `id` da linha (nova ou existente), ou 0 em erro.
        """
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
                           ultima_atualizacao = CURRENT_TIMESTAMP
                     WHERE id = ?
                    """,
                    (nome_final, status, link, status_hash, data_fim_inscricao,
                     fase, fonte, pci_id, id_),
                )
                self.conn.commit()
                return id_

            cursor.execute(
                """
                INSERT INTO editais
                    (area, nome, status, link, status_hash, data_fim_inscricao,
                     fase, fonte, pci_id, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.area, nome, status, link, status_hash, data_fim_inscricao,
                 fase, fonte, pci_id),
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Erro ao salvar dados no banco ({nome!r}): {e}")
            return 0

    def _resolver_nome_sem_colisao(
        self, cursor: sqlite3.Cursor, id_existente: int, nome_atual: str, nome_novo: str
    ) -> str:
        """Decide o `nome` da linha, FUNDINDO duplicatas do mesmo orgao.

        Antes esta funcao so desistia do nome novo quando ele colidia, e as duas
        linhas duplicadas ficavam no banco pra sempre. A varredura de 08/08
        logou quatro casos assim (SEFIN RO, Seduc AL, IFFar, UEAP): o mesmo
        orgao ocupando dois ids, cada um com metade da historia.

        Agora, quando a colisao e o MESMO orgao, as linhas sao fundidas na que
        foi casada por identidade forte (pci_id ou link), nao na de menor id: e
        ela que representa este concurso na varredura corrente. Quando sao
        orgaos de fato distintos que por acaso disputam o nome, mantem o
        comportamento antigo de preservar o nome atual.
        """
        if not nome_novo or nome_novo == nome_atual:
            return nome_atual

        conflito = cursor.execute(
            "SELECT * FROM editais WHERE area = ? AND nome = ? COLLATE NOCASE AND id != ?",
            (self.area, nome_novo, id_existente),
        ).fetchone()
        if not conflito:
            return nome_novo

        if not mesma_entidade(nome_novo, nome_atual):
            self.logger.warning(
                f"Nome {nome_novo!r} colide com id={conflito['id']} e nao e o mesmo orgao; "
                f"mantendo {nome_atual!r} em id={id_existente}."
            )
            return nome_atual

        self._fundir(cursor, mantem=id_existente, descarta=dict(conflito))
        return nome_novo

    def _fundir(self, cursor: sqlite3.Cursor, mantem: int, descarta: dict) -> None:
        """Funde a linha `descarta` na linha `mantem` e remove a duplicata.

        O estado marcado pelo Lucas (seguindo/ignorado) tem prioridade sobre
        'ativo' e sobrevive a fusao, venha de qual das duas linhas vier. Perder
        um "seguindo" numa fusao automatica seria destruir dado do usuario.
        """
        atual = cursor.execute(
            "SELECT * FROM editais WHERE id = ?", (mantem,)
        ).fetchone()
        if not atual:
            return

        estado = max(
            (atual["estado_usuario"] or "ativo", descarta.get("estado_usuario") or "ativo"),
            key=lambda e: _PRIORIDADE_ESTADO.get(e, 0),
        )
        fase_final = fase_mais_avancada(atual["fase"], descarta.get("fase"))

        cursor.execute(
            """
            UPDATE editais
               SET estado_usuario = ?,
                   fase = COALESCE(?, fase),
                   data_fim_inscricao = COALESCE(data_fim_inscricao, ?),
                   link = COALESCE(link, ?),
                   pci_id = COALESCE(pci_id, ?),
                   fonte = COALESCE(fonte, ?)
             WHERE id = ?
            """,
            (estado, fase_final, descarta.get("data_fim_inscricao"),
             descarta.get("link"), descarta.get("pci_id"), descarta.get("fonte"), mantem),
        )
        cursor.execute("DELETE FROM editais WHERE id = ?", (descarta["id"],))
        self.logger.info(
            f"Fundido id={descarta['id']} ({descarta.get('nome')!r}) em id={mantem}; "
            f"estado preservado: {estado}."
        )

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
