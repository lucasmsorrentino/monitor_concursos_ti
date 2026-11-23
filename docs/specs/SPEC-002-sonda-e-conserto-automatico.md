# SPEC-002 — Sonda barata de madrugada, e conserto automatico do que tem prova

> **Estado:** proposta ao dono — 23/11/2026
> **Decisao que a sustenta:** `docs/adr/0003-sonda-barata-separada-do-conserto.md`
> **Itens do pedido que atende:** PED-05, PED-06
> **Depende da SPEC-001:** a sonda de contrato vigia a porta do MCP, que nasce la.
> Os termos sao os do `GLOSSARIO.md`.

## Pedido original

Pedido do Lucas no chat, em 23/11/2026:

- **PED-05** — "queria tambem uma especificacao de self heal do sistema": o sistema percebe sozinho que
  quebrou.
- **PED-06** — "um cron de verificacao barata, talvez amostral, pra consertar o codigo automaticamente": a
  verificacao e um cron, o custo e baixo, a cobertura e por amostra, e o conserto nao espera o dono.

## 1. Problema

O bot nao percebe que quebrou, e quando percebe nao diz por que. Os oito incidentes de 2026 estao tabelados na
ADR-0003; tres padroes se repetem neles:

1. **Silencio identico.** Um dia sem concurso novo e um dia quebrado produzem a mesma coisa: nada no Telegram.
   Foi assim que o bot ficou morto de 16/07 a 08/08/2026 com `exit=127` todo dia, e de 23/09 a 22/10 sem uma
   varredura completa.
2. **Alerta sem causa.** De 14/10 a 22/10 o Lucas recebeu 24 avisos por dia de "varredura incompleta" e
   "sem rodar", nenhum deles dizendo que o problema era o login da LLM expirado. O conserto de 22/10 nomeou a
   causa (alerta especifico de chave), mas so para essa causa.
3. **Conserto que chega tarde.** Entre a quebra e o conserto houve 36 dias (Gran congelado), 23 dias (venv
   quebrada) e 29 dias (login da LLM). Em todos, o que faltou foi alguem olhando de madrugada.

O que ja existe, e nao basta:

- `src/utils/saude_fontes.py` acusa fonte **vazia** e **parada** (21 dias de conteudo identico), mas so sobre o
  que a rodada daquele momento trouxe, e nao olha campo por campo;
- o dead-man do `scripts/run_daily.sh` avisa quando a ultima rodada completa esta velha, e so quando a maquina
  volta;
- o `scripts/diagnostico_producao.sh` da SPEC-001 e **retrospectivo**: le 30 dias de log e o banco, para
  humano, rodado a mao. A sonda e **prospectiva**: toca as fontes agora e compara com a linha de base. Eixos
  diferentes, sem sobreposicao de codigo.

## 2. Decisao

Duas sondas de madrugada, sem LLM, com amostragem; uma triagem deterministica que nomeia a causa; e um
conserto com agente confinado, que roda em duas das nove classes de sintoma e entrega branch com gate.

- **Sonda de ambiente**, no notebook de producao: venv, cron, marcador, banco, credencial, rede, disco,
  relogio.
- **Sonda de contrato**, na maquina de desenvolvimento: uma porta profunda por noite em rodizio, poucos itens
  por porta, campo por campo contra piso declarado e contra a linha de base.
- **Triagem**: nove classes, primeira que casa vence. Sete terminam em alerta com causa nomeada; duas acionam
  o conserto.
- **Conserto**: a sonda grava a fixture e escreve o teste vermelho; o agente faz o verde sem tocar em teste;
  nove condicoes de gate; a saida e branch mais alerta com o diff resumido.

## 3. Contrato

### 3.1. `src/sonda/contrato.py` — o que cada porta promete

```python
@dataclass(frozen=True)
class CampoEsperado:
    nome: str          # chave do item que a porta devolve
    piso: float        # fracao minima de itens com o campo preenchido (0.0 a 1.0)
    tipo: type         # str, bool, int. None conta como ausente, nao como tipo errado.

@dataclass(frozen=True)
class ContratoDaPorta:
    porta: str                      # "pci_mcp", "gran", "pci_slug", "pci_nacional"
    campos: tuple[CampoEsperado, ...]
    profunda: bool                  # True entra no rodizio; a do MCP e conferida toda noite

@dataclass(frozen=True)
class Medida:
    porta: str
    itens: int
    preenchimento: dict[str, float]  # campo -> fracao preenchida nesta noite
    medido_em: str                   # AAAA-MM-DD
```

`comparar(contrato, medida, base) -> list[Sintoma]` e **pura**. Dois gatilhos, independentes:

- **piso**: `preenchimento[campo] < campo.piso`;
- **queda**: `base[campo] - preenchimento[campo] > TOLERANCIA_QUEDA` (0.30), quando existe linha de base.

O piso de cada porta e declarado no modulo, nao configuravel, porque e afirmacao sobre a fonte e tem de ser
revisada por quem muda o parser. Para a porta do MCP, com os numeros da fixture de 23/11/2026:

| Campo | Piso | Por que |
| :--- | :-: | :--- |
| `link`, `pci_id`, `nome`, `fase`, `fonte` | 1.00 | sem eles o item nao e gravavel nem deduplicavel |
| `regiao` | 0.95 | e o campo que o filtro da SPEC-001 exige (R-15); sem ele o concurso perde a avaliacao |
| `uf` | 0.80 | `NACIONAL` vem com `uf: null` de proposito (1 em 9 na fixture medida) |
| `cargos_total` | 0.90 | e a evidencia do municipal inflado |
| `vagas_salario` | 0.60 | 11 de 21 titulos tinham `R$` na medida de 22/10; piso folgado |
| `data_fim_inscricao` | 0.50 | so os abertos tem data de fim |

### 3.2. `src/sonda/triagem.py` — sintoma, classe, acao

```python
@dataclass(frozen=True)
class Sintoma:
    origem: str        # "ambiente:venv", "contrato:pci_mcp", "suite"
    detalhe: str       # uma frase, sem segredo, pronta para o Telegram
    dados: dict        # numeros crus para o relatorio (nunca valor de credencial)

@dataclass(frozen=True)
class Veredito:
    classe: str        # uma das nove da secao 4.3
    acao: str          # "alerta" | "conserto" | "nota"
    emoji: str         # o do alerta, no padrao que o bot ja usa
```

`classificar(sintomas) -> list[tuple[Sintoma, Veredito]]` e **pura** e sem rede.

### 3.3. A linha de base — `data/sonda-base.json`

```json
{
  "pci_mcp": {
    "preenchimento": {"link": 1.0, "uf": 0.86, "regiao": 1.0, "cargos_total": 0.97},
    "itens": 30, "medido_em": "2026-11-23", "noites": 7
  }
}
```

- Escrita por media movel das ultimas sete noites **saudaveis**. Noite com sintoma de `rede`, `credencial` ou
  `fonte_vazia` nao entra na media: um dia de site fora nao pode rebaixar o piso e mascarar a queda seguinte.
  E a mesma regra que o `saude_fontes` ja aplica ao digest de fonte vazia.
- Sem linha de base (primeira noite), so o piso vale. A sonda nao inventa queda contra base que nao existe.
- Vive em `data/`, que nao e versionado, pelo mesmo motivo do `saude_fontes.json`.

### 3.4. O dossie — `data/sondas/<data>-<classe>/`

O que a sonda entrega ao conserto, e o que fica como evidencia mesmo quando o conserto nao roda:

| Arquivo | O que e |
| :--- | :--- |
| `resposta.json` ou `resposta.html` | a resposta crua da porta naquela noite, byte a byte |
| `fixture/<nome>.json` | a mesma resposta, no formato e no lugar de `tests/fixtures/` |
| `test_sintoma.py` | o teste vermelho, escrito pela sonda a partir do contrato declarado |
| `sintoma.json` | sintomas, classe, medida, linha de base, versao do repo (`git rev-parse`) |
| `relatorio.md` | uma pagina: o que mudou, o que o teste cobra, o que o gate exige |

Retencao: `SONDA_RETENCAO_DIAS` (14). Dossie com conserto integrado e apagado junto; a fixture dele ja esta no
repo.

### 3.5. O gate do conserto — `src/sonda/conserto.py`

`gate(diff, resultado_suite, contexto) -> Gate` e **pura** sobre texto. Nove condicoes, todas obrigatorias:

| # | Condicao |
| :-: | :--- |
| 1 | o teste vermelho do dossie passa |
| 2 | a suite inteira passa, sem nenhum teste a menos do que antes do conserto |
| 3 | todo arquivo do diff esta na allowlist (`src/scrapers/`, `src/utils/salario.py`, `src/utils/esfera.py`, `src/utils/text.py`, `src/core/elegibilidade.py`) |
| 4 | nenhum arquivo de `tests/`, `requirements.txt`, `.env*`, `scripts/`, `kanban/`, `docs/`, `main.py` ou `config/` aparece no diff |
| 5 | o diff adiciona no maximo `SONDA_CONSERTO_DIFF_MAX` linhas (80) |
| 6 | `requirements.txt` inalterado |
| 7 | o diff nao casa com o regex de segredo do `src/utils/logger.py` nem com nome de chave conhecido |
| 8 | nenhum `requests.`, `urlopen` ou `socket` novo dentro de `tests/` (redundante com a 4, e deliberado) |
| 9 | o teste novo nao foi afrouxado: o `test_sintoma.py` do worktree e byte a byte igual ao do dossie |

Reprovou qualquer uma: a branch fica, nada se mescla, e o alerta diz **qual** condicao reprovou. Isso e
informacao sobre o agente, nao sobre a fonte.

### 3.6. Configuracao (ambiente, fora do repo)

| Chave | Padrao | O que faz |
| :--- | :--- | :--- |
| `SONDA_CONSERTO` | `dossie` | `desligado`, `dossie`, `patch` ou `auto` |
| `SONDA_CONSERTO_EXECUTOR` | vazio | comando do agente; vazio equivale a `dossie` |
| `SONDA_CONSERTO_MAX_NOITE` | `1` | consertos por noite |
| `SONDA_CONSERTO_MAX_SEMANA` | `3` | consertos por semana ISO |
| `SONDA_CONSERTO_DIFF_MAX` | `80` | linhas adicionadas no diff |
| `SONDA_CONSERTO_AMBIENTE` | `0` | deixa a sonda reconstruir venv e reinstalar cron |
| `SONDA_PORTAS` | `pci_mcp,gran,pci_slug,pci_nacional` | ordem do rodizio |
| `SONDA_AMOSTRA` | `3` | itens por porta de HTML |
| `SONDA_RETENCAO_DIAS` | `14` | dias de dossie guardado |
| `MONITOR_AUTO_PULL` | `0` | `git pull --ff-only` antes da rodada, na producao |

Valor invalido cai no mais conservador (`SONDA_CONSERTO` vira `dossie`, nunca `auto`), pela regra de fail-open
do `kanban/REGRAS.md`.

## 4. Regras

### 4.1. A sonda de contrato (maquina de desenvolvimento)

- **R-30** Uma porta **profunda** por noite, no rodizio de `SONDA_PORTAS`, mais a porta do MCP toda noite. O
  ponteiro do rodizio vive na linha de base.
- **R-31** Amostra: na porta do MCP, **um** termo de cargo por noite (rodizio na lista de termos) e todos os
  itens que ele devolver, porque vem numa chamada so. Nas portas de HTML, os `SONDA_AMOSTRA` primeiros itens.
- **R-32** **A sonda nunca chama a LLM.** Na porta do Gran ela confere so a parte deterministica: a pagina
  abriu, quantos blocos sairam, e o `dateModified`. Mandar bloco para a LLM custa 15 s por bloco.
- **R-33** Resposta com HTTP 404 ou 410 e `fonte_morta`; 401 ou 403 e `credencial`; timeout ou falha de DNS em
  **todos** os hosts e `rede`; num host so, `fonte_morta`.
- **R-34** Zero itens e `fonte_vazia`, e so alerta na **terceira** noite seguida. Uma noite vazia e comum.
- **R-35** Chave nova na resposta, que o contrato nao declara, e `contrato_novo`: nota no relatorio, sem alerta
  e sem conserto. Fonte que acrescenta campo nao quebrou nada.
- **R-36** Ao fim, `pytest -m contrato` na arvore limpa. Vermelha com as fontes saudaveis e `regressao`. O
  `pytest.ini` do repo roda com `--strict-markers`, entao o marcador `contrato` precisa ser **registrado** em
  `[pytest] markers` na mesma fatia que o usa, senao todo teste marcado quebra na coleta. Marcam-se os testes
  que leem fixture de porta (`test_pci_mcp_scraper.py` e os irmaos), nao os de regra pura.
- **R-37** A resposta crua da noite e sempre gravada, com ou sem sintoma, por `SONDA_RETENCAO_DIAS`. E a unica
  chance de saber como a fonte era na vespera.

### 4.2. A sonda de ambiente (notebook de producao)

Cada item e um sintoma com causa nomeada:

- **R-40** **venv**: importa cada pacote de primeiro nivel do `requirements.txt`. Falha e `ambiente`.
- **R-41** **agendamento**: `crontab -l` tem a linha horaria e a `@reboot` com a tag do projeto. Ausente e
  `agendamento`.
- **R-42** **marcador**: `logs/.last_success_date` com mais de 2 dias e `agendamento`.
- **R-43** **saida das rodadas**: nenhum `exit=0` nos logs das ultimas 72 h e `agendamento`, com o ultimo
  `ERROR` do log mais recente no detalhe.
- **R-44** **banco**: `PRAGMA integrity_check` diferente de `ok` e `ambiente`; schema em versao diferente da
  esperada e `ambiente`; zero linha nova em 7 dias e `cobertura`.
- **R-45** **credencial**: para cada chave esperada, confere **presenca** e faz um ping do provedor com
  `max_tokens=20`, no molde do `scripts/diagnostico_zai.py`. Ausencia, 401, 403 ou saldo e `credencial`. O
  valor da chave nao e lido para log nem para alerta, so o nome.
- **R-46** **disco**: menos de 500 MB livres e `ambiente`.
- **R-47** **relogio**: diferenca maior que 5 min entre o relogio local e o cabecalho `Date` de uma das fontes
  e `ambiente`. Relogio errado estraga prazo, dead-man e marcador de semana ISO.
- **R-48** A sonda de ambiente **nao** toca as fontes alem do HEAD do R-47, nao roda varredura, nao escreve no
  banco e nao manda card de concurso.

### 4.3. A triagem (primeira que casa vence)

| # | Sintoma | Classe | Acao | Alerta |
| :-: | :--- | :--- | :--- | :-: |
| 0 | chave ausente, 401, 403, saldo | `credencial` | alerta | 🔑 |
| 1 | DNS ou timeout em todos os hosts | `rede` | alerta | 📡 |
| 2 | cron ausente, marcador velho, nenhum `exit=0` em 72 h | `agendamento` | alerta (conserto de ambiente se ligado) | ⏰ |
| 3 | venv, disco, relogio, integridade do banco | `ambiente` | alerta (conserto de ambiente se ligado) | 🧰 |
| 4 | HTTP 404 ou 410 numa porta | `fonte_morta` | alerta | 🚪 |
| 5 | zero itens por 3 noites | `fonte_vazia` | alerta | 🕳️ |
| 6 | conteudo identico ha mais de 21 dias | `fonte_parada` | alerta | 🧊 |
| 7 | campo abaixo do piso, ou queda maior que 0,30 | **`contrato`** | **conserto** | 🧩 |
| 8 | suite `contrato` vermelha com as fontes saudaveis | **`regressao`** | **conserto** | 🧩 |
| 9 | chave nova na resposta | `contrato_novo` | nota | — |

- **R-50** Classe de credencial, rede, agendamento, ambiente, fonte morta, fonte vazia e fonte parada **nunca**
  acionam conserto de codigo. Nao ha o que consertar em codigo, e tentar esconde a causa.
- **R-51** Varios sintomas na mesma noite: um alerta so, com uma linha por classe, na ordem da tabela. Nunca um
  alerta por sintoma, que foi o erro de 14/10 a 22/10/2026.
- **R-52** No maximo um alerta de cada classe por dia, no esquema do `_alerta_uma_vez_por_dia` que o bot ja
  usa.

### 4.4. O conserto

- **R-60** So nas classes `contrato` e `regressao`. Modo `dossie` para em 3.4, sem agente.
- **R-61** O agente roda num **worktree** novo, saido de `main`, nunca na arvore de trabalho e nunca no repo de
  producao.
- **R-62** O prompt leva: o `relatorio.md`, o `sintoma.json`, o caminho do teste vermelho, a allowlist e as
  nove condicoes do gate. Nao leva nada de fora do worktree, pela mesma razao da esteira: sessao headless nao
  tem quem aprove acesso.
- **R-63** O gate da secao 3.5 roda **depois** do agente, sobre o diff. Nenhuma condicao e opcional e nenhuma e
  avaliada pelo agente.
- **R-64** Gate aprovado: branch `conserto/<classe>-<AAAAMMDD>`, comitada no padrao de TDD do repo (`test:`
  com a fixture e o teste, `fix:` com o conserto), mais alerta com o `--stat` do diff. Modo `auto` mescla em
  `main`; modo `patch` para na branch.
- **R-65** Gate reprovado: a branch fica para inspecao, nada se mescla, e o alerta nomeia a condicao.
- **R-66** **Disjuntor**: dois consertos reprovados na mesma classe desligam o conserto dessa classe por 7
  dias, e o alerta diz isso. Healer que insiste em erro queima cota e enche o Telegram.
- **R-67** Os limites de `SONDA_CONSERTO_MAX_NOITE` e `SONDA_CONSERTO_MAX_SEMANA` valem sobre tentativas, nao
  sobre sucessos.
- **R-68** O conserto **nunca** grava credencial, nunca mexe em `~/concursos-secrets/`, nunca roda
  `install_schedule.*` e nunca faz `push`. Publicar e do dono.
- **R-69** Conserto de ambiente (`SONDA_CONSERTO_AMBIENTE=1`) e deterministico e sem agente: reconstruir a
  venv com `pip install -r requirements.txt` e reinstalar o cron com o proprio `install_schedule.sh`. Uma
  tentativa por noite, e o alerta sai de qualquer jeito, antes e depois.

### 4.5. A sonda falhando

- **R-70** Excecao dentro da sonda vira alerta com a classe `sonda` e saida diferente de zero. Sonda que morre
  calada reproduz o problema que ela existe para resolver.
- **R-71** Codigos de saida: `0` saudavel, `10` sintoma sem conserto, `20` sintoma com conserto entregue, `30`
  a propria sonda falhou.
- **R-72** Tres noites sem nenhum relatorio novo de uma das sondas e sintoma da outra: cada sonda vigia a
  frescura do relatorio da irma, pelo arquivo, nao por rede.

## 5. Testes e aceitacao

**Costuras**, da mais alta para a mais baixa:

1. `sonda.rodar()`, com as portas e o ambiente dublados — a noite inteira: medida, sintoma, triagem, dossie,
   alerta, codigo de saida. Nao pega rede nem agente.
2. `conserto.rodar()`, com o agente dublado por um script que aplica um diff conhecido — pega o worktree, o
   gate e a branch. **Nunca lanca agente de verdade na suite.**
3. `contrato.comparar()` — pura: piso, queda, ausencia de base.
4. `triagem.classificar()` — pura: uma linha da tabela 4.3 por teste, mais a precedencia entre classes.
5. `conserto.gate()` — pura sobre texto: um diff que passa, e **um diff por condicao** que a reprova sozinha.

**Oraculo:** as fixtures de `tests/fixtures/pci_mcp/` gravadas em 23/11/2026, uma linha de base escrita a mao,
e diffs de texto escritos a mao. Nenhum valor esperado sai do proprio comparador nem do proprio gate.

**A SPEC fecha quando:**

- [ ] a suite passa inteira, sem regressao, e cada regra numerada tem teste;
- [ ] uma noite real de cada sonda grava relatorio e chega no Telegram, **sem nenhum alerta falso** (a primeira
      noite e so linha de base: alerta de queda sem base e bug);
- [ ] **o ensaio do sintoma plantado** atravessa o caminho inteiro: uma copia da fixture do MCP sem o campo
      `regiao` produz sintoma, classe `contrato`, dossie com fixture e teste vermelho, e um conserto que passa
      as nove condicoes do gate;
- [ ] no mesmo ensaio, o gate **reprova** um patch que edita `tests/`, um que acrescenta linha ao
      `requirements.txt` e um que afrouxa o teste do dossie;
- [ ] o disjuntor da R-66 desliga a classe depois de duas reprovacoes, verificado por teste;
- [ ] a sonda de ambiente, rodada no notebook com a venv propositalmente quebrada, nomeia `ambiente` e nao
      `credencial`.

## 6. Fora do escopo

- **Autocorrecao de seletores com `browser-use` e Playwright** (`PLANO_EVOLUCAO_AGENTICA.md` secao 7). O
  criterio de entrada de la continua valendo e nao foi atingido: zero quebra de seletor em 90 dias.
- **Consertar credencial, saldo, DNS e rede.** Chave quem grava e o Lucas (`kanban/REGRAS.md`).
- **Decidir cobertura.** Classe de concurso que nenhuma porta ve (a Dataprev de 07/2026) e decisao de produto,
  nao sintoma: vira ticket.
- **Trocar a porta do Gran pela API do WordPress.** Continua fora, como na SPEC-001 secao 6.
- **Rotacionar o token do Telegram** vazado nos logs antigos. Pendencia 2 do `HANDOFF.md`, do dono.
- **Deploy automatico em producao.** `MONITOR_AUTO_PULL` existe e nasce desligado.
- **Vigiar outra coisa que nao este projeto.** A sonda nao e monitor de infra do Lucas: Hermes, VM do OCI e
  mesh ficam fora.
- **Dashboard ou historico em banco.** O relatorio e arquivo, com retencao de 14 dias.

## 7. Questoes em aberto (precisam do dono antes dos tickets)

1. **Modo do conserto na largada.** Proposto `dossie` na primeira semana, `patch` depois do ensaio plantado, e
   `auto` so se o primeiro conserto real acertar. Alternativa: `patch` ja na largada.
2. **Onde a sonda de contrato roda.** Proposto o desktop, onde os agentes e as chaves vivem; noite com a
   maquina desligada e noite perdida. Alternativa: a VM ARM do OCI, que esta de pe com 148 dias de uptime e
   nunca desliga, mas nao tem agente nem chave de agente, o que obrigaria a separar ver de consertar em duas
   maquinas.
3. **`MONITOR_AUTO_PULL` em producao.** Com ele, um conserto mesclado entra sozinho na rodada seguinte, e o
   ciclo fecha sem o dono. Sem ele, o `git pull` continua sendo o degrau humano de hoje.

## 8. Ainda nao especificado (nevoa)

- **O custo real de uma noite.** A estimativa e de segundos e de um ping de 20 tokens por provedor. A medida
  sai na primeira semana, e o piso de cada campo pode mudar com ela.
- **Se a classe `regressao` acontece.** E uma classe nova, criada porque a esteira passou a mexer no parser com
  agente. Sem historico.
- **Se o conserto automatico acerta.** O ensaio plantado prova o caminho, nao o acerto. So o primeiro sintoma
  real diz se o patch do agente presta, e e por isso que o modo nasce em `dossie`.
- **O piso honesto de cada campo.** Os numeros da secao 3.1 vem de uma fixture de um dia. Sete noites de linha
  de base dizem mais.
- **O que o diagnostico de producao da SPEC-001 vai revelar.** Ele ainda nao foi rodado; se mostrar uma falha
  recorrente que a sonda nao cobre, entra como regra nova aqui.

## Corte proposto (tickets, depois do OK do dono)

| # | Nivel | Depende de | Entrega |
| :--- | :-: | :--- | :--- |
| S-01 | M− | — | `src/sonda/contrato.py`: `ContratoDaPorta`, pisos declarados, `comparar()` pura |
| S-02 | M− | — | `src/sonda/triagem.py`: as nove classes e a precedencia, pura |
| S-03 | M+ | S-01, T-004 | `src/sonda/portas.py`: rodizio, amostra, medida por campo, sem LLM |
| S-04 | M+ | — | `src/sonda/ambiente.py`: R-40 a R-48, com o ping do molde do `diagnostico_zai.py` |
| S-05 | P+ | S-01 | `src/sonda/dossie.py`: fixture, teste vermelho gerado, relatorio |
| S-06 | **G−** | S-05 | `src/sonda/conserto.py`: worktree, agente, as nove condicoes do gate, disjuntor |
| S-07 | M− | S-02, S-03, S-04 | `src/sonda/__main__.py` e o alerta de uma mensagem por noite |
| S-08 | P+ | S-07 | `scripts/sonda.sh`, `scripts/sonda_ambiente.sh`, instalador de cron de madrugada escalonado |
| S-09 | P+ | S-06, S-08 | `docs/SONDA.md`, README, CLAUDE.md, e o roteiro do ensaio plantado |
| S-10 | P− | S-09 | Deploy e a primeira semana de linha de base. Recurso do dono. |

Caminho critico: S-01 → S-05 → S-06 → S-09 → S-10. Onda 0 larga: S-01, S-02, S-04.

## Revisoes

- 23/11/2026 r1 — criada. A tabela de incidentes da ADR-0003 mudou o desenho: a camada que ve nao tem LLM, e o
  conserto automatico vale para duas classes das nove, nao para todas.
- 23/11/2026 r1.1 — R-36 ganhou o registro do marcador `contrato`: o `pytest.ini` do repo roda com
  `--strict-markers`, e marcador nao registrado quebra a coleta inteira.
