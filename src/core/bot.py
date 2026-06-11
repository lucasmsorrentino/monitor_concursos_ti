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
from src.utils.fases import (
    sanitizar_fase,
    fase_avancou,
    fase_mais_avancada,
    label as fase_label,
)


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

            if total_concursos_validos == 0:
                # A pagina do Gran sempre lista dezenas de concursos. Zero validos
                # significa varredura cega: site fora do ar, bloqueio, ou mudanca
                # de layout que quebrou o fatiamento. Nunca mascarar isso como sucesso.
                self.logger.warning(
                    f"🚫 Nenhum concurso valido extraido para [{self.area_name}] "
                    f"({total_blocos} bloco(s) brutos). Possivel falha de rede ou mudanca no site; "
                    "enviando alerta em vez do heartbeat de sucesso."
                )
                aviso_msg = (
                    f"⚠️ <b>Atenção - {self.area_name}</b>\n\n"
                    f"Não consegui extrair nenhum concurso da página nesta varredura.\n"
                    f"Costuma ser instabilidade do site (tente mais tarde) ou mudança no layout "
                    f"(o monitor pode precisar de ajuste).\n\n"
                    f"🔗 <a href='{self.scraper.url}'>Abrir a página manualmente</a>"
                )
                self.notifier.notificar(aviso_msg)
            elif novos_cont == 0 and atualizados_cont == 0:
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

        Um concurso e considerado `inativo` quando a inscricao ja encerrou
        (`data_fim_inscricao` passada) OU quando e uma listagem morta — sem
        janela de inscricao conhecida e com o ultimo evento citado no passado
        (ex: "provas previstas para maio de 2025"). Concursos so "previstos",
        sem data alguma, NAO sao inativos.

        A deteccao de mudanca compara a `fase` (vocabulario controlado) e a
        `data_fim_inscricao` — NAO o texto livre do status, que a LLM reformula
        a cada extracao (fonte dos antigos falsos positivos). So avanco de fase
        ou mudanca de data geram notificacao; reescrita e regressao de fase nao.

        Matriz:
            - estado 'ignorado' → skip total (nem atualiza DB)
            - registro None + inativo → salva silencioso
            - registro None + ativo → notifica NOVO + salva
            - registro legado (fase NULL) → backfill silencioso da fase
            - sem avanco de fase e sem mudanca de data → refresh silencioso
            - transicao real (fase avancou e/ou data mudou):
                - estado 'seguindo' → notifica sempre
                - inativo (e nao 'seguindo') → atualiza silencioso
                - caso contrario → notifica ATUALIZACAO

        Returns:
            'novo' | 'atualizado' | 'skip' — para contabilidade do ciclo.
        """
        nome_raw = dados.get('nome', 'Nome não identificado')
        status_raw = dados.get('status', 'Status não detalhado')
        link = dados.get('link', self.scraper.url)
        data_fim = dados.get('data_fim_inscricao')
        fase_nova = sanitizar_fase(dados.get('fase'))

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
        # Listagem morta: sem janela de inscricao conhecida E o ultimo evento citado
        # ja passou (ex: "provas previstas para maio de 2025"). Distinto de um
        # "previsto" legitimo, que nao traz data alguma (data_referencia = None).
        listagem_morta = data_fim is None and self._prazo_encerrado(
            dados.get('data_referencia')
        )
        inativo = prazo_encerrado or listagem_morta

        # --- Caso A: inedito ---
        if registro is None:
            if inativo:
                motivo = "inscricao encerrada" if prazo_encerrado else "evento ja passou (listagem antiga)"
                self.logger.info(
                    f"🔕 [NOVO+INATIVO] {nome_raw}: {motivo}; salvando silencioso."
                )
                self.db.atualizar_concurso(
                    nome_raw, status_raw, link,
                    url_indice=self.scraper.url,
                    status_hash=hash_novo,
                    data_fim_inscricao=data_fim,
                    fase=fase_nova,
                )
                return "skip"

            self.logger.info(f"✨ [NOVO] {nome_raw} detectado pela primeira vez.")
            id_interno = self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
                fase=fase_nova,
            )
            msg = (
                f"<b>🆕 NOVO CONCURSO - {self.area_name}</b>\n\n"
                f"🏛 <b>Instituição:</b> {nome_esc}\n"
                f"📝 <b>Status:</b> {status_esc}\n"
                + (f"📊 <b>Fase:</b> {fase_label(fase_nova)}\n" if fase_nova else "")
                + (f"📅 <b>Inscrições até:</b> {html.escape(data_fim)}\n" if data_fim else "")
                + f"\n🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>"
            )
            self.notifier.notificar_concurso(id_interno, msg)
            self.logger.info(f"✅ {nome_raw} salvo no banco de dados (id={id_interno}).")
            return "novo"

        # --- Caso B.1: linha legada sem fase → backfill silencioso ---
        # Linhas anteriores ao schema v4 nao tem `fase`. Como a LLM reformula o
        # status, comparar texto daria falso positivo. Estrategia: na 1a varredura
        # apenas popula a fase, sem notificar. A partir do proximo ciclo a
        # comparacao por fase funciona normalmente.
        fase_antiga = registro.get('fase')
        if fase_antiga is None:
            self.logger.info(f"🧮 [BACKFILL] {nome_raw}: populando fase (legado); sem notificacao.")
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
                fase=fase_nova,
            )
            return "skip"

        data_antiga = registro.get('data_fim_inscricao')
        avancou = fase_avancou(fase_antiga, fase_nova)
        # Data so conta como mudanca quando uma data NOVA aparece e difere da antiga.
        # Data sumindo (nova None) e quase sempre falha de extracao, nao mudanca real.
        data_mudou = data_fim is not None and data_fim != data_antiga

        # --- Caso B.2: sem transicao real → refresh silencioso ---
        # Reescrita do status ou regressao de fase (flapping da LLM) nao notificam.
        # Preserva a fase mais avancada ja vista para nao oscilar.
        if not avancou and not data_mudou:
            self.logger.debug(f"😴 {nome_raw}: sem avanco de fase nem mudanca de data; sem notificacao.")
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
                fase=fase_mais_avancada(fase_antiga, fase_nova),
            )
            return "skip"

        # --- Caso C: transicao real (fase avancou e/ou data mudou) ---
        fase_final = fase_mais_avancada(fase_antiga, fase_nova)
        estado = registro.get('estado_usuario', 'ativo')
        if estado != 'seguindo' and inativo:
            self.logger.info(
                f"🔕 [TRANSICAO+INATIVO] {nome_raw}: avanco real mas concurso inativo; atualiza silencioso."
            )
            self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=self.scraper.url,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
                fase=fase_final,
            )
            return "skip"

        self.logger.info(
            f"🔔 [TRANSICAO] {nome_raw}: {fase_label(fase_antiga)} → {fase_label(fase_nova)} "
            f"(data_mudou={data_mudou})."
        )
        id_interno = self.db.atualizar_concurso(
            nome_raw, status_raw, link,
            url_indice=self.scraper.url,
            status_hash=hash_novo,
            data_fim_inscricao=data_fim,
            fase=fase_final,
        )
        linhas_transicao = []
        if avancou:
            linhas_transicao.append(f"📈 <b>{fase_label(fase_antiga)} → {fase_label(fase_nova)}</b>")
        if data_mudou:
            linhas_transicao.append(f"📅 <b>Inscrições até:</b> {html.escape(data_fim)}")
        bloco_transicao = ("\n".join(linhas_transicao) + "\n\n") if linhas_transicao else ""
        msg = (
            f"<b>🔔 ATUALIZAÇÃO - {self.area_name}: {nome_esc}</b>\n\n"
            f"{bloco_transicao}"
            f"📝 <b>Status:</b> {status_esc}\n\n"
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
