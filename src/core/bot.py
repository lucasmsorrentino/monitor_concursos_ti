"""Módulo orquestrador do sistema de monitoramento de concursos.

Contém a classe :class:`ConcursoBot`, que coordena o fluxo completo:
Scraping (HTML) → Extração via IA (JSON) → Banco de Dados → Análise de
Mudanças via IA → Notificação (Telegram).
"""

import logging
import html
from src.scrapers.gran_scraper import GranScraper
from src.database.manager import DatabaseManager
from src.intelligence.langchain_unit import IntelligenceUnit
from src.notifiers.telegram import TelegramNotifier


class ConcursoBot:
    """Orquestrador principal do pipeline de monitoramento de concursos.

    Integra todos os subsistemas do projeto:

    - :class:`GranScraper` — fatia a página HTML em blocos brutos.
    - :class:`IntelligenceUnit` — extrai JSON dos blocos e analisa mudanças.
    - :class:`DatabaseManager` — persiste o estado de cada concurso.
    - :class:`TelegramNotifier` — envia alertas para o usuário.

    Args:
        config: Dicionário com as chaves ``url_alvo``, ``ollama_model``,
                ``token`` e ``chat_id``.
    """

    def __init__(self, config: dict):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scraper = GranScraper(config['url_alvo'])
        self.db = DatabaseManager()
        self.ai = IntelligenceUnit(
            model_name=config['ollama_model'],
            base_url=config.get('ollama_base_url', 'http://127.0.0.1:11434'),
            timeout_s=config.get('ollama_timeout_s', 120.0),
            retries=config.get('ollama_retries', 2),
            retry_delay_s=config.get('ollama_retry_delay_s', 2.0),
        )
        self.notifier = TelegramNotifier(config['token'], config['chat_id'])

    def executar(self) -> None:
        """Executa um ciclo completo de monitoramento.

        Fluxo:
            1. O ``GranScraper`` fatia a página HTML em blocos ``<h3>``.
            2. Cada bloco é enviado à chain de extração da ``IntelligenceUnit``,
               que retorna um JSON com ``nome``, ``status``, ``link`` e ``ignorar``.
            3. Blocos marcados como ``ignorar`` (listas genéricas, etc.) são descartados.
            4. Para concursos inéditos, uma notificação é enviada e o registro é
               salvo no banco de dados.
            5. Para concursos já conhecidos cujo texto mudou, a chain de análise
               da ``IntelligenceUnit`` decide se a mudança é relevante.
            6. Ao final, se nenhuma novidade foi encontrada, envia uma mensagem
               de status ao Telegram confirmando a varredura.
        """
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

            for indice, bloco in enumerate(blocos_html, start=1):
                self.logger.info(f"🧩 Processando bloco {indice}/{total_blocos}...")
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
            self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)

    def __del__(self):
        """Garante que a conexão com o banco seja fechada ao destruir o objeto."""
        if hasattr(self, 'db'):
            self.db.fechar_conexao()
            self.logger.info("🔌 Conexão com o banco de dados encerrada.")
