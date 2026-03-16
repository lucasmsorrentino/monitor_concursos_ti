import sqlite3
import os

class DatabaseManager:
    def __init__(self, area: str = "TI", db_path="data/concursos.db"):
        # Garante que a pasta 'data' exista antes de criar o banco
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

    def buscar_status_antigo(self, nome: str) -> str:
        """Retorna o status salvo anteriormente para um concurso específico."""
        query = "SELECT status FROM editais WHERE area = ? AND nome = ?"
        cursor = self.conn.cursor()
        cursor.execute(query, (self.area, nome))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None

    def atualizar_concurso(self, nome: str, status: str, link: str = ""):
        """Insere um novo concurso ou atualiza o status de um existente."""
        query = '''
        INSERT OR REPLACE INTO editais (area, nome, status, link, ultima_atualizacao)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (self.area, nome, status, link))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Erro ao salvar dados no banco: {e}")

    def fechar_conexao(self):
        """Fecha a conexão com o banco de forma segura."""
        if self.conn:
            self.conn.close()