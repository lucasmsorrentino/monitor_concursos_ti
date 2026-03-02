import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="data/concursos.db"):
        # Garante que a pasta 'data' exista antes de criar o banco
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        """Cria a estrutura da tabela se ela ainda não existir."""
        query = '''
        CREATE TABLE IF NOT EXISTS editais (
            nome TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            link TEXT,
            ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Erro ao criar tabela: {e}")

    def buscar_status_antigo(self, nome: str) -> str:
        """Retorna o status salvo anteriormente para um concurso específico."""
        query = "SELECT status FROM editais WHERE nome = ?"
        cursor = self.conn.cursor()
        cursor.execute(query, (nome,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None

    def atualizar_concurso(self, nome: str, status: str, link: str = ""):
        """Insere um novo concurso ou atualiza o status de um existente."""
        query = '''
        INSERT OR REPLACE INTO editais (nome, status, link, ultima_atualizacao)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        '''
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (nome, status, link))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Erro ao salvar dados no banco: {e}")

    def fechar_conexao(self):
        """Fecha a conexão com o banco de forma segura."""
        if self.conn:
            self.conn.close()