"""Módulo orquestrador do sistema de monitoramento de concursos.

Contém a classe :class:`ConcursoBot`, que coordena o fluxo completo:
Scraping (HTML) → Extração via IA (JSON) → Banco de Dados → Notificação
(Telegram) com botoes de interesse.

Fontes (08/2026): cada area pode ler de mais de um lugar. O blog do Gran
devolve blocos de HTML que precisam da LLM para virar dados; o PCI Concursos
devolve dados ja estruturados e nao passa pela LLM. O loop trata os dois como
"candidatos" e so muda o caminho ate obter o dict de dados — dali pra frente
(matriz de decisao, dedup, botoes) tudo e igual.
"""

import html
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta

from bs4 import BeautifulSoup

from src.database.manager import DatabaseManager
from src.intelligence.langchain_unit import IntelligenceUnit
from src.notifiers.telegram import TelegramNotifier
from src.notifiers.telegram_callbacks import TelegramCallbackProcessor
from src.scrapers.gran_scraper import GranScraper
from src.scrapers.pci_nacional_scraper import PciNacionalScraper
from src.scrapers.pci_scraper import PciScraper
from src.utils import memoria_json, saude_fontes
from src.utils.fases import (
    sanitizar_fase,
    fase_avancou,
    fase_mais_avancada,
    label as fase_label,
)
from src.utils.logger import LOG_DIR
from src.utils.text import status_fingerprint

# Acima desta fracao de blocos perdidos na extracao, a varredura da area deixa
# de reportar "concluida" e passa a alertar. Perder 1 bloco em 45 e ruido de
# rede; perder metade significa que o resultado do dia nao vale nada.
LIMITE_ERRO_EXTRACAO = 0.20

# Marcadores de classe CSS que indicam conteudo lateral, nao o edital em si.
# Blocos com essas classes sao descartados antes do filtro de palavras.
_CLASSES_LATERAIS = (
    "relacionad", "sidebar", "widget", "menu", "rodape", "footer",
    "compartilh", "share", "leia-tambem", "leia_tambem", "veja-tambem",
    "veja_tambem", "recomend", "tags", "breadcrumb", "banner", "publicidade",
)

# Estado dos itens da pagina nacional ja julgados fora da area pela LLM, para
# nao pagar uma chamada por dia pelo mesmo "nao e TI". Ver `_nacional_ja_descartado`.
ARQUIVO_DESCARTES = "pci_nacional_descartados"
DIAS_REJULGAR_DESCARTE = 30
DIAS_MANTER_DESCARTE = 120

# Modos de primeira carga do PCI (config `pci_primeira_carga` por alvo).
CARGA_INDIVIDUAL = "individual"   # um card por edital, com botoes
CARGA_RESUMO_UF = "resumo_uf"     # uma mensagem por estado
CARGA_SILENCIOSA = "silencioso"   # so semeia o banco


@dataclass(frozen=True)
class ResultadoFonte:
    """O que uma fonte contribuiu para os contadores da rodada."""

    validos: int
    erros: int
    novos: int
    atualizados: int
    diagnostico: saude_fontes.Diagnostico


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
        self.dry_run = bool(config.get('dry_run'))

        self.scraper = GranScraper(config['url_alvo'])
        self.pci_slugs = [s for s in (config.get('pci_slugs') or []) if s]
        self.pci_scraper = PciScraper(self.pci_slugs) if self.pci_slugs else None
        # Terceira fonte: a lista de concursos NACIONAIS do PCI. E o unico lugar
        # onde estatal federal aparece — nem o artigo do Gran nem os slugs de
        # cargo listaram a Dataprev com as inscricoes abertas (ver o docstring
        # do PciNacionalScraper).
        self.nacional_scraper = (
            PciNacionalScraper() if config.get('pci_nacional') else None
        )
        self.dias_fonte_parada = int(
            config.get('dias_fonte_parada') or saude_fontes.DIAS_PARADA_PADRAO
        )
        self.modo_primeira_carga = config.get('pci_primeira_carga', CARGA_INDIVIDUAL)

        # Setado quando qualquer etapa da varredura falha. O MultiAreaRunner
        # agrega e o main.py devolve exit != 0, para o run_daily.sh nao gravar o
        # marker de sucesso e o catch-up horario tentar de novo. Antes disso, um
        # crash no meio da area virava "varredura concluida" e o dia seguinte
        # parecia saudavel.
        self.falhou = False
        # Quando nao e None, editais novos sao acumulados aqui em vez de
        # notificados um a um (primeira carga do PCI).
        self._coletor_carga: list[dict] | None = None
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
            2. Cada fonte configurada devolve candidatos. O Gran devolve blocos
               de HTML, que passam pelo filtro de palavras e pela extracao da
               ``IntelligenceUnit``; o PCI devolve dados ja estruturados.
            3. Matriz de decisao por concurso — ver ``_decidir_e_notificar``.
            4. Mensagem final: alerta se a varredura ficou cega ou se muitos
               blocos se perderam na extracao; caso contrario heartbeat.
        """
        self.logger.info(f"🔍 Iniciando captura de novos editais para area [{self.area_name}]...")

        # Processa cliques pendentes antes do scraping — nao deve travar a varredura.
        self._processar_callbacks_telegram()

        novos_cont = 0
        atualizados_cont = 0
        validos = 0
        erros_extracao = 0
        total_blocos_gran = 0
        diagnosticos: list[saude_fontes.Diagnostico] = []
        links_pci_vistos: set[str] = set()

        try:
            primeira_carga_pci = self._preparar_primeira_carga()

            # --- Fonte 1: blog do Gran (HTML bruto, precisa da LLM) ---
            blocos_html = self.scraper.capturar_concursos()
            total_blocos_gran = len(blocos_html)
            self.logger.info(
                f"📊 Gran retornou {total_blocos_gran} blocos HTML para análise da IA."
            )
            # Assinatura pelo TEXTO VISIVEL, nao pelo HTML: id de anuncio e
            # token de sessao mudam a cada request e fariam uma pagina
            # congelada parecer viva para sempre.
            diagnosticos.append(
                self._avaliar_fonte("gran", (self._texto_visivel(b) for b in blocos_html))
            )

            for indice, bloco in enumerate(blocos_html, start=1):
                self.logger.info(f"🧩 Processando bloco {indice}/{total_blocos_gran}...")

                if not self._passa_filtro_palavras(bloco):
                    self.logger.debug("🧹 Bloco descartado por filtro rápido de palavras-chave.")
                    continue

                dados = self.ai.extrair_dados(bloco)
                if dados.get("erro"):
                    erros_extracao += 1
                    continue
                if dados.get("ignorar"):
                    continue

                validos += 1
                dados["fonte"] = "gran"
                resultado = self._decidir_e_notificar(dados, url_indice=self.scraper.url)
                novos_cont += resultado == "novo"
                atualizados_cont += resultado == "atualizado"

            # --- Fonte 2: PCI Concursos por slug de cargo (ja estruturado, sem LLM) ---
            if self.pci_scraper:
                itens_pci = self.pci_scraper.capturar_concursos()
                diagnosticos.append(self._avaliar_fonte(
                    "pci", (f"{i['pci_id']}|{i['status']}" for i in itens_pci)
                ))

                for item in itens_pci:
                    # Enriquecer custa uma requisicao na noticia, entao so vale
                    # pra quem ainda nao esta no banco. A pagina de cargo nunca
                    # traz o prazo, e o prazo e o que define se o edital esta ativo.
                    if not self.db.buscar_registro(
                        item["nome"], link=item["link"], pci_id=item["pci_id"]
                    ):
                        self.pci_scraper.enriquecer(item)

                    validos += 1
                    links_pci_vistos.add(item["link"])
                    resultado = self._decidir_e_notificar(item, url_indice=item["link"])
                    novos_cont += resultado == "novo"
                    atualizados_cont += resultado == "atualizado"

            # --- Fonte 3: PCI Concursos, lista NACIONAL (estatal federal) ---
            if self.nacional_scraper:
                parcial = self._varrer_nacional(links_pci_vistos)
                validos += parcial.validos
                erros_extracao += parcial.erros
                novos_cont += parcial.novos
                atualizados_cont += parcial.atualizados
                diagnosticos.append(parcial.diagnostico)

            if primeira_carga_pci:
                novos_cont += self._entregar_primeira_carga()

            # O diagnostico agregado tem precedencia: quando ele ja alertou
            # (varredura degradada ou cega), o aviso por fonte seria uma segunda
            # mensagem sobre o mesmo problema. O caso que importa e o inverso —
            # uma fonte morta enquanto o agregado parece um dia normal.
            alertou_agregado = self._mensagem_final(
                total_blocos_gran, validos, erros_extracao, novos_cont, atualizados_cont
            )
            self._alertar_fontes_doentes(diagnosticos, silenciar=alertou_agregado)
            self.logger.info("🏁 Ciclo finalizado.")

        except Exception as e:
            # Marca a falha: sem isso o main.py devolvia 0, o run_daily.sh
            # gravava o marker e o dia seguinte parecia saudavel.
            self.falhou = True
            self.logger.error(f"❌ Erro crítico durante o loop de execução: {e}", exc_info=True)
            self._notificar(
                f"⚠️ <b>Falha na varredura - {self.area_name}</b>\n\n"
                f"A varredura foi interrompida por um erro: {html.escape(str(e)[:300])}\n\n"
                f"<i>O bot vai tentar de novo na próxima hora.</i>"
            )

    def _preparar_primeira_carga(self) -> bool:
        """Liga o modo de coleta quando o PCI nunca rodou nesta area.

        Detectado pelo banco (zero linhas com fonte='pci'), sem flag em arquivo.
        No modo `individual` nao ha coleta: cada edital sai como card normal.
        """
        if not self.pci_scraper or self.db.contar_por_fonte("pci") > 0:
            return False

        if self.modo_primeira_carga == CARGA_INDIVIDUAL:
            self.logger.info(
                f"📦 Primeira carga do PCI em [{self.area_name}]: notificando individualmente."
            )
            return False

        self.logger.info(
            f"📦 Primeira carga do PCI em [{self.area_name}]: modo "
            f"{self.modo_primeira_carga!r}, acumulando em vez de notificar um a um."
        )
        self._coletor_carga = []
        return True

    def _entregar_primeira_carga(self) -> int:
        """Envia o resultado acumulado da primeira carga. Devolve quantos entraram."""
        coletados = self._coletor_carga or []
        self._coletor_carga = None
        if not coletados:
            return 0

        if self.modo_primeira_carga == CARGA_SILENCIOSA:
            self.logger.info(
                f"🤫 Primeira carga: {len(coletados)} edital(is) semeados sem notificar."
            )
            return 0

        por_uf: dict[str, list[dict]] = {}
        for item in coletados:
            por_uf.setdefault(item.get("uf") or "Outros", []).append(item)

        self.logger.info(
            f"📬 Primeira carga: {len(coletados)} edital(is) em {len(por_uf)} grupo(s) de UF."
        )
        self._notificar(
            f"📦 <b>{self.area_name}: acervo inicial</b>\n\n"
            f"Encontrei <b>{len(coletados)}</b> concursos com inscrição em aberto, "
            f"em <b>{len(por_uf)}</b> estados. Vou mandar um resumo por estado.\n\n"
            f"<i>A partir da próxima varredura você recebe um aviso por edital novo.</i>"
        )

        for uf in sorted(por_uf):
            itens = sorted(por_uf[uf], key=lambda i: i.get("nome", ""))
            linhas = []
            for item in itens:
                nome = html.escape(item.get("nome", "?"))
                prazo = item.get("data_fim_inscricao")
                sufixo = f" — até {html.escape(prazo)}" if prazo else ""
                linhas.append(f"• <a href='{item.get('link', '')}'>{nome}</a>{sufixo}")
            self._notificar(
                f"📍 <b>{uf}</b> — {len(itens)} concurso(s)\n\n" + "\n".join(linhas)
            )

        return len(coletados)

    def _varrer_nacional(self, ja_vistos: set[str]) -> ResultadoFonte:
        """Le a lista de concursos NACIONAIS do PCI e separa o que e da area.

        Esta e a fonte que existe por causa da Dataprev: nem o artigo do Gran
        nem os slugs de cargo a listaram enquanto as inscricoes estavam
        abertas. Ver o docstring de :mod:`src.scrapers.pci_nacional_scraper`.

        Custo: a listagem tem uma dezena de itens. So o que ainda NAO esta no
        banco — e que nao foi julgado fora da area nos ultimos
        ``DIAS_REJULGAR_DESCARTE`` dias — abre a noticia e gasta uma chamada de
        LLM. Em regime, isso e zero chamada por dia.
        """
        itens = self.nacional_scraper.capturar_concursos()
        diagnostico = self._avaliar_fonte(
            "pci_nacional",
            (f"{i['link']}|{i['status']}|{i['data_fim_inscricao']}" for i in itens),
        )

        validos = erros = novos = atualizados = 0
        descartes = memoria_json.carregar(ARQUIVO_DESCARTES)
        descartes_mudou = False
        url_indice = self.nacional_scraper.url

        for item in itens:
            # O mesmo edital pode ter chegado pelo slug de cargo nesta rodada.
            # Reprocessar so geraria um refresh silencioso a toa.
            if item["link"] in ja_vistos:
                continue

            if self.db.buscar_registro(item["nome"], link=item["link"], url_indice=url_indice):
                # Ja conhecido: prazo e fase vem da propria listagem, sem LLM.
                validos += 1
                resultado = self._decidir_e_notificar(item, url_indice=url_indice)
                novos += resultado == "novo"
                atualizados += resultado == "atualizado"
                continue

            if self._nacional_ja_descartado(descartes, item):
                continue

            self.nacional_scraper.detalhar(item)
            dados = self.ai.extrair_dados(self.nacional_scraper.bloco_para_ia(item))

            if dados.get("erro"):
                erros += 1
                continue

            if dados.get("ignorar"):
                self._marcar_descarte_nacional(descartes, item)
                descartes_mudou = True
                self.logger.info(
                    f"🧹 [NACIONAL] {item['nome']}: fora de [{self.area_name}]; "
                    f"nao reavalia por {DIAS_REJULGAR_DESCARTE} dias."
                )
                continue

            # A LLM decide UMA coisa: se o concurso e da area. Identidade e
            # calendario continuam vindo da listagem, que e fato datado e
            # estavel entre rodadas — deixar a LLM escolher o link e
            # exatamente o que duplica linha no banco.
            #
            # `nome` tambem fica com o da listagem, e nao so por estabilidade:
            # ele vem no formato "SIGLA - Nome por extenso", o mesmo das
            # paginas de cargo, que e para o que `mesma_entidade` foi ajustado.
            # A LLM devolve coisas como "DATAPREV - Concurso 2026", que casa
            # pior com uma linha vinda do Gran para o mesmo orgao.
            # So o `status` vem da LLM: e o texto do card no Telegram e nao
            # participa de identidade nem de deteccao de mudanca.
            item["status"] = dados.get("status") or item["status"]
            item["data_fim_inscricao"] = (
                item["data_fim_inscricao"] or dados.get("data_fim_inscricao")
            )
            item["fase"] = item["fase"] or sanitizar_fase(dados.get("fase"))
            item["data_referencia"] = dados.get("data_referencia")

            validos += 1
            resultado = self._decidir_e_notificar(item, url_indice=url_indice)
            novos += resultado == "novo"
            atualizados += resultado == "atualizado"

        # Em dry-run nao persiste o descarte, pela mesma razao que nao escreve
        # no banco: marcaria itens como ja julgados e a rodada real seguinte
        # pularia a avaliacao deles.
        if descartes_mudou and not self.dry_run:
            memoria_json.salvar(ARQUIVO_DESCARTES, self._podar_descartes(descartes))

        return ResultadoFonte(validos, erros, novos, atualizados, diagnostico)

    def _chave_descarte(self, item: dict) -> str:
        """Descarte e por area: o mesmo edital pode servir a TI e nao a Educacao."""
        return f"{self.area_slug}::{item.get('link', '')}"

    def _nacional_ja_descartado(self, descartes: dict, item: dict) -> bool:
        """Ja julgado fora da area, e sem nada novo desde entao?"""
        registro = descartes.get(self._chave_descarte(item))
        if not registro:
            return False

        # Prazo diferente pode ser edital novo do mesmo orgao: vale reavaliar.
        if registro.get("prazo") != item.get("data_fim_inscricao"):
            return False

        try:
            dias = (date.today() - date.fromisoformat(registro.get("em", ""))).days
        except (TypeError, ValueError):
            return False
        return 0 <= dias < DIAS_REJULGAR_DESCARTE

    def _marcar_descarte_nacional(self, descartes: dict, item: dict) -> None:
        descartes[self._chave_descarte(item)] = {
            "em": date.today().isoformat(),
            "prazo": item.get("data_fim_inscricao"),
            "nome": item.get("nome"),
        }

    @staticmethod
    def _podar_descartes(descartes: dict) -> dict:
        """Descarte antigo nao decide mais nada e nao pode crescer sem fim."""
        limite = date.today() - timedelta(days=DIAS_MANTER_DESCARTE)
        vivos = {}
        for chave, registro in descartes.items():
            try:
                if date.fromisoformat(registro.get("em", "")) >= limite:
                    vivos[chave] = registro
            except (TypeError, ValueError):
                continue          # registro corrompido morre na poda
        return vivos

    def _avaliar_fonte(self, fonte: str, assinaturas) -> saude_fontes.Diagnostico:
        """Registra a materia-prima desta fonte e devolve o diagnostico."""
        return saude_fontes.avaliar(
            self.area_slug, fonte, assinaturas, dias_parada=self.dias_fonte_parada
        )

    def _url_da_fonte(self, fonte: str) -> str:
        """URL que o alerta oferece pro Lucas abrir e conferir com o olho."""
        if fonte == "gran":
            return self.scraper.url
        if fonte == "pci_nacional" and self.nacional_scraper:
            return self.nacional_scraper.url
        return "https://www.pciconcursos.com.br/cargos/"

    def _alertar_fontes_doentes(self, diagnosticos, silenciar: bool = False) -> None:
        """Avisa quando UMA fonte adoece, mesmo com as outras saudaveis.

        Este e o alerta que faltava. O de cegueira era agregado —
        ``total_blocos == 0 and not self.pci_scraper`` — entao, depois que o
        PCI entrou como segunda fonte, o Gran podia devolver zero (ou devolver
        sempre a mesma coisa) para sempre sem ninguem perceber. Foi o que
        aconteceu: o alvo de TI esta congelado desde 12/06/2026.

        NAO marca ``self.falhou``, de proposito. Fonte vazia ou parada nao se
        conserta com retry: repetir de hora em hora so gastaria LLM nas outras
        fontes e nunca gravaria o marker do dia. O conserto e humano — trocar a
        URL do alvo — e por isso o alerta sai uma vez por dia, por fonte.

        Args:
            silenciar: ``True`` quando a mensagem final ja alertou sobre a
                varredura inteira. A condicao persiste, entao a fonte doente
                volta a ser cobrada amanha, sem duplicar aviso hoje.
        """
        if silenciar:
            return

        for diagnostico in diagnosticos:
            if diagnostico.saudavel:
                continue

            fonte = diagnostico.fonte
            url = self._url_da_fonte(fonte)

            if diagnostico.vazia:
                self.logger.warning(
                    f"🕳️ [{self.area_name}] fonte {fonte!r} nao devolveu nada nesta rodada."
                )
                self._alerta_uma_vez_por_dia(
                    f"fonte_vazia_{fonte}",
                    f"🕳️ <b>Fonte sem retorno - {self.area_name}</b>\n\n"
                    f"A fonte <b>{fonte}</b> não devolveu nenhum item nesta varredura. "
                    f"As outras seguiram normalmente, então a rodada não conta como falha "
                    f"— mas se repetir, é queda do site ou mudança de layout.\n\n"
                    f"🔗 <a href='{url}'>Abrir a fonte</a>"
                )
                continue

            self.logger.warning(
                f"🧊 [{self.area_name}] fonte {fonte!r} devolve conteudo identico ha "
                f"{diagnostico.dias_sem_mudanca} dias ({diagnostico.itens} itens)."
            )
            self._alerta_uma_vez_por_dia(
                f"fonte_parada_{fonte}",
                f"🧊 <b>Fonte parada - {self.area_name}</b>\n\n"
                f"A fonte <b>{fonte}</b> devolve exatamente o mesmo conteúdo há "
                f"<b>{diagnostico.dias_sem_mudanca} dias</b> "
                f"({diagnostico.itens} itens).\n\n"
                f"Nenhum concurso publicado nesse período pode chegar por ela. "
                f"Costuma ser página curada que o site parou de atualizar — o conserto "
                f"é trocar a URL do alvo, não esperar.\n\n"
                f"🔗 <a href='{url}'>Abrir a fonte</a>"
            )

    def _mensagem_final(
        self, total_blocos: int, validos: int, erros: int, novos: int, atualizados: int
    ) -> bool:
        """Decide entre alerta e heartbeat no fim da varredura da area.

        Returns:
            bool: ``True`` se enviou um alerta sobre a varredura inteira
            (degradada ou cega). Quem chama usa isso para nao empilhar o aviso
            por fonte em cima do mesmo problema.
        """
        # Erro de extracao acima do limite invalida o resultado do dia, mesmo
        # que alguns editais tenham passado. Antes isso saia como sucesso.
        base = validos + erros
        taxa_erro = (erros / base) if base else 0.0
        extracao_degradada = erros > 0 and taxa_erro >= LIMITE_ERRO_EXTRACAO

        # Degradado e checado ANTES de cegueira: 10 blocos dos quais 5 se
        # perderam na LLM nao e cegueira, e perda. Sao diagnosticos diferentes
        # e o alerta precisa dizer qual dos dois foi.
        if extracao_degradada:
            self.falhou = True
            self.logger.error(
                f"🚨 [{self.area_name}] perdeu {erros}/{base} blocos na extracao "
                f"({taxa_erro:.0%}); resultado do dia nao e confiavel."
            )
            self._notificar(
                f"🚨 <b>Varredura incompleta - {self.area_name}</b>\n\n"
                f"Perdi <b>{erros}</b> de <b>{base}</b> publicações na extração "
                f"({taxa_erro:.0%}). Pode ter escapado edital.\n\n"
                f"<i>Vou tentar de novo na próxima hora.</i>"
            )
            return True

        # Varredura cega = nao entregou NADA, nem valido nem perdido, e isso nao
        # se explica pela configuracao do alvo:
        # - 0 blocos brutos e nenhuma fonte alternativa: site fora, bloqueio ou layout mudou.
        # - 0 candidatos SEM keywords_include: pagina dedicada que sempre lista dezenas.
        # - 0 candidatos COM keywords_include: dia quieto e o caso NORMAL (heartbeat).
        sem_materia_prima = total_blocos == 0 and not self.pci_scraper
        varredura_cega = sem_materia_prima or (base == 0 and not self.keywords_include)

        if varredura_cega:
            self.falhou = True
            self.logger.warning(
                f"🚫 Nenhum concurso valido extraido para [{self.area_name}] "
                f"({total_blocos} bloco(s) brutos). Possivel falha de rede ou mudanca no site."
            )
            # Uma vez por dia: a falha marca `falhou`, entao o catch-up horario
            # roda de novo. Se o site mudou de layout, repetir o mesmo aviso a
            # cada hora so ensina o Lucas a ignorar alerta do bot.
            self._alerta_uma_vez_por_dia(
                "cegueira",
                f"⚠️ <b>Atenção - {self.area_name}</b>\n\n"
                f"Não consegui extrair nenhum concurso da página nesta varredura.\n"
                f"Costuma ser instabilidade do site (tente mais tarde) ou mudança no layout "
                f"(o monitor pode precisar de ajuste).\n\n"
                f"🔗 <a href='{self.scraper.url}'>Abrir a página manualmente</a>"
            )
            return True

        if erros:
            self.logger.warning(
                f"⚠️ [{self.area_name}]: {erros} bloco(s) perdidos na extracao "
                f"({taxa_erro:.0%}), abaixo do limite de alerta."
            )

        if novos or atualizados:
            self.logger.info(
                f"📊 Ciclo finalizado: {novos} novos e {atualizados} atualizações enviadas."
            )
            return False

        if validos == 0:
            self.logger.info(
                f"📭 Nenhum concurso de [{self.area_name}] entre os {total_blocos} blocos "
                "da pagina (alvo filtrado, dia quieto). Enviando heartbeat..."
            )
            self._notificar(
                f"✅ <b>Varredura Concluída</b>\n\n"
                f"📚 <b>Área:</b> {self.area_name}\n"
                f"🔍 Verifiquei <b>{total_blocos}</b> publicações e nenhuma é da sua área hoje.\n\n"
                f"🕒 <i>Próxima verificação agendada.</i>"
            )
            return False

        self.logger.info("📭 Nenhuma novidade relevante encontrada. Enviando status para o Telegram...")
        self._notificar(
            f"✅ <b>Varredura Concluída</b>\n\n"
            f"📚 <b>Área:</b> {self.area_name}\n"
            f"🔍 Analisei <b>{validos}</b> concursos e não encontrei nenhuma alteração "
            f"relevante desde a última consulta.\n\n"
            f"🕒 <i>Próxima verificação agendada.</i>"
        )
        return False

    def _alerta_uma_vez_por_dia(self, tipo: str, mensagem: str) -> None:
        """Envia o alerta no maximo uma vez por dia, por area e por tipo.

        Necessario porque o cron passou a rodar de hora em hora: sem isso, um
        problema estrutural (site mudou de layout) renderia ate 24 mensagens
        identicas no mesmo dia.
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] alerta {tipo!r} suprimido.")
            return

        marcador = os.path.join(LOG_DIR, f".alerta_{self.area_slug}_{tipo}")
        hoje = date.today().isoformat()
        try:
            if os.path.exists(marcador):
                with open(marcador, encoding="utf-8") as f:
                    if f.read().strip() == hoje:
                        self.logger.info(
                            f"🔁 Alerta {tipo!r} de [{self.area_name}] ja enviado hoje; nao repete."
                        )
                        return
        except OSError:
            pass  # marcador ilegivel nunca pode impedir o alerta

        self._notificar(mensagem)

        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(marcador, "w", encoding="utf-8") as f:
                f.write(hoje)
        except OSError as e:
            self.logger.warning(f"Nao consegui gravar o marcador de alerta {tipo!r}: {e}")

    def _notificar(self, mensagem: str, id_interno: int | None = None) -> None:
        """Envia (ou apenas registra, em dry-run) uma mensagem no Telegram."""
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] mensagem suprimida: {mensagem.splitlines()[0][:90]}")
            return
        if id_interno is not None:
            entregue = self.notifier.notificar_concurso(id_interno, mensagem)
        else:
            entregue = self.notifier.notificar(mensagem)
        if not entregue:
            self.falhou = True

    def _decidir_e_notificar(self, dados: dict, url_indice: str = "") -> str:
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
        url_indice = url_indice or self.scraper.url
        nome_raw = dados.get('nome', 'Nome não identificado')
        status_raw = dados.get('status', 'Status não detalhado')
        link = dados.get('link') or url_indice
        data_fim = dados.get('data_fim_inscricao')
        fase_nova = sanitizar_fase(dados.get('fase'))
        pci_id = dados.get('pci_id') or None
        fonte = dados.get('fonte') or None

        nome_esc = html.escape(nome_raw)
        status_esc = html.escape(status_raw)
        hash_novo = status_fingerprint(status_raw)

        def salvar(fase_para_gravar):
            """Persiste este edital. Em dry-run nao escreve nada.

            Escrever em dry-run seria pior que inutil: marcaria os editais como
            ja vistos e a rodada real seguinte nao notificaria nada.
            """
            if self.dry_run:
                return 0
            return self.db.atualizar_concurso(
                nome_raw, status_raw, link,
                url_indice=url_indice,
                status_hash=hash_novo,
                data_fim_inscricao=data_fim,
                fase=fase_para_gravar,
                fonte=fonte,
                pci_id=pci_id,
            )

        registro = self.db.buscar_registro(
            nome_raw, link=link, url_indice=url_indice, pci_id=pci_id or ""
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
                salvar(fase_nova)
                return "skip"

            id_interno = salvar(fase_nova)

            # Primeira carga em modo agrupado: acumula pra sair como resumo por
            # UF no fim da varredura, em vez de um ping por edital.
            if self._coletor_carga is not None:
                self._coletor_carga.append({
                    "nome": nome_raw,
                    "link": link,
                    "uf": dados.get("uf"),
                    "data_fim_inscricao": data_fim,
                })
                self.logger.info(f"📥 [CARGA] {nome_raw} acumulado para o resumo.")
                return "skip"

            self.logger.info(f"✨ [NOVO] {nome_raw} detectado pela primeira vez.")
            msg = (
                f"<b>🆕 NOVO CONCURSO - {self.area_name}</b>\n\n"
                f"🏛 <b>Instituição:</b> {nome_esc}\n"
                f"📝 <b>Status:</b> {status_esc}\n"
                + (f"📊 <b>Fase:</b> {fase_label(fase_nova)}\n" if fase_nova else "")
                + (f"📅 <b>Inscrições até:</b> {html.escape(data_fim)}\n" if data_fim else "")
                + f"\n🔗 <a href='{link}'>Clique aqui para ver os detalhes</a>"
            )
            self._notificar(msg, id_interno=id_interno)
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
            salvar(fase_nova)
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
            salvar(fase_mais_avancada(fase_antiga, fase_nova))
            return "skip"

        # --- Caso C: transicao real (fase avancou e/ou data mudou) ---
        fase_final = fase_mais_avancada(fase_antiga, fase_nova)
        estado = registro.get('estado_usuario', 'ativo')
        if estado != 'seguindo' and inativo:
            self.logger.info(
                f"🔕 [TRANSICAO+INATIVO] {nome_raw}: avanco real mas concurso inativo; atualiza silencioso."
            )
            salvar(fase_final)
            return "skip"

        self.logger.info(
            f"🔔 [TRANSICAO] {nome_raw}: {fase_label(fase_antiga)} → {fase_label(fase_nova)} "
            f"(data_mudou={data_mudou})."
        )
        id_interno = salvar(fase_final)
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
        self._notificar(msg, id_interno=id_interno)
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
        # Sem log aqui: __del__ roda em ordem nao-deterministica no shutdown do
        # interpretador, e logar de dentro dele produzia as tres linhas
        # "🔌 Conexão encerrada" no rodape de todo log, sem informar nada.
        if hasattr(self, 'db'):
            self.db.fechar_conexao()

    def _passa_filtro_palavras(self, bloco_html: str) -> bool:
        """Filtro textual barato antes da chamada da IA.

        Roda sobre o TEXTO VISIVEL, nao sobre o HTML cru. Casar substring no
        HTML tinha dois defeitos serios:

        - `keywords_exclude` derrubava edital legitimo por causa de palavra em
          sidebar, link de "posts relacionados", `alt` de imagem ou nome de
          classe CSS. Um edital de TI sumia porque a barra lateral citava artes.
        - `keywords_include=["ti", ...]` era inocuo, porque "ti" casa dentro de
          "notícia", "gestão", "Justiça" e de meia duzia de atributos HTML.

        Com o texto visivel os dois lados passam a olhar o que o leitor le.
        """
        texto = self._texto_visivel(bloco_html).lower()

        if self.keywords_include and not any(keyword in texto for keyword in self.keywords_include):
            return False

        if self.keywords_exclude and any(keyword in texto for keyword in self.keywords_exclude):
            return False

        return True

    @staticmethod
    def _texto_visivel(bloco_html: str) -> str:
        """Texto do EDITAL: sem marcacao, sem atributos e sem conteudo lateral.

        Descartar o lateral e o ponto principal. So tirar as tags nao bastava:
        o texto do link de "posts relacionados" tambem e visivel, e era ele que
        derrubava um edital de TI por citar artes numa chamada de rodape.
        """
        if not bloco_html:
            return ""
        try:
            soup = BeautifulSoup(bloco_html, "html.parser")
            for tag in soup(["script", "style", "nav", "aside", "footer", "form"]):
                tag.decompose()
            for tag in soup.find_all(attrs={"class": True}):
                classes = " ".join(tag.get("class", [])).lower()
                if any(m in classes for m in _CLASSES_LATERAIS):
                    tag.decompose()
            return soup.get_text(" ", strip=True)
        except Exception:
            return bloco_html
