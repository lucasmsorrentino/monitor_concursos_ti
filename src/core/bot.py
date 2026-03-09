import logging
import html
from src.scrapers.gran_scraper import GranScraper
from src.database.manager import DatabaseManager
from src.intelligence.langchain_unit import IntelligenceUnit
from src.notifiers.telegram import TelegramNotifier

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
        
        # 1. Inicializamos contadores para saber o que aconteceu no ciclo
        novos_cont = 0
        atualizados_cont = 0

        try:   
            # 1. Captura os dados brutos (Agora são BLOCOS de HTML em vez de dicionários)
            blocos_html = self.scraper.capturar_concursos()
            total_blocos = len(blocos_html)
            self.logger.info(f"📊 Scraper retornou {total_blocos} blocos HTML para análise da IA.")

            # Contador para sabermos quantos concursos reais sobraram após a IA filtrar a redundância
            total_concursos_validos = 0

            for bloco in blocos_html:
                # --- NOVIDADE: A IA lê o HTML e extrai o JSON limpo ---
                dados = self.ai.extrair_dados(bloco)

                # Se a IA decidiu que é apenas redundância (lista sem link, etc), pulamos.
                if dados.get("ignorar"):
                    continue
                
                total_concursos_validos += 1

                # Extrai as variáveis e protege contra caracteres especiais no Telegram
                nome = html.escape(dados.get('nome', 'Nome não identificado'))
                status_novo = html.escape(dados.get('status', 'Status não detalhado'))
                link = dados.get('link', self.scraper.url)

                # 2. Consulta o passado (Banco de Dados)
                status_antigo = self.db.buscar_status_antigo(nome)

                # Caso A: Concurso inédito
                if status_antigo is None:
                    print(f"🆕 Novo concurso detectado: {nome}")
                    self.logger.info(f"✨ [NOVO] {nome} detectado pela primeira vez.")
                    novos_cont += 1

                    msg = (f"<b>🆕 NOVO CONCURSO DE TI</b>\n\n"
                           f"🏛 <b>Instituição:</b> {nome}\n"
                           f"📝 <b>Status:</b> {status_novo}\n\n"
                           f"🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>")
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

                        analise_esc = html.escape(analise)
                        msg = (f"<b>🔔 ATUALIZAÇÃO IMPORTANTE: {nome}</b>\n\n"
                               f"💡 <b>O que mudou:</b> {analise_esc}\n\n"
                               f"🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>")
                        
                        self.notifier.notificar(msg)
                        # Atualiza o banco para não notificar a mesma coisa de novo
                        self.db.atualizar_concurso(nome, status_novo, link)
                        atualizados_cont += 1
                        self.logger.info(f"✅ Banco de dados atualizado para {nome}.")
                    else:
                        print(f"😴 IA ignorou mudança irrelevante em {nome}.")
                        self.logger.info(f"😴 [IRRELEVANTE] IA decidiu ignorar a mudança em {nome}.")
                
                # Caso C: Já existia e o texto continua igual
                else:
                    self.logger.debug(f"😴 {nome}: Sem alterações desde a última consulta.")

            # --- NOVIDADE: VERIFICAÇÃO FINAL APÓS O LOOP ---
            if novos_cont == 0 and atualizados_cont == 0:
                self.logger.info("📭 Nenhuma novidade relevante encontrada. Enviando status para o Telegram...")
                
                # Mensagem amigável de "Tudo na mesma"
                status_msg = (f"✅ <b>Varredura Concluída</b>\n\n"
                              f"🔍 Analisei <b>{total_concursos_validos}</b> concursos validados pela IA e não encontrei nenhuma alteração relevante desde a última consulta.\n\n"
                              f"🕒 <i>Próxima verificação agendada.</i>")
                
                self.notifier.notificar(status_msg)
            else:
                self.logger.info(f"📊 Ciclo finalizado: {novos_cont} novos e {atualizados_cont} atualizações enviadas.")
            print("🏁 Ciclo finalizado. Até a próxima!")

        except Exception as e:
            # O parâmetro exc_info=True salva o rastro completo do erro (Stack Trace)
            self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)
        
    def __del__(self):
        """Garante que a conexão com o banco seja fechada ao destruir o objeto."""
        if hasattr(self, 'db'):
            self.db.fechar_conexao()
            self.logger.info("🔌 Conexão com o banco de dados encerrada.")


# import logging
# from src.scrapers.gran_scraper import GranScraper
# from src.database.manager import DatabaseManager
# from src.intelligence.langchain_unit import IntelligenceUnit
# from src.notifiers.telegram import TelegramNotifier

# class ConcursoBot:
#     def __init__(self, config):
#         self.logger = logging.getLogger(self.__class__.__name__)
#         self.scraper = GranScraper(config['url_alvo'])
#         self.db = DatabaseManager()
#         self.ai = IntelligenceUnit(model_name=config['ollama_model'])
#         self.notifier = TelegramNotifier(config['token'], config['chat_id'])

#     def executar(self):
#         print("🚀 Iniciando ciclo de monitoramento...")
#         self.logger.info("🔍 Iniciando captura de novos editais...")
        
#         # 1. Inicializamos contadores para saber o que aconteceu no ciclo
#         novos_cont = 0
#         atualizados_cont = 0

#         try:   
#             # 1. Captura os dados brutos
#             concursos_atuais = self.scraper.capturar_concursos()
#             total_concursos = len(concursos_atuais)
#             self.logger.info(f"📊 Scraper retornou {total_concursos} itens para análise.")

#             for item in concursos_atuais:
#                 nome = item['nome']
#                 status_novo = item['status']
#                 link = item['link']

#                 # 2. Consulta o passado (Banco de Dados)
#                 status_antigo = self.db.buscar_status_antigo(nome)

#                 # Caso A: Concurso inédito
#                 if status_antigo is None:
#                     print(f"🆕 Novo concurso detectado: {nome}")
#                     self.logger.info(f"✨ [NOVO] {nome} detectado pela primeira vez.")
#                     novos_cont += 1

#                     # Adicionamos o 🔗 [Acesse o Edital]({link})                
#                     #msg = f"🆕 <b>NOVO CONCURSO DE TI</b>\n\n🏛 <b>{nome}</b>\n📝 {status_novo}\n\n🔗 [Acesse a matéria aqui]({link})"
#                     msg = (f"<b>🆕 NOVO CONCURSO DE TI</b>\n\n"
#                            f"🏛 <b>Instituição:</b> {nome}\n"
#                            f"📝 <b>Status:</b> {status_novo}\n\n"
#                            f"🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>")
#                     self.notifier.notificar(msg)
#                     self.db.atualizar_concurso(nome, status_novo, link)
#                     self.logger.info(f"✅ {nome} salvo no banco de dados.")

#                 # Caso B: Já existia, mas o texto mudou
#                 elif status_antigo != status_novo:
#                     print(f"🔄 Possível atualização em: {nome}")
#                     self.logger.info(f"🔄 [MUDANÇA BRUTA] Detectada alteração de texto em: {nome}")
                    
#                     # 3. Inteligência Artificial decide se a mudança importa
#                     self.logger.info(f"🧠 Consultando IA para analisar relevância em {nome}...")
#                     analise = self.ai.analisar_mudanca(status_antigo, status_novo)
                    
#                     if analise:
#                         print(f"🔔 Mudança relevante confirmada pela IA!")
#                         self.logger.info(f"🔔 [RELEVANTE] IA confirmou mudança importante para {nome}.")

#                         #msg = f"🔔 <b>ATUALIZAÇÃO: {nome}</b>\n\n💡 {analise}\n\n🔗 [Acesse a matéria aqui]({link})"
#                         msg = (f"<b>🔔 ATUALIZAÇÃO IMPORTANTE: {nome}</b>\n\n"
#                                f"💡 <b>O que mudou:</b> {analise}\n\n"
#                                f"🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>")
                        
#                         self.notifier.notificar(msg)
#                         # Atualiza o banco para não notificar a mesma coisa de novo
#                         self.db.atualizar_concurso(nome, status_novo, link)
#                         atualizados_cont += 1
#                         self.logger.info(f"✅ Banco de dados atualizado para {nome}.")
#                 else:
#                     print(f"😴 IA ignorou mudança irrelevante em {nome}.")
#                     self.logger.info(f"😴 [IRRELEVANTE] IA decidiu ignorar a mudança em {nome}.")

#             # --- NOVIDADE: VERIFICAÇÃO FINAL APÓS O LOOP ---
            
#             if novos_cont == 0 and atualizados_cont == 0:
#                 self.logger.info("📭 Nenhuma novidade relevante encontrada. Enviando status para o Telegram...")
                
#                 # Mensagem amigável de "Tudo na mesma"
#                 status_msg = (f"✅ <b>Varredura Concluída</b>\n\n"
#                              f"🔍 Analisei <b>{total_concursos}</b> concursos no Gran Cursos e não encontrei nenhuma alteração relevante desde a última consulta.\n\n"
#                              f"🕒 <i>Próxima verificação agendada.</i>")
                
#                 self.notifier.notificar(status_msg)
#             else:
#                 self.logger.info(f"📊 Ciclo finalizado: {novos_cont} novos e {atualizados_cont} atualizações enviadas.")
#             print("🏁 Ciclo finalizado. Até a próxima!")

#         except Exception as e:
#             # O parâmetro exc_info=True salva o rastro completo do erro (Stack Trace)
#             self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)
        
#     def __del__(self):
#         """Garante que a conexão com o banco seja fechada ao destruir o objeto."""
#         if hasattr(self, 'db'):
#             self.db.fechar_conexao()
#             self.logger.info("🔌 Conexão com o banco de dados encerrada.")
