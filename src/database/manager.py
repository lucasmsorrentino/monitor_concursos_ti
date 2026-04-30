"""Persistencia SQLite para o monitor de concursos.

Schema v3 (atual):
    editais(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area TEXT NOT NULL,
        nome TEXT NOT NULL,
        status TEXT NOT NULL,
        link TEXT,
        data_fim_inscricao TEXT,       -- ISO YYYY-MM-DD ou NULL
        status_hash TEXT,              -- fingerprint do status para dedup
        estado_usuario TEXT NOT NULL DEFAULT 'ativo',  -- ativo|ignorado|seguindo
        ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(area, nome)
    )

Historico de migracoes:
    v1: PK em `nome` apenas (modo single-area).
    v2: PK composta `(area, nome)` — linhas v1 taggueadas como `TI`.
    v3: adiciona `id AUTOINCREMENT` (necessario para callback_data do Telegram),
        `data_fim_inscricao`, `status_hash`, `estado_usuario`.
        `(area, nome)` mantem uniqueness via UNIQUE constraint.

Dedup por link: quando o bloco traz um link especifico (diferente da
URL-indice do scraper), usamos ele como chave canonica de identidade.
O nome humano pode variar entre execucoes do LLM — o upsert por link
sobrescreve o nome mantendo a mesma linha.
"""
import logging
import os
import sqlite3


_ESTADOS_VALIDOS = ("ativo", "ignorado", "seguindo")


class DatabaseManager:
    """Gerencia a tabela `editais` para uma area especifica."""

    def __init__(self, area: str = "TI", db_path: str = "data/concursos.db"):
        """Abre (ou cria) o banco SQLite e garante o schema atualizado.

        Args:
            area: Slug da area monitorada (ex: `TI`, `EDUCACAO`).
            db_path: Caminho do arquivo SQLite. A pasta-pai e criada se ausente.
        """
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
                estado_usuario TEXT NOT NULL DEFAULT 'ativo',
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
                estado_usuario TEXT NOT NULL DEFAULT 'ativo',
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
        self, nome: str, link: str = "", url_indice: str = ""
    ) -> dict | None:
        """Retorna o registro completo deste edital como dict, ou None.

        Quando `link` e especifico, a busca usa ele como chave canonica;
        caso contrario cai no match por `(area, nome)`.
        """
        cursor = self.conn.cursor()
        if self._link_e_especifico(link, url_indice):
            row = cursor.execute(
                "SELECT * FROM editais WHERE area = ? AND link = ?",
                (self.area, link),
            ).fetchone()
            if row:
                return dict(row)
        row = cursor.execute(
            "SELECT * FROM editais WHERE area = ? AND nome = ?",
            (self.area, nome),
        ).fetchone()
        return dict(row) if row else None

    def buscar_status_antigo(
        self, nome: str, link: str = "", url_indice: str = ""
    ) -> str | None:
        """Wrapper de compatibilidade — retorna apenas o campo `status`."""
        registro = self.buscar_registro(nome, link=link, url_indice=url_indice)
        return registro["status"] if registro else None

    def atualizar_concurso(
        self,
        nome: str,
        status: str,
        link: str = "",
        url_indice: str = "",
        status_hash: str | None = None,
        data_fim_inscricao: str | None = None,
    ) -> int:
        """Insere novo concurso ou atualiza existente, preservando `id`.

        Se `link` for especifico e ja existir registro com esse link, o UPDATE
        mantem o `id` existente (crucial para callback_data do Telegram
        permanecer valido entre execucoes). Caso contrario faz UPSERT por
        (area, nome).

        Returns:
            int: `id` da linha (nova ou existente).
        """
        cursor = self.conn.cursor()
        try:
            if self._link_e_especifico(link, url_indice):
                row = cursor.execute(
                    "SELECT id, nome FROM editais WHERE area = ? AND link = ?",
                    (self.area, link),
                ).fetchone()
                if row:
                    nome_final = self._resolver_nome_sem_colisao(
                        cursor, row["id"], row["nome"], nome
                    )
                    cursor.execute(
                        """
                        UPDATE editais
                           SET nome = ?,
                               status = ?,
                               status_hash = COALESCE(?, status_hash),
                               data_fim_inscricao = COALESCE(?, data_fim_inscricao),
                               ultima_atualizacao = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        (nome_final, status, status_hash, data_fim_inscricao, row["id"]),
                    )
                    self.conn.commit()
                    return row["id"]

            # UPSERT por (area, nome) preservando id se ja existir.
            row = cursor.execute(
                "SELECT id FROM editais WHERE area = ? AND nome = ?",
                (self.area, nome),
            ).fetchone()
            if row:
                cursor.execute(
                    """
                    UPDATE editais
                       SET status = ?,
                           link = ?,
                           status_hash = COALESCE(?, status_hash),
                           data_fim_inscricao = COALESCE(?, data_fim_inscricao),
                           ultima_atualizacao = CURRENT_TIMESTAMP
                     WHERE id = ?
                    """,
                    (status, link, status_hash, data_fim_inscricao, row["id"]),
                )
                self.conn.commit()
                return row["id"]

            cursor.execute(
                """
                INSERT INTO editais
                    (area, nome, status, link, status_hash, data_fim_inscricao, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.area, nome, status, link, status_hash, data_fim_inscricao),
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
        """Decide qual `nome` usar ao atualizar via match por link.

        Se o `nome_novo` do LLM for igual ao existente, ou se nao colidir com
        nenhuma outra linha da mesma area, usa o `nome_novo`. Caso colida com
        outra linha (UNIQUE(area, nome) violaria), mantem o `nome_atual` —
        o link e canonico, a variacao do nome e cosmetica.
        """
        if not nome_novo or nome_novo == nome_atual:
            return nome_atual
        conflito = cursor.execute(
            "SELECT id FROM editais WHERE area = ? AND nome = ? AND id != ?",
            (self.area, nome_novo, id_existente),
        ).fetchone()
        if conflito:
            self.logger.warning(
                f"Nome {nome_novo!r} colide com id={conflito['id']}; mantendo {nome_atual!r} em id={id_existente}."
            )
            return nome_atual
        return nome_novo

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
