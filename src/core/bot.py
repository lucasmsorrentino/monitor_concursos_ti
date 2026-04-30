"""Módulo orquestrador do sistema de monitoramento de concursos.

Contém a classe :class:`ConcursoBot`, que coordena o fluxo completo:
Scraping (HTML) → Extração via IA (JSON) → Banco de Dados → Análise de
Mudanças via IA → Notificação (Telegram) com botoes de interesse.
"""

import logging
import html
from datetime import date

from src.scrapers.gran_scraper import GranScraper
from src.database.manager import DatabaseManager
from src.intelligence.langchain_unit import IntelligenceUnit
from src.notifiers.telegram import TelegramNotifier
from src.notifiers.telegram_callbacks import TelegramCallbackProcessor
from src.utils.text import status_fingerprint


class ConcursoBot:
    """Orquestrador principal do pipeline de monitoramento de concursos.

    Integra todos os subsistemas do projeto:

    - :class:`GranScraper` — fatia a página HTML em blocos brutos.
    - :class:`IntelligenceUnit` — extrai JSON dos blocos e analisa mudanças.
    - :class:`DatabaseManager` — persiste o estado de cada concurso.
    - :class:`TelegramNotifier` — envia alertas para o usuário.
    - :class:`TelegramCallbackProcessor` — aplica cliques de ⭐/❌ feitos
      pelo usuario desde a ultima varredura.

    Args:
        config: Dicionário com as chaves ``url_alvo``, ``ollama_model``,
                ``token`` e ``chat_id``.
    """

    def __init__(self, config: dict):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.area_slug = config.get('area', 'TI')
        self.area_name = config.get('display_name', self.area_slug)
        self.keywords_include = [k.lower() for k in config.get('keywords_include', [])]
        self.keywords_exclude = [k.lower() for k in config.get('keywords_exclude', [])]
        self.token = config.get('token', '')

        self.scraper = GranScraper(config['url_alvo'])
        self.db = DatabaseManager(area=self.area_slug)
        self.ai = IntelligenceUnit(
            model_name=config['ollama_model'],
            base_url=config.get('ollama_base_url', 'http://127.0.0.1:11434'),
            timeout_s=config.get('ollama_timeout_s', 120.0),
            retries=config.get('ollama_retries', 2),
            retry_delay_s=config.get('ollama_retry_delay_s', 2.0),
            area_context=self.area_name,
            include_keywords=self.keywords_include,
            exclude_keywords=self.keywords_exclude,
        )
        self.notifier = TelegramNotifier(
            self.token,
            chat_id=config.get('chat_id'),
            chat_ids=config.get('chat_ids', []),
        )

    def executar(self) -> None:
        """Executa um ciclo completo de monitoramento.

        Fluxo:
            1. Processa callbacks pendentes do Telegram (cliques em ⭐/❌).
            2. ``GranScraper`` fatia a página HTML em blocos ``<h3>``.
            3. Cada bloco é enviado à chain de extração da ``IntelligenceUnit``,
               que retorna JSON com ``nome``, ``status``, ``link``, ``ignorar``
               e ``data_fim_inscricao``.
            4. Matriz de decisao por concurso aplicada — ver docstring de
               ``_decidir_e_notificar``.
            5. Mensagem "Varredura Concluida" ao final se nada foi notificado.
        """
        self.logger.info(f"🔍 Iniciando captura de novos editais para area [{self.area_name}]...")

        # Processa cliques pendentes antes do scraping — nao deve travar a varredura.
        self._processar_callbacks_telegram()

        novos_cont = 0
        atualizados_cont = 0

        try:
            blocos_html = self.scraper.capturar_concursos()
            total_blocos = len(blocos_html)
            self.logger.info(f"📊 Scraper retornou {total_blocos} blocos HTML para análise da IA.")

            total_concursos_validos = 0

            for indice, bloco in enumerate(blocos_html, start=1):
                self.logger.info(f"🧩 Processando bloco {indice}/{total_blocos}...")

                if not self._passa_filtro_palavras(bloco):
                    self.logger.debug("🧹 Bloco descartado por filtro rápido de palavras-chave.")
                    continue

                dados = self.ai.extrair_dados(bloco)
                if dados.get("ignorar"):
                    continue

                total_concursos_validos += 1
                resultado = self._decidir_e_notificar(dados)
                if resultado == "novo":
                    novos_cont += 1
                elif resultado == "atualizado":
                    atualizados_cont += 1

            if novos_cont == 0 and atualizados_cont == 0:
                self.logger.info("📭 Nenhuma novidade relevante encontrada. Enviando status para o Telegram...")
                status_msg = (
                    f"✅ <b>Varredura Concluída</b>\n\n"
                    f"📚 <b>Área:</b> {self.area_name}\n"
                    f"🔍 Analisei <b>{total_concursos_validos}</b> concursos validados pela IA e não encontrei nenhuma alteração relevante desde a última consulta.\n\n"
                    f"🕒 <i>Próxima verificação agendada.</i>"
                )
                self.notifier.notificar(status_msg)
            else:
                self.logger.info(
                    f"📊 Ciclo finalizado: {novos_cont} novos e {atualizados_cont} atualizações enviadas."
                )
            self.logger.info("🏁 Ciclo finalizado.")

        except Exception as e:
            self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)

    def _decidir_e_notificar(self, dados: dict) -> str:
        """Aplica a matriz de decisao para um concurso ja extraido.

        Matriz:
            - estado 'ignorado' → skip total (nem atualiza DB)
            - registro None + prazo passou → salva silencioso
            - registro None + prazo aberto/ausente → notifica NOVO + salva
            - hash identico → skip (corrige repeticao)
            - hash diferente + analise IGNORE → atualiza silencioso
            - mudanca relevante:
                - estado 'seguindo' → notifica sempre
                - 'ativo' + prazo passou → atualiza silencioso
                - caso contrario → notifica ATUALIZACAO

        Returns:
            'novo' | 'atualizado' | 'skip' — para contabilidade do ciclo.
        """
        nome_raw = dados.get('nome', 'Nome não identificado')
        status_raw = dados.get('status', 'Status não detalhado')
        link = dados.get('link', self.scraper.url)
        data_fim = dados.get('data_fim_inscricao')

        nome_esc = html.escape(nome_raw)
        status_esc = html.escape(status_raw)
        hash_novo = status_fingerprint(status_raw)

        registro = self.db.buscar_registro(
            nome_raw, link=link, url_indice=self.scraper.url
        )

        if registro and registro.get('estado_usuario') == 'ignorado':
            self.logger.debug(f"🚫 [IGNORADO] {nome_raw} marcado pelo usuario; skip.")
            return "skip"

        prazo_encerrado = self._prazo_encerrado(data_fim)

        # --- Caso A: inedito ---
        if registro is None:
            if prazo_encerrado:
                self.logger.info(
                    f"🔕 [NOVO+FECHADO] {nome_raw}: inscricao encerrou em {data_fim}; salvando silencioso."
                )
                self.db.atualizar_concurso(
                    nome_raw, status_raw, link,
                    url_indice=self.scraper.url,
                    status_hash=hash_novo,
                    data_fim_inscricao=data_fim,
                )
                return "skip"

            self.logger.info(f"✨ [NOVO] {nome_raw} detectado pela primeira vez.")
            id_interno = self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
            )
            msg = (
                f"<b>🆕 NOVO CONCURSO - {self.area_name}</b>\n\n"
                f"🏛 <b>Instituição:</b> {nome_esc}\n"
                f"📝 <b>Status:</b> {status_esc}\n"
                + (f"📅 <b>Inscrições até:</b> {html.escape(data_fim)}\n" if data_fim else "")
                + f"\n🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>"
            )
            self.notifier.notificar_concurso(id_interno, msg)
            self.logger.info(f"✅ {nome_raw} salvo no banco de dados (id={id_interno}).")
            return "novo"

        # --- Caso B.1: linha legada sem status_hash → backfill silencioso ---
        # No primeiro ciclo pos-migracao, o texto em `status` foi armazenado
        # 24h atras e a LLM frequentemente reformula. Sem hash confiavel, a
        # analise da chain pode dar falsos positivos. Estrategia: silenciar
        # a primeira varredura para essas linhas — apenas popula o hash e
        # atualiza o status. A partir do proximo ciclo, a comparacao por
        # hash funciona normalmente.
        if not registro.get('status_hash'):
            self.logger.info(f"🧮 [BACKFILL] {nome_raw}: populando status_hash (legado); sem notificacao.")
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
            )
            return "skip"

        # --- Caso B.2: hash identico (corrige o bug da repeticao) ---
        if registro['status_hash'] == hash_novo:
            self.logger.debug(f"😴 {nome_raw}: fingerprint identico; sem mudanca real.")
            # Atualiza apenas data_fim caso a LLM tenha extraido uma data nova.
            if data_fim and registro.get('data_fim_inscricao') != data_fim:
                self.db.atualizar_concurso(
                    nome_raw, status_raw, link,
                    url_indice=self.scraper.url,
                    status_hash=hash_novo,
                    data_fim_inscricao=data_fim,
                )
            return "skip"

        # --- Caso C: existente, texto diferente — avaliar relevancia ---
        status_antigo = registro['status']
        self.logger.info(f"🔄 [MUDANÇA BRUTA] Detectada alteração de texto em: {nome_raw}")
        self.logger.info(f"🧠 Consultando IA para analisar relevância em {nome_raw}...")
        analise = self.ai.analisar_mudanca(status_antigo, status_raw)

        if not analise:
            self.logger.info(f"😴 [IRRELEVANTE] IA decidiu ignorar a mudança em {nome_raw}.")
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
            )
            return "skip"

        estado = registro.get('estado_usuario', 'ativo')
        if estado != 'seguindo' and prazo_encerrado:
            self.logger.info(
                f"🔕 [POS-PRAZO+ATIVO] {nome_raw}: mudanca relevante mas inscricao encerrou; atualiza silencioso."
            )
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
            )
            return "skip"

        self.logger.info(f"🔔 [RELEVANTE] IA confirmou mudança importante para {nome_raw}.")
        analise_esc = html.escape(analise)
        id_interno = self.db.atualizar_concurso(
            nome_raw, status_raw, link,
            url_indice=self.scraper.url,
            status_hash=hash_novo,
            data_fim_inscricao=data_fim,
        )
        msg = (
            f"<b>🔔 ATUALIZAÇÃO IMPORTANTE - {self.area_name}: {nome_esc}</b>\n\n"
            f"💡 <b>O que mudou:</b> {analise_esc}\n\n"
            f"🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>"
        )
        self.notifier.notificar_concurso(id_interno, msg)
        self.logger.info(f"✅ Banco de dados atualizado para {nome_raw}.")
        return "atualizado"

    @staticmethod
    def _prazo_encerrado(data_fim_iso: str | None) -> bool:
        """True se `data_fim_iso` (ISO YYYY-MM-DD) ja e estritamente passada.

        None ou string invalida -> False (sem prazo conhecido = permite notificar).
        Dia do encerramento ainda conta como aberto (comparacao com `>`).
        """
        if not data_fim_iso:
            return False
        try:
            return date.today() > date.fromisoformat(data_fim_iso)
        except ValueError:
            return False

    def _processar_callbacks_telegram(self) -> None:
        """Aplica cliques em ⭐/❌ feitos desde a ultima varredura.

        Falha silenciosa — problemas de rede/Telegram nao podem impedir
        o scraping seguir.
        """
        if not self.token:
            return
        try:
            processor = TelegramCallbackProcessor(self.token, self.db)
            processor.processar_pendentes()
        except Exception as e:
            self.logger.warning(f"⚠️ Falha ao processar callbacks do Telegram: {e}")

    def __del__(self):
        """Garante que a conexão com o banco seja fechada ao destruir o objeto."""
        if hasattr(self, 'db'):
            self.db.fechar_conexao()
            self.logger.info("🔌 Conexão com o banco de dados encerrada.")

    def _passa_filtro_palavras(self, bloco_html: str) -> bool:
        """Aplica um filtro textual barato antes da chamada da IA."""
        texto = bloco_html.lower()

        if self.keywords_include and not any(keyword in texto for keyword in self.keywords_include):
            return False

        if self.keywords_exclude and any(keyword in texto for keyword in self.keywords_exclude):
            return False

        return True
