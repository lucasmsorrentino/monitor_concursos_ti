# Diagrama de Classes — Monitor de Concursos

```mermaid
classDiagram
    direction LR

    class main {
        +build_bots(dry_run: bool) List~ConcursoBot~
        +main(argv) int
    }

    class MultiAreaRunner {
        -bots: List~ConcursoBot~
        -logger: Logger
        +executar() bool
    }

    class ConcursoBot {
        -area_slug: str
        -area_name: str
        -scraper: GranScraper
        -mcp_scraper: PciMcpScraper
        -pci_scraper: PciScraper
        -nacional_scraper: PciNacionalScraper
        -politica: Politica
        -db: DatabaseManager
        -ai: IntelligenceUnit
        -notifier: TelegramNotifier
        +falhou: bool
        +executar() void
        -_avaliar_elegibilidade(dados: dict, nome: str, registro: dict) tuple
        -_varrer_nacional(ja_vistos: set) ResultadoFonte
        -_decidir_e_notificar(dados: dict, url_indice: str) str
        -_alertar_fontes_doentes(diagnosticos: list, silenciar: bool) void
        -_politica_de(config: dict)$ Politica
        -_mensagem_final(...) bool
    }

    class BaseScraper {
        <<abstract>>
        #url: str
        #headers: dict
        #tentativas: int
        +capturar_concursos()* List
        +get_html(url: str) str
    }

    class GranScraper {
        +capturar_concursos() List~str~
    }

    class PciMcpScraper {
        -termos: List~str~
        +capturar_concursos() List~dict~
        -_chamar(termo: str) dict
    }

    class PciScraper {
        -slugs: List~str~
        +capturar_concursos() List~dict~
        +enriquecer(item: dict) dict
    }

    class PciNacionalScraper {
        +capturar_concursos() List~dict~
        +detalhar(item: dict) dict
        +bloco_para_ia(item: dict)$ str
    }

    class pci_comum {
        <<module>>
        +inferir_fase(titulo: str) str
        +extrair_data_fim(texto: str) str
        +para_texto(html: str) str
    }

    class elegibilidade {
        <<module>>
        +SELO_NAO_VERIFICADO: str
        +decidir(c: Candidato, p: Politica) Decisao
    }

    class Candidato {
        <<dataclass>>
        +uf: str
        +regiao: str
        +esfera: str
        +teto: float
        +cargos_total: int
        +seguindo: bool
    }

    class Politica {
        <<dataclass>>
        +modo: str
        +corte_fora_sul: float
        +ufs_sem_corte: tuple
        +esferas_sem_corte: tuple
        +cargos_total_inflado: int
    }

    class Decisao {
        <<dataclass>>
        +entra: bool
        +motivo: str
        +selo: str
    }

    class salario {
        <<module>>
        +teto_de(texto: str) float
    }

    class esfera {
        <<module>>
        +esfera_de(nome: str) str
    }

    class resumo_filtrados {
        <<module>>
        +montar(linhas: list, area_nome: str, limite: int) str
        +marcador_da_semana(hoje: date) str
    }

    class IntelligenceUnit {
        -llm_json: LLM
        -llm_text: LLM
        -chain_extracao: RunnableSequence
        +extrair_dados(bloco_html: str) dict
        -_detect_backend(model_name: str)$ str
    }

    class fases {
        <<module>>
        +FASES_ORDEM: tuple
        +sanitizar_fase(valor) str
        +fase_avancou(antiga, nova) bool
        +fase_mais_avancada(a, b) str
        +label(fase) str
    }

    class saude_fontes {
        <<module>>
        +avaliar(area, fonte, assinaturas, dias_parada) Diagnostico
    }

    class text {
        <<module>>
        +status_fingerprint(texto: str) str
        +mesma_entidade(nome_a: str, nome_b: str) bool
        +extrair_uf(texto: str) str
    }

    class DatabaseManager {
        -db_path: str
        -area: str
        -conn: Connection
        +buscar_registro(nome, link, url_indice, pci_id) dict
        +atualizar_concurso(nome, status, link, ..., fonte, pci_id, uf, regiao, esfera, cargos_total, salario_teto, elegibilidade, motivo_filtro) int
        +atualizar_estado_usuario(id, estado) bool
        +listar_filtrados(desde: str) list
        +contar_por_fonte(fonte: str) int
        +fechar_conexao() void
    }

    class TelegramNotifier {
        -token: str
        -chat_ids: List~str~
        -dry_run: bool
        +notificar(mensagem: str) bool
        +notificar_concurso(id_interno: int, msg: str) bool
    }

    class TelegramCallbackProcessor {
        -db: DatabaseManager
        +processar_pendentes() int
    }

    main --> MultiAreaRunner : instancia via config/loader
    MultiAreaRunner --> ConcursoBot : executa N bots em sequencia
    ConcursoBot --> TelegramCallbackProcessor : aplica cliques pendentes (⭐/❌)
    ConcursoBot --> PciMcpScraper : Porta do PCI (padrao, MCP do PCI)
    ConcursoBot --> GranScraper : Porta do Gran (blocos HTML + LLM)
    ConcursoBot --> PciScraper : Porta de reserva (por slug de cargo)
    ConcursoBot --> PciNacionalScraper : Porta de reserva (lista nacional)
    ConcursoBot --> elegibilidade : decide notificar ou silenciar (item da porta MCP)
    ConcursoBot --> Politica : uma por area, montada da config
    elegibilidade --> Candidato : avalia
    elegibilidade --> Decisao : devolve entra + motivo + selo
    ConcursoBot --> salario : teto do texto na montagem do Candidato
    ConcursoBot --> esfera : classifica o orgao na montagem do Candidato
    ConcursoBot --> resumo_filtrados : resumo semanal dos filtrados (uma vez por semana)
    resumo_filtrados --> DatabaseManager : le listar_filtrados
    ConcursoBot --> IntelligenceUnit : extrai JSON (Gran + Nacional novo)
    ConcursoBot --> fases : compara fase antiga vs nova
    ConcursoBot --> saude_fontes : diagnostica porta vazia/congelada (MCP entra como pci_mcp)
    ConcursoBot --> DatabaseManager : persiste estado (schema v6)
    ConcursoBot --> TelegramNotifier : envia alertas e cards interativos
    TelegramCallbackProcessor --> DatabaseManager : grava estado_usuario
    DatabaseManager --> text : deduplica entre fontes (mesma_entidade)
    GranScraper --|> BaseScraper : herda
    PciMcpScraper --|> BaseScraper : herda
    PciScraper --|> BaseScraper : herda
    PciNacionalScraper --|> BaseScraper : herda
    PciScraper --> pci_comum : usa helpers de data/fase
    PciNacionalScraper --> pci_comum : usa helpers de data/fase
```

> O agendamento é externo: Windows Task Scheduler (`scripts/install_schedule.ps1`) ou cron horário com catch-up + `@reboot` no Linux (`scripts/install_schedule.sh`). As regras da elegibilidade (as nove da tabela, com precedência) estão na SPEC-001, seção 4.2, e nas ADRs `docs/adr/0001` (a porta do MCP) e `docs/adr/0002` (o teto como evidência).
