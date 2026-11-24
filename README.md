# 🎯 Monitor de Concursos (TI + Multi-Área) — Pipeline Híbrido Determinístico e LLM

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![SQLite Schema v6](https://img.shields.io/badge/SQLite-Schema%20v6-003B57?logo=sqlite&logoColor=white)
![LangChain + Multi-LLM](https://img.shields.io/badge/LLM-Ollama%20%7C%20LiteLLM%20%7C%20Claude%20CLI-10A37F)
![Telegram Bot API](https://img.shields.io/badge/Telegram-Interactive%20Bot-26A5E4?logo=telegram&logoColor=white)
![Tests](https://img.shields.io/badge/pytest-539%20passed-2EA44F?logo=pytest&logoColor=white)

> **Nota:** a versão em inglês deste README foi removida em 24/11/2026. Manter duas línguas coerentes
> custava mais do que valia (a inglesa já estava defasada) e este texto em português passa a ser a
> única versão. O texto antigo continua no histórico do git.

Sistema automatizado de engenharia de dados e LLM para monitorar, classificar e notificar atualizações
de concursos públicos em múltiplas áreas (**Tecnologia da Informação**, **Educação**, **Sociologia,
Artes e Licenciaturas**), com roteamento independente de mensagens por chat do Telegram.

Em vez de depender apenas de seletores CSS frágeis ou gastar chamadas de LLM em cada linha de HTML, o
sistema adota uma **arquitetura híbrida determinística + LLM**: o parsing determinístico processa
listagens estruturadas de alto volume (mais de 1.000 editais por rodada em milissegundos, a custo zero
de LLM), enquanto a LLM (via Ollama, LiteLLM ou Claude Code CLI) entra apenas onde o texto em prosa
exige extração semântica ou classificação de área. Todas as portas convergem para uma única **máquina
de estados de fases** com deduplicação cruzada de órgãos, **elegibilidade por área** e autodiagnóstico
de saúde por fonte.

> **Documentos que mandam:** a especificação normativa da fase atual é
> [`docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md`](docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md),
> com as decisões registradas nas ADRs de [`docs/adr/`](docs/adr/). O
> `PLANO_EVOLUCAO_AGENTICA.md` é plano antigo, não normativo — onde ele discordar da SPEC, vale a SPEC.
> Os termos (*porta*, *rodada*, *teto do concurso*, *elegibilidade*...) são os do `GLOSSARIO.md`.

---

## ✨ Destaques de Engenharia

### Ingestão com quatro portas de entrada

| # | Porta | Papel |
| :--- | :--- | :--- |
| 1 | **Servidor MCP do PCI (`PciMcpScraper`)** | **A porta padrão do PCI.** Chama a ferramenta `buscar_por_cargo` do servidor MCP oficial (`https://mcp.pciconcursos.com.br/mcp`, JSON-RPC 2.0 por HTTP POST, sem autenticação), que devolve o dado já estruturado — região, teto do concurso, total de cargos e datas de inscrição já calculadas. Uma chamada por termo da área, união por `id`, **sem LLM**. |
| 2 | **Blog do Gran (`GranScraper`)** | Fatiamento em blocos `<h3>` + pré-filtro por texto visível + extração semântica via LLM — cobre grandes concursos estaduais e federais. |
| 3 | **PCI por cargo (`PciScraper`)** | **Reserva** (desligada por padrão): parsing 100% determinístico em `/cargos/<slug>`, com enriquecimento da data de inscrição na notícia, só para itens novos. |
| 4 | **PCI nacional (`PciNacionalScraper`)** | **Reserva** (desligada por padrão): `/concursos/nacional/`, captura estatais federais (Dataprev, Transpetro, Correios) e usa 1 chamada de LLM apenas para itens inéditos. |

> **Por que quatro portas:** o PCI publicou um servidor MCP oficial que devolve o que as duas portas
> de HTML liam raspando página — e mais o que elas nunca tiveram (região, teto, total de cargos). As
> duas portas de HTML ficam no repo como **reserva, desligáveis por configuração** (`pci_slugs`,
> `pci_nacional`) e religáveis do mesmo jeito, se o MCP sair do ar ou mudar de contrato. A decisão
> está na [ADR-0001 — o servidor MCP é a única porta do PCI](docs/adr/0001-mcp-como-unica-porta-do-pci.md).

### Máquina de estados por fase estruturada (anti-flapping)

Em vez de comparar texto livre (que a LLM reescreve a cada leitura, gerando falsos positivos), cada
concurso é classificado num vocabulário fechado e ordenado:
`previsto → banca_definida → edital_publicado → inscricoes_abertas → inscricoes_encerradas → concluido`.
Apenas **avanço real de fase** ou **mudança na janela de inscrição** dispara alerta `🔔 ATUALIZAÇÃO`.
Regressões acidentais da LLM são absorvidas (`fase_mais_avancada`).

### Elegibilidade por área: o que o bot silencia

A **elegibilidade** é a decisão do bot sobre notificar ou não um concurso, com o motivo gravado no
banco. Hoje ela só é avaliada na área TI e só para itens da porta do MCP — a única que traz região,
teto e total de cargos; itens do Gran e das portas de reserva entram como sempre entraram. A limitação
central do dado: **o PCI publica o teto do concurso, não o salário do cargo** — num edital com 86
cargos, o teto costuma ser de procurador ou médico. A decisão usa as duas evidências que o dado
sustenta (teto abaixo do corte; municipal inflado) e isenta a esfera federal do corte. Regras,
motivos e precedência estão na tabela abaixo e na
[ADR-0002 — a elegibilidade usa o teto do concurso](docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md).

| # | Condição (a primeira que casa vence) | Resultado | Motivo |
| :-: | :--- | :--- | :--- |
| 0 | usuário segue o concurso (⭐) | entra | `seguindo` |
| 1 | filtro da área diferente de `ativo` | entra | `filtro_desligado` |
| 2 | UF e região desconhecidas | entra, com selo | `nao_verificado` |
| 3 | UF é PR/SC/RS, ou região é `SUL` | entra | `sul` |
| 4 | esfera federal | entra | `federal` |
| 5 | teto conhecido e menor que o corte | **filtrado** | `abaixo_do_corte` |
| 6 | municipal fora do Sul com muitos cargos | **filtrado** | `municipal_inflado` |
| 7 | teto desconhecido | entra, com selo | `sem_evidencia` |
| 8 | resto | entra | `acima_do_corte` |

- O selo das regras 2 e 7 é `⚠️ salario nao verificado` e aparece no card.
- **Fail-open:** teto ilegível, chamada que falhou ou UF desconhecida fazem o concurso **entrar,
  marcado** — erro nunca vira silêncio. Só se descarta com evidência positiva.
- A regra 0 nunca se contorna: o que o Lucas marcou com estrela chega sempre. A elegibilidade é
  **coluna separada** de `estado_usuario` (aquela é do bot; esta, do Lucas) — as duas não se misturam.
- Com `resumo_filtrados: "semanal"`, uma vez por semana por área sai a lista do que foi filtrado nos
  últimos 7 dias, com a contagem por motivo. A especificação completa (contrato da função, as oito
  chaves de configuração e as regras R-01 a R-22) é a
  [SPEC-001, seções 3 e 4](docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md) — este README não a repete.

### Resolução e fusão de entidades entre fontes (`mesma_entidade`)

Um mesmo concurso capturado pelo Gran (`"Prefeitura de Ponta Grossa - PR"`) e pelo PCI
(`"Concurso Prefeitura Ponta Grossa"`) é reconciliado por tokens discriminantes e validação de UF
(impedindo colisões falsas como *"Ponta Grossa"* vs. *"Ponta Porã"*). O `id` do MCP é o mesmo número
de notícia que virava `pci_id` nas páginas de HTML, então a deduplicação atravessa a troca de porta
sem migração de dado. Duplicatas são fundidas no SQLite preservando a preferência do usuário
(`⭐ Seguindo` > `❌ Ignorado` > `Ativo`).

### Observabilidade e saúde por porta (`saude_fontes`)

Detecta individualmente quando uma porta fica **vazia (`🕳️`)** ou **congelada (`🧊`)** devolvendo o
mesmo conteúdo visível por mais de `dias_fonte_parada` dias (padrão: 21), mesmo quando as outras
continuam trazendo novidades — a porta do MCP entra nesse acompanhamento como `pci_mcp`. Detecta
**extração degradada (`🚨`)** quando ≥ 20% dos blocos falham na LLM e inclui um
**Dead-Man's-Switch (`⏰`)** no agendador Linux caso o bot fique mais de `MONITOR_MAX_DIAS_SEM_RODAR`
dias sem concluir uma rodada.

### Interatividade no Telegram

Botões inline em cada notificação (`⭐ Seguir` / `❌ Não tenho interesse`) processados em lote via
`getUpdates` no início de cada rodada, sem exigir servidor web ou webhook exposto.

---

## 🏛️ Arquitetura — Quatro Portas, Um Caminho de Decisão

| | 1. Gran blog (`GranScraper`) | 2. PCI MCP (`PciMcpScraper`) — **padrão** | 3. PCI por cargo (`PciScraper`) — reserva | 4. PCI nacional (`PciNacionalScraper`) — reserva |
|---|---|---|---|---|
| **Acesso** | 1 página de blog por área | `POST https://mcp.pciconcursos.com.br/mcp` (JSON-RPC 2.0; resposta em JSON ou SSE) | `/cargos/<slug>` (N slugs por área) | `/concursos/nacional/` |
| **Formato** | prosa em HTML | estruturado (JSON do servidor) | lista estruturada (`ul.link-d` + `ul.link-i`) | cartões estruturados (`div.ca`) |
| **Usa LLM?** | **Sim** (1 chamada por bloco pré-filtrado) | **Não** (100% determinístico) | **Não** (100% determinístico) | **Só para item NOVO** (julga aderência à área) |
| **Volume típico** | ~45 blocos | 1 chamada por termo (hoje ≤ 69 resultados por termo de TI; o servidor corta em 200) | 50 a 1.100+ itens por área | ~4 a 15 itens |
| **Cobertura** | grandes estaduais/federais | tudo que a busca por cargo cobre (municipais, conselhos, estatais, nacionais) | municipal, autarquias, conselhos | **estatal federal** (Dataprev, Transpetro) |
| **Chave de dedup** | `link` canônico + `(area, nome)` | `id` do MCP (= `pci_id`) | `pci_id` (`nXXXXXX`) + `link` | `link` (o mesmo das outras portas do PCI) |

### Fluxo de dados

```text
main.py (opcional --dry-run | carrega MONITOR_ENV_FILE ou .env)
  │
  ▼
MultiAreaRunner ──▶ roda N ConcursoBots em sequência (TI, EDUCACAO, SOCIOLOGIA_ARTES...)
  │
  ▼
ConcursoBot (orquestrador por área)
  │
  ├──▶ 1. TelegramCallbackProcessor.processar_pendentes()
  │         Aplica cliques pendentes (⭐ Seguir / ❌ Ignorar) no SQLite antes de varrer
  │
  ├──▶ 2. Ingestão por porta:
  │      ├─▶ [Porta 1: PciMcpScraper] ──▶ buscar_por_cargo por termo (JSON-RPC) ──▶ união por id
  │      ├─▶ [Porta 2: GranScraper]   ──▶ blocos <h3> ──▶ filtro de palavras ──▶ IntelligenceUnit (LLM)
  │      ├─▶ [Porta 3: PciScraper]    ──▶ /cargos/<slug> (reserva; enriquecer() só em item novo)
  │      └─▶ [Porta 4: PciNacional]   ──▶ /concursos/nacional/ (reserva; cache 30d + LLM só no novo)
  │
  ├──▶ 3. Elegibilidade (só itens da porta do MCP):
  │         montar Candidato (salario.teto_de + esfera.esfera_de) ──▶ elegibilidade.decidir()
  │         filtrado ──▶ grava `elegibilidade='filtrado'` + motivo e NÃO notifica
  │         elegível ──▶ segue para a matriz de decisão
  │
  ├──▶ 4. DatabaseManager.buscar_registro(nome, link, url_indice, pci_id)
  │         Resolução de identidade: pci_id ──▶ link específico ──▶ (area, nome) NOCASE ──▶ mesma_entidade()
  │
  ├──▶ 5. ConcursoBot._decidir_e_notificar(dados)
  │         Matriz de decisão determinística por fase (previsto..concluido), prazo e listagem morta
  │
  ├──▶ 6. TelegramNotifier (cards individuais com botões ⭐/❌ ou resumo por UF na 1ª carga do PCI)
  │
  └──▶ 7. Fechamento:
         diagnóstico operacional (heartbeat ✅, degradado 🚨, cego ⚠️, vazia 🕳️, congelada 🧊)
         + resumo semanal dos filtrados (🔁, uma vez por semana por área)
```

O diagrama de classes está em [`CLASS_DIAGRAM.md`](CLASS_DIAGRAM.md).

---

## 🧠 Matriz de Decisão e Notificação (`ConcursoBot._decidir_e_notificar`)

A elegibilidade (seção acima) roda **antes** desta matriz e só para itens da porta do MCP; um item
filtrado nunca chega à matriz e nunca notifica.

| Situação | Ação do Sistema |
|---|---|
| Concurso inédito, ativo ou previsto | Envia card **🆕 NOVO CONCURSO** (com fase, prazo e botões ⭐/❌) e salva no banco |
| Concurso inédito na 1ª carga do PCI (`pci_primeira_carga="resumo_uf"`) | Acumula e envia **📦 Resumo agrupado por Estado (UF)** para evitar flood inicial |
| Concurso inédito com inscrição já encerrada ou listagem morta (`data_referencia` passada) | Salva em silêncio no banco (sem notificar) |
| **Fase avançou** (ex.: `banca_definida` → `edital_publicado`) | Envia card **🔔 ATUALIZAÇÃO** mostrando a transição `Fase Antiga → Fase Nova` |
| **Prazo de inscrição mudou** (nova data válida diferente da anterior) | Envia card **🔔 ATUALIZAÇÃO** destacando o novo prazo |
| LLM apenas reescreveu o resumo ou regrediu a fase | Atualiza em silêncio preservando a `fase_mais_avancada` |
| Concurso marcado com **⭐ Seguir** pelo usuário | Notifica qualquer transição real, mesmo após o encerramento das inscrições |
| Concurso marcado com **❌ Não tenho interesse** | Ignora completamente em todas as rodadas futuras |
| Perda de ≥ 20% dos blocos na extração via IA | Dispara alerta **🚨 Extração Degradada** e retorna exit code `1` (para retry horário) |
| Varredura sem candidatos válidos (em alvo não filtrado) | Dispara alerta **⚠️ Varredura Cega** (rate-limited a 1x/dia) |
| Uma porta específica não retornou itens ou está congelada há >21 dias | Dispara alerta **🕳️ Porta sem retorno** ou **🧊 Porta parada** apontando a URL exata |
| Rodada concluída sem novidades e portas saudáveis | Envia heartbeat **✅ Varredura Concluída** (1x por dia por área) |

---

## 📂 Estrutura do Projeto

```text
monitor_concursos_ti/
├── main.py                           # Ponto de entrada de rodada única (--dry-run e MONITOR_ENV_FILE)
├── requirements.txt                  # Dependências de produção
├── requirements-dev.txt              # Dependências de teste (pytest, pytest-mock, pytest-cov)
├── .env.example                      # Template completo de configuração (multi-área, portas PCI, LLMs)
├── CLASS_DIAGRAM.md                  # Diagrama de classes Mermaid
├── CLAUDE.md                         # Referência arquitetural e operacional (contrato de trabalho)
├── docs/
│   ├── DEPLOY-PCI-MCP.md             # Roteiro de deploy da fase MCP + filtro salarial no notebook
│   ├── adr/                          # Decisões de arquitetura (0001: MCP; 0002: elegibilidade; ...)
│   └── specs/                        # Specs normativas (SPEC-001: PCI via MCP e elegibilidade)
├── config/
│   └── loader.py                     # Carregador e validador de alvos (MONITOR_TARGETS_JSON + fallback)
├── data/
│   ├── concursos.db                  # SQLite (schema v6, migração automática e aditiva v1→v6)
│   ├── saude_fontes.json             # Digests por porta e contadores de dias sem mudança
│   ├── pci_nacional_descartados.json # Memoização de descartes nacionais fora da área (TTL 30 dias)
│   └── telegram_offset.json          # Offset de polling dos callback_query do Telegram
├── logs/
│   └── bot_concursos.log             # Logs rotativos + marcadores diários de execução/alerta
├── scripts/
│   ├── install_schedule.ps1          # Instalador no Task Scheduler do Windows (com StartWhenAvailable)
│   ├── run_daily.bat                 # Wrapper de execução diária no Windows
│   ├── install_schedule.sh           # Instalador de cron horário + @reboot no Linux
│   ├── run_daily.sh                  # Wrapper Linux: 1 sucesso/dia + catch-up horário + dead-man's-switch
│   ├── diagnostico_producao.sh       # Coleta somente-leitura de evidência dos últimos 30 dias
│   ├── export_known.py               # Exporta os concursos ativos do SQLite para Markdown (auditoria)
│   └── dedupe_db.py                  # Utilitário pontual de limpeza de duplicatas históricas
├── src/
│   ├── core/
│   │   ├── bot.py                    # ConcursoBot — orquestrador multiporta, matriz de decisão e saúde
│   │   ├── elegibilidade.py          # Candidato, Politica, Decisao e decidir() — as nove regras
│   │   ├── multi_area_runner.py      # MultiAreaRunner — roda os bots em sequência e agrega falha
│   │   └── resumo_filtrados.py       # Resumo semanal dos filtrados (texto + marcador de semana ISO)
│   ├── scrapers/
│   │   ├── base_scraper.py           # BaseScraper — ABC com retry HTTP, backoff e User-Agent
│   │   ├── gran_scraper.py           # GranScraper — fatiador de blocos <h3> dos artigos do Gran
│   │   ├── pci_mcp_scraper.py        # PciMcpScraper — porta padrão do PCI (servidor MCP oficial)
│   │   ├── pci_scraper.py            # PciScraper — parser determinístico de /cargos/<slug> (reserva)
│   │   ├── pci_nacional_scraper.py   # PciNacionalScraper — parser de /concursos/nacional/ (reserva)
│   │   └── pci_comum.py              # Helpers determinísticos de fase e datas compartilhados
│   ├── intelligence/
│   │   ├── langchain_unit.py         # IntelligenceUnit — HTML → JSON sobre 3 backends de LLM
│   │   └── claude_cli_backend.py     # ClaudeCliLLM — wrapper LangChain do `claude -p` via stdin
│   ├── database/
│   │   └── manager.py                # DatabaseManager — schema v6, resolução em 4 níveis e fusão
│   ├── notifiers/
│   │   ├── telegram.py               # TelegramNotifier — entrega resiliente com botões e dry-run
│   │   └── telegram_callbacks.py     # TelegramCallbackProcessor — aplica cliques ⭐ Seguir / ❌ Ignorar
│   └── utils/
│       ├── esfera.py                 # esfera_de() — classificação do órgão (federal, municipal, ...)
│       ├── fases.py                  # Vocabulário controlado de 6 fases e comparação anti-regressão
│       ├── salario.py                # teto_de() — maior valor em reais do texto, com banda de sanidade
│       ├── saude_fontes.py           # Diagnóstico de porta vazia (🕳️) e congelada (🧊)
│       ├── memoria_json.py           # Persistência atômica de caches JSON em data/
│       ├── text.py                   # mesma_entidade(), extrair_uf(), status_fingerprint() e normalização
│       └── logger.py                 # RotatingFileHandler + FormatterSemSegredos (token nunca no log)
└── tests/                            # Suíte com 539 testes (100% offline; nenhuma rede, nenhuma LLM)
```

---

## 🛠️ Configuração, Execução e Testes

```bash
git clone https://github.com/lucasmsorrentino/monitor_concursos_ti.git
cd monitor_concursos_ti

python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

> **Atenção:** `MONITOR_TARGETS_JSON` deve ficar em **uma única linha** no arquivo de configuração
> (limitação do `python-dotenv` — quebrar a linha faz o carregamento falhar em silêncio e cair no modo
> legado de área única).

### Seleção de backend de LLM (`LLM_MODEL`)

| Formato de `LLM_MODEL` | Backend | Custo marginal | Observação |
|---|---|---|---|
| `llama3.1`, `qwen2.5:7b` (sem `/`) | **Ollama local** | Zero | Requer servidor Ollama local (`OLLAMA_BASE_URL`) |
| `zai/glm-5.3-flash`, `anthropic/claude-...`, `openai/gpt-4o-mini` | **LiteLLM (API)** | Por token | Requer chave do provedor no ambiente (`ZAI_API_KEY`) |
| `claude-cli:haiku` (`sonnet` / `opus`) | **Claude Code CLI** | Zero (assinatura) | Usa o binário `claude` autenticado no `PATH` |

### Configuração por área (`MONITOR_TARGETS_JSON`)

Exemplo com a área TI na configuração da fase atual (porta do MCP + filtro salarial ativo) e as
outras duas áreas como estão — **sem nenhuma das chaves novas**, que são exclusivas da TI
([SPEC-001, seção 3.6](docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md)):

```ini
MONITOR_TARGETS_JSON=[{"area": "TI", "display_name": "Tecnologia da Informacao", "url": "https://blog.grancursosonline.com.br/concursos-ti/", "chat_ids": ["SEU_CHAT_ID"], "keywords_include": ["ti", "tecnologia", "informacao", "sistemas"], "keywords_exclude": ["sociologia", "artes", "pedagogia"], "pci_mcp": true, "pci_mcp_cargos": ["analista de sistemas", "tecnologia da informacao", "desenvolvedor", "programador", "tecnico em informatica", "informatica", "analista de dados", "ciencia da computacao", "banco de dados", "redes", "suporte tecnico", "computacao", "software"], "filtro_salarial": "ativo", "corte_fora_sul": 10000, "resumo_filtrados": "semanal"}, {"area": "EDUCACAO", "display_name": "Educacao", "url": "https://blog.grancursosonline.com.br/concursos-educacao/", "chat_ids": ["CHAT_ID_EDUCACAO"], "keywords_include": [], "keywords_exclude": [], "pci_slugs": ["professor", "pedagogo", "professor-de-educacao-basica", "supervisor-escolar", "orientador-educacional"], "pci_primeira_carga": "resumo_uf"}, {"area": "SOCIOLOGIA_ARTES", "display_name": "Sociologia, Artes e Licenciaturas", "url": "https://blog.grancursosonline.com.br/concursos-abertos/", "chat_ids": ["CHAT_ID_EDUCACAO"], "keywords_include": ["sociologia", "antropologia", "artes", "licenciatura"], "keywords_exclude": [], "pci_slugs": ["professor-de-artes", "professor-de-sociologia", "professor-de-filosofia", "arte-educador"], "pci_primeira_carga": "resumo_uf"}]
```

Chaves novas da TI: `pci_mcp` liga a porta do MCP; `pci_mcp_cargos` são os termos de
`buscar_por_cargo`; `filtro_salarial` (`desligado` \| `ativo`) liga a elegibilidade; `corte_fora_sul`
é o piso de teto fora do Sul; `resumo_filtrados` (`nunca` \| `semanal`) liga o resumo. Os padrões de
`ufs_sem_corte`, `esferas_sem_corte` e `cargos_total_inflado` vêm da SPEC — só precisam ser escritos
para se afastar do padrão. Valor inválido cai no modo mais conservador, nunca no mais agressivo.

Em produção o arquivo de configuração vive **fora do repo**, em `~/concursos-secrets/monitor.env`
(apontado por `MONITOR_ENV_FILE`); o roteiro de deploy é
[`docs/DEPLOY-PCI-MCP.md`](docs/DEPLOY-PCI-MCP.md).

### Agendamento automático

- **Linux (`cron` com catch-up horário + `@reboot` + Dead-Man's-Switch):**
  ```bash
  ./scripts/install_schedule.sh        # Instala tick horário no minuto 20 + @reboot
  crontab -l                           # Inspecionar entradas instaladas
  ./scripts/install_schedule.sh --remove
  ```
- **Windows (`Task Scheduler` com `StartWhenAvailable`):**
  ```powershell
  .\scripts\install_schedule.ps1
  .\scripts\install_schedule.ps1 -Time 04:30
  ```

### Execução e testes

```bash
# Simulação segura (varre todas as portas, loga as decisões, não escreve no banco e não envia):
python main.py --dry-run

# Rodada única de produção em todas as áreas configuradas:
python main.py

# Teste real da credencial de LLM com o cabeamento de produção:
python main.py --testar-llm

# Suíte completa (539 testes, sem rede e sem LLM):
pip install -r requirements-dev.txt
pytest
```

---

## 🧪 Suíte de Testes (539 testes em 19 arquivos)

| Arquivo de Teste | Escopo Coberto |
|---|---|
| `test_concurso_bot.py` | Fluxo ponta a ponta: 4 portas, matriz de decisão por fase, elegibilidade e selo no card, resumo semanal, listagem morta, 1ª carga por UF, extração degradada, alertas de saúde e dry-run |
| `test_pci_mcp_scraper.py` | Porta do MCP: união por `id`, mapeamento do item, leitura de JSON e SSE, truncamento e termo que falha sem parar a rodada (rede nunca é tocada: resposta gravada como fixture) |
| `test_pci_scraper.py` | Parsing determinístico de `/cargos/<slug>`, deduplicação intra-rodada por `pci_id`, extração de prazo na notícia (`enriquecer`) |
| `test_pci_nacional_scraper.py` | Parsing de `/concursos/nacional/`, precedência da janela de inscrição sobre o verbo do título, montagem de bloco para IA |
| `test_elegibilidade.py` | As nove regras da SPEC-001 e a precedência (primeira que casa vence), com casos transcritos à mão da tabela da spec |
| `test_salario.py` | `teto_de()`: formatos de texto reais do PCI e banda de sanidade (taxa de inscrição e valor por hora não viram salário) |
| `test_esfera.py` | `esfera_de()`: classificação do órgão (federal, estadual, distrital, municipal, conselho profissional) contra tabela escrita à mão |
| `test_resumo_filtrados.py` | Montagem do texto do resumo (contagem por motivo, limite de 30 linhas) e marcador de semana ISO |
| `test_saude_fontes.py` | Detecção de porta vazia (`🕳️`), porta congelada por dias (`🧊`), insensibilidade à ordem dos blocos |
| `test_database_manager.py` | Criação e migração automática aditiva de schema `v1 → v6`, resolução de identidade em 4 níveis, fusão automática de órgãos duplicados (`_fundir`), `listar_filtrados` |
| `test_intelligence_unit.py` | Roteamento entre Ollama, LiteLLM e Claude CLI, sanitização de datas/fases, retry, sinalização de erro (`erro: True`) e falha de credencial |
| `test_gran_scraper.py` | Fatiamento HTML por `<h3>`, páginas de carreira e filtros de ruído |
| `test_telegram_notifier.py` | Roteamento multi-chat, botões inline (`⭐`/`❌`), resiliência HTTP e modo `dry_run` |
| `test_telegram_callbacks.py` | Polling de `getUpdates`, transição de `estado_usuario` no banco e persistência de offset |
| `test_claude_cli_backend.py` | Invocação via `stdin`, timeouts, parsing de aliases (`haiku`/`sonnet`/`opus`) |
| `test_config_loader.py` | Parsing de `MONITOR_TARGETS_JSON`, as oito chaves novas por área, fallback legado e erro de configuração conservador |
| `test_diagnostico_producao.py` | Execução do script de diagnóstico por subprocess sobre uma árvore de arquivos falsa |
| `test_logger.py` | O token do Telegram nunca chega ao log (`FormatterSemSegredos`) |
| `test_text_utils.py` | Normalização sem acentos, `extrair_uf`, `status_fingerprint` e heurística `mesma_entidade` |
