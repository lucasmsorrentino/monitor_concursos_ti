"""Persistencia SQLite com chave composta `(area, nome)`.

Cada instancia do `DatabaseManager` e vinculada a uma area — todas as
operacoes de busca e update usam essa area como filtro implicito. Isso
permite que concursos com o mesmo `nome` em areas diferentes coexistam
sem colisao de chave primaria.

Ao inicializar, o schema e criado (se nao existir) ou migrado do formato
legado single-area (PK somente em `nome`) — linhas existentes sao tagueadas
com area `TI` por compatibilidade.

Deduplicacao por link: o `nome` extraido pelo LLM varia entre execucoes
(ex: "CRM ES" vs "Concurso CRM ES"), entao quando o bloco traz um link
especifico (diferente da URL-indice do scraper) usamos ele como chave de
identidade. O nome humano continua sendo atualizado na mesma linha.
"""
import os
import sqlite3


class DatabaseManager:
    """Gerencia a tabela `editais` para uma area especifica."""

    def __init__(self, area: str = "TI", db_path: str = "data/concursos.db"):
        """Abre (ou cria) o banco SQLite e garante o schema atualizado.

        Args:
            area: Slug da area monitorada (ex: `TI`, `EDUCACAO`).
            db_path: Caminho do arquivo SQLite. A pasta-pai e criada se ausente.
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.area = area
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self):
        """Cria ou migra a tabela para o formato com chave composta (area, nome)."""
        try:
            cursor = self.conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='editais'")
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                cursor.execute('''
                CREATE TABLE editais (
                    area TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    status TEXT NOT NULL,
                    link TEXT,
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (area, nome)
                )
                ''')
                self.conn.commit()
                return

            cursor.execute("PRAGMA table_info(editais)")
            columns = cursor.fetchall()
            has_area_column = any(col[1] == "area" for col in columns)
            primary_key_columns = [col[1] for col in columns if col[5] > 0]

            # Migra banco legado (nome como PK) para PK composta (area, nome).
            if (not has_area_column) or primary_key_columns == ["nome"]:
                cursor.execute('''
                CREATE TABLE editais_v2 (
                    area TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    status TEXT NOT NULL,
                    link TEXT,
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (area, nome)
                )
                ''')
                cursor.execute('''
                INSERT OR REPLACE INTO editais_v2 (area, nome, status, link, ultima_atualizacao)
                SELECT 'TI', nome, status, link, COALESCE(ultima_atualizacao, CURRENT_TIMESTAMP)
                FROM editais
                ''')
                cursor.execute("DROP TABLE editais")
                cursor.execute("ALTER TABLE editais_v2 RENAME TO editais")

            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Erro ao criar tabela: {e}")

    @staticmethod
    def _link_e_especifico(link: str, url_indice: str) -> bool:
        """Decide se `link` aponta pra um edital individual (nao a pagina-indice)."""
        if not link:
            return False
        if not url_indice:
            return True
        return link.rstrip("/") != url_indice.rstrip("/")

    def buscar_status_antigo(self, nome: str, link: str = "", url_indice: str = "") -> str:
        """Retorna o status previo deste edital.

        Quando `link` e especifico (diferente de `url_indice`), a busca usa ele
        como chave canonica — imune a variacoes do `nome` entre execucoes do LLM.
        Caso contrario, cai no match por nome (comportamento legado).
        """
        cursor = self.conn.cursor()
        if self._link_e_especifico(link, url_indice):
            cursor.execute(
                "SELECT status FROM editais WHERE area = ? AND link = ?",
                (self.area, link),
            )
            resultado = cursor.fetchone()
            if resultado:
                return resultado[0]
        cursor.execute(
            "SELECT status FROM editais WHERE area = ? AND nome = ?",
            (self.area, nome),
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None

    def atualizar_concurso(self, nome: str, status: str, link: str = "", url_indice: str = ""):
        """Insere um novo concurso ou atualiza um existente.

        Se `link` for especifico, faz upsert pelo par `(area, link)` — pode
        sobrescrever `nome` caso o LLM tenha extraido uma variacao diferente,
        mantendo uma unica linha por edital.
        """
        cursor = self.conn.cursor()
        try:
            if self._link_e_especifico(link, url_indice):
                cursor.execute(
                    "SELECT nome FROM editais WHERE area = ? AND link = ?",
                    (self.area, link),
                )
                existente = cursor.fetchone()
                if existente:
                    cursor.execute(
                        """
                        UPDATE editais
                           SET nome = ?, status = ?, ultima_atualizacao = CURRENT_TIMESTAMP
                         WHERE area = ? AND link = ?
                        """,
                        (nome, status, self.area, link),
                    )
                    self.conn.commit()
                    return
            cursor.execute(
                """
                INSERT OR REPLACE INTO editais (area, nome, status, link, ultima_atualizacao)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.area, nome, status, link),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Erro ao salvar dados no banco: {e}")

    def fechar_conexao(self):
        """Fecha a conexão com o banco de forma segura."""
        if self.conn:
            self.conn.close()