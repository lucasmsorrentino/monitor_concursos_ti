import logging
from scrapers.gran_scraper import GranScraper
from database.manager import DatabaseManager
from intelligence.langchain_unit import IntelligenceUnit
from notifiers.telegram import TelegramNotifier

class ConcursoBot:
    def __init__(self, config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scraper = GranScraper(config['url_alvo'])
        self.db = DatabaseManager()
        self.ai = IntelligenceUnit(model_name=config['ollama_model'])
        self.notifier = TelegramNotifier(config['token'], config['chat_id'])

    def executar(self):
        print("🚀 Iniciando ciclo de monitoramento...")
        self.logger.info("🔍 Iniciando captura de novos editais...")

        try:   
            # 1. Captura os dados brutos
            concursos_atuais = self.scraper.capturar_concursos()
            self.logger.info(f"📊 Scraper retornou {len(concursos_atuais)} itens para análise.")

            for item in concursos_atuais:
                nome = item['nome']
                status_novo = item['status']
                link = item['link']

                # 2. Consulta o passado (Banco de Dados)
                status_antigo = self.db.buscar_status_antigo(nome)

                # Caso A: Concurso inédito
                if status_antigo is None:
                    print(f"🆕 Novo concurso detectado: {nome}")
                    self.logger.info(f"✨ [NOVO] {nome} detectado pela primeira vez.")
                    msg = f"🆕 *NOVO CONCURSO DE TI*\n\n🏛 *{nome}*\n📝 {status_novo}"
                    self.notifier.notificar(msg)
                    self.db.atualizar_concurso(nome, status_novo, link)
                    self.logger.info(f"✅ {nome} salvo no banco de dados.")

                # Caso B: Já existia, mas o texto mudou
                elif status_antigo != status_novo:
                    print(f"🔄 Possível atualização em: {nome}")
                    self.logger.info(f"🔄 [MUDANÇA BRUTA] Detectada alteração de texto em: {nome}")
                    
                    # 3. Inteligência Artificial decide se a mudança importa
                    self.logger.info(f"🧠 Consultando IA para analisar relevância em {nome}...")
                    analise = self.ai.analisar_mudanca(status_antigo, status_novo)
                    
                    if analise:
                        print(f"🔔 Mudança relevante confirmada pela IA!")
                        self.logger.info(f"🔔 [RELEVANTE] IA confirmou mudança importante para {nome}.")
                        msg = f"🔔 *ATUALIZAÇÃO: {nome}*\n\n💡 {analise}"
                        self.notifier.notificar(msg)
                        # Atualiza o banco para não notificar a mesma coisa de novo
                        self.db.atualizar_concurso(nome, status_novo, link)
                        self.logger.info(f"✅ Banco de dados atualizado para {nome}.")
                    else:
                        print(f"😴 IA ignorou mudança irrelevante em {nome}.")
                        self.logger.info(f"😴 [IRRELEVANTE] IA decidiu ignorar a mudança em {nome}.")

            print("🏁 Ciclo finalizado. Até a próxima!")
            self.logger.info("🏁 Ciclo de monitoramento finalizado com sucesso.")

        except Exception as e:
            # O parâmetro exc_info=True salva o rastro completo do erro (Stack Trace)
            self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)
        
    def __del__(self):
        """Garante que a conexão com o banco seja fechada ao destruir o objeto."""
        if hasattr(self, 'db'):
            self.db.fechar_conexao()
            self.logger.info("🔌 Conexão com o banco de dados encerrada.")
