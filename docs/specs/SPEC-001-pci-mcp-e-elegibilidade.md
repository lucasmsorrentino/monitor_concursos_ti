# SPEC-001 — O PCI pelo servidor MCP, e silencio para o que nao paga fora do Sul

> **Estado:** proposta ao dono — 23/11/2026
> **Decisoes que a sustentam:** `docs/adr/0001-mcp-como-unica-porta-do-pci.md`,
> `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`
> **Itens do pedido que atende:** PED-01, PED-02, PED-03, PED-04
> Os termos sao os do `GLOSSARIO.md`.

## Pedido original

Pedido do Lucas no chat, em 20/11/2026:

- **PED-01** — "ele nao tem funcionado muito bem": a confiabilidade das portas do PCI.
- **PED-02** — "o pci concursos agora tem um servidor mcp. pode atualizar o projeto": adotar o servidor MCP
  oficial do PCI.
- **PED-03** — "cuida para nao enviar mais concursos fora do sul do brasil que paguem menos que 10 mil":
  silenciar o que nao alcanca o corte fora do Sul.
- **PED-04** — "para o cargo de ti especificamente": so na area TI; as outras areas nao mudam de comportamento.

Decisoes do dono em 22 e 23/11/2026, nas duas rodadas de perguntas:

- esfera `federal` fica isenta do corte (o contrario da leitura literal de PED-03, escolhido com os numeros na
  mesa);
- o MCP vira a unica porta do PCI, com os dois scrapers de HTML desligados mas presentes;
- municipal inflado fora do Sul e descartado;
- o filtro entra cortando na primeira rodada, com resumo semanal do que foi filtrado;
- a esteira integra em `main` (o `fix/ia-sem-login-e-zai` foi mesclado por fast-forward em 23/11/2026) e vai
  ate o deploy no notebook.

## 1. Problema

Tres portas leem concurso hoje e nenhuma delas e confiavel do jeito que esta:

- o blog do Gran manda **um bloco de HTML por LLM**, 45 a 51 blocos por rodada, ~15 s cada. Foi o caminho que
  ficou sem completar uma varredura de **23/09 a 22/10/2026** (`HANDOFF.md`), um mes inteiro, porque a
  credencial da LLM morreu;
- o `PciScraper` le `/cargos/<slug>` raspando `ul.link-d` e o `nXXXXXX` da classe CSS. A pagina de cargo
  **nunca** traz o prazo (medido: 0 de 55 itens), entao cada item novo custa uma requisicao extra na noticia;
- o `PciNacionalScraper` existe so porque a porta de cargo nao lista estatal federal: a Dataprev ficou com
  inscricoes abertas de 06/07 a 06/08/2026 e nao apareceu em nenhum dos seis garimpos rodados na janela.

E o volume nao e filtrado. Em 22/11/2026, a busca por 13 termos de TI no PCI devolveu **108 concursos
distintos**: 29 no Sul e **79 fora**, dos quais 44 tem teto abaixo de R$ 10.000. Metade do que chega no
Telegram e vaga que o Lucas nao faria: fora do Sul, pagando menos do que ele ganha hoje.

## 2. Decisao

**Uma porta nova, estruturada, no lugar das duas de HTML** (ADR-0001), e **uma funcao de elegibilidade** que
decide o silencio antes da notificacao (ADR-0002).

O servidor MCP (`https://mcp.pciconcursos.com.br/mcp`, sem autenticacao, somente leitura, verificado em
20 e 22/11/2026) devolve por chamada o que as duas portas raspavam, mais o que elas nunca tiveram: `regiao`
(inclusive `NACIONAL`), `cargos_total`, o teto do concurso e as datas de inscricao **ja calculadas pelo
servidor**. O `id` dele e o mesmo numero de noticia que virava `pci_id`, entao o dedup atravessa a troca de
porta sem migracao de dado.

A elegibilidade e uma funcao pura sobre valores primitivos, fora do bot. Quem a chama monta a entrada; ela
decide. Assim ela se testa sozinha e e o oraculo dos testes de quem a consome.

## 3. Contrato

### 3.1. Item que a porta do MCP devolve

Dict no mesmo formato que a `IntelligenceUnit` produziria, como o `PciScraper` ja faz, com quatro campos novos:

```python
{
    "ignorar": False,
    "nome": "Prefeitura de Italva - RJ",   # titulo + " - " + uf; so o titulo quando uf e None
    "status": "<noticia.titulo>",
    "link": "<noticia.link>",
    "fase": "inscricoes_abertas",
    "data_fim_inscricao": "2026-12-16",    # datas.fim, ja ISO
    "data_referencia": None,
    "pci_id": "296654",                    # str(id)
    "uf": "RJ",                            # ou None nos nacionais
    "cargos": ["ANALISTA DE SISTEMAS"],
    "fonte": "pci_mcp",
    # novos
    "regiao": "SUDESTE",                   # SUL | SUDESTE | NORTE | NORDESTE | CENTRO-OESTE | NACIONAL
    "cargos_total": 53,
    "vagas_salario": "137 vagas ate R$ 12.132,37",   # texto cru, sem parse
    "termos_origem": ["analista de sistemas"],
}
```

- **`nome` leva a UF no sufixo.** O `extrair_uf` e o `mesma_entidade` de `src/utils/text.py` esperam o estilo do
  PCI ("Camara de Passos - MG"); o MCP manda `titulo` e `uf` separados. Montar o sufixo mantem o dedup entre
  fontes funcionando sem tocar em `text.py`.
- **`fase` vem das datas, nao do titulo:** `datas.aberto` para `inscricoes_abertas`; `datas.em_breve` para
  `edital_publicado`; nenhum dos dois cai no `inferir_fase(noticia.titulo)` de `src/scrapers/pci_comum.py`.
- **`vagas_salario` vai cru.** O parse mora em `src/utils/salario.py`, nao no scraper.

### 3.2. `src/utils/salario.py`

```python
def teto_de(texto: str | None) -> float | None
```

O maior valor em reais citado no texto, ou `None` quando nao ha valor legivel. **Banda de sanidade:** valor
abaixo de R$ 500,00 ou acima de R$ 80.000,00 e ignorado, para taxa de inscricao ("a taxa e de R$ 65,00") e
valor por hora ("R$ 32,64 por hora") nao virarem salario mensal.

### 3.3. `src/utils/esfera.py`

```python
def esfera_de(nome: str | None) -> str | None
```

Uma de `"federal"`, `"estadual"`, `"distrital"`, `"municipal"`, `"conselho_profissional"`, ou `None` quando o
nome nao decide.

### 3.4. `src/core/elegibilidade.py`

```python
@dataclass(frozen=True)
class Candidato:
    uf: str | None
    regiao: str | None
    esfera: str | None
    teto: float | None
    cargos_total: int | None
    seguindo: bool = False

@dataclass(frozen=True)
class Politica:
    modo: str = "desligado"               # "desligado" | "ativo"
    corte_fora_sul: float = 0.0
    ufs_sem_corte: tuple[str, ...] = ("PR", "SC", "RS")
    esferas_sem_corte: tuple[str, ...] = ("federal",)
    cargos_total_inflado: int = 10

@dataclass(frozen=True)
class Decisao:
    entra: bool
    motivo: str
    selo: str | None = None

def decidir(c: Candidato, p: Politica) -> Decisao
```

`motivo` e de conjunto fechado: `seguindo`, `filtro_desligado`, `nao_verificado`, `sul`, `federal`,
`abaixo_do_corte`, `municipal_inflado`, `sem_evidencia`, `acima_do_corte`.

### 3.5. Colunas novas no banco (schema v6, aditivo)

`uf TEXT`, `regiao TEXT`, `esfera TEXT`, `cargos_total INTEGER`, `salario_teto REAL`, `elegibilidade TEXT`,
`motivo_filtro TEXT`. Linha anterior ao v6 tem `elegibilidade` nulo e **conta como elegivel**: ja foi
notificada, nao se renotifica nem se apaga.

```python
def listar_filtrados(self, desde: str) -> list[dict]
```

As linhas da area com `elegibilidade = 'filtrado'` e `ultima_atualizacao >= desde`.

### 3.6. Config por area (`MONITOR_TARGETS_JSON`)

| chave | padrao | o que faz |
| :--- | :--- | :--- |
| `pci_mcp` | `false` | liga a porta do MCP |
| `pci_mcp_cargos` | `[]` | termos de `buscar_por_cargo`; vazio com `pci_mcp` ligado e erro de config |
| `filtro_salarial` | `"desligado"` | `desligado` ou `ativo`; valor invalido cai em `desligado` |
| `corte_fora_sul` | `0` | o piso de teto fora do Sul |
| `ufs_sem_corte` | `["PR","SC","RS"]` | UFs que nao passam pelo corte |
| `esferas_sem_corte` | `["federal"]` | esferas isentas do corte |
| `cargos_total_inflado` | `10` | acima disso, municipal fora do Sul e inflado |
| `resumo_filtrados` | `"nunca"` | `nunca` ou `semanal` |

## 4. Regras

### 4.1. A porta do MCP

- **R-01** Uma chamada `buscar_por_cargo` por termo de `pci_mcp_cargos`, sem `uf` (a busca sem `uf` cobre todos
  os estados e os nacionais). A uniao e por `id`; o mesmo concurso visto por varios termos acumula os `cargos`
  e os `termos_origem`, como o `PciScraper` ja faz com os slugs.
- **R-02** Transporte JSON-RPC 2.0 por HTTP POST, com `Accept: application/json, text/event-stream`. A resposta
  vem em JSON direto ou em SSE (uma linha por `data: `): as duas formas se leem. O payload util e o primeiro
  `content` de tipo `text`, que carrega JSON.
- **R-03** Termo que devolve o campo `message` nao trouxe resultado: segue sem erro e **nao** se repete a
  chamada com o mesmo valor.
- **R-04** Chamada que falha (rede, HTTP diferente de 200, JSON invalido) e registrada e a rodada **segue com
  os outros termos**. Todos os termos falhando e falha da fonte, que o diagnostico de saude pega.
- **R-05** Item cujo `cargos` casado contem palavra de `keywords_exclude` da area e descartado. **Nao** se
  exige `keywords_include`: cargo legitimo de TI ("PROGRAMADOR", "DESENVOLVEDOR") nao casa as palavras de
  inclusao configuradas hoje, e gate de inclusao viraria silencio.
- **R-06** `buscar_por_cargo` corta em 200 itens (medido: `professor` devolve exatamente 200). Termo de TI nao
  passa de 69 hoje; termo que devolver 200 e logado como aviso de truncamento.
- **R-07** A fonte entra em `saude_fontes` com o nome `pci_mcp` e a URL do servidor, para o alerta de fonte
  parada valer para ela.

### 4.2. A elegibilidade (primeira regra que casa vence)

| # | Condicao | Resultado | `motivo` |
| :-: | :--- | :--- | :--- |
| 0 | `c.seguindo` | entra | `seguindo` |
| 1 | `p.modo` diferente de `"ativo"` | entra | `filtro_desligado` |
| 2 | `uf` e `regiao` ambas desconhecidas | entra, com selo | `nao_verificado` |
| 3 | `uf` em `p.ufs_sem_corte`, ou `regiao == "SUL"` | entra | `sul` |
| 4 | `esfera` em `p.esferas_sem_corte` | entra | `federal` |
| 5 | `teto` conhecido e menor que `p.corte_fora_sul` | **filtrado** | `abaixo_do_corte` |
| 6 | `esfera == "municipal"` e `cargos_total` maior que `p.cargos_total_inflado` | **filtrado** | `municipal_inflado` |
| 7 | `teto` desconhecido | entra, com selo | `sem_evidencia` |
| 8 | resto | entra | `acima_do_corte` |

- O selo das regras 2 e 7 e `⚠️ salario nao verificado`, e aparece no card.
- `regiao == "NACIONAL"` nao e Sul: cai nas regras seguintes, e na pratica a esfera decide.
- **A regra 0 nunca se contorna:** o que o Lucas marcou com estrela chega sempre.

### 4.3. O que o bot faz com a decisao

- **R-10** A elegibilidade e **coluna separada** de `estado_usuario`: aquela e do bot, esta e do Lucas.
- **R-11** Item novo e filtrado: salva em silencio com `elegibilidade='filtrado'` e o `motivo_filtro`, do mesmo
  jeito que hoje salva um concurso novo e inativo. **Nao notifica.**
- **R-12** Linha filtrada que depois passa a entrar (o edital saiu, o teto subiu, o Lucas estrelou) sai como
  **novo**, porque ele nunca a viu.
- **R-13** Linha que entrava e passa a filtrada: nada se renotifica e nada se apaga; so se grava o novo motivo.
- **R-14** Area com `filtro_salarial` desligado nao muda em nada o comportamento de hoje (PED-04).
- **R-15** **So item de porta que carrega `regiao` e avaliado.** Hoje e a do MCP. Item do blog do Gran, da
  pagina de cargo ou da lista nacional nao e avaliado, nao recebe selo e nao grava `elegibilidade`: entra como
  entra hoje. Motivo: so a porta do MCP traz `regiao`, `cargos_total` e o teto; avaliar as outras poria o selo
  `nao_verificado` em todo card do Gran, por falta de um dado que aquela porta nunca teve.

### 4.4. O resumo semanal

- **R-20** Com `resumo_filtrados: "semanal"`, uma vez por semana por area sai uma mensagem com a contagem por
  motivo e a lista do que foi filtrado nos ultimos 7 dias (orgao, UF, teto, motivo), no maximo 30 linhas, com o
  resto como "e mais N".
- **R-21** Semana sem nada filtrado nao manda mensagem.
- **R-22** O controle de "uma vez por semana" usa marcador em arquivo, como o `_alerta_uma_vez_por_dia` faz
  hoje, e nao depende de o cron acertar o dia.

## 5. Testes e aceitacao

**Costuras**, da mais alta para a mais baixa:

1. `ConcursoBot.executar()`, com as portas dubladas — pega a rodada inteira: filtro aplicado, silencio,
   gravacao, resumo. Nao pega o transporte HTTP.
2. `PciMcpScraper.capturar_concursos()`, com a resposta do servidor gravada como fixture — pega a uniao por
   `id`, o mapeamento do item e a leitura de SSE. Nao pega a rede.
3. `elegibilidade.decidir()` — pega as nove regras e a precedencia. Pura, sem duble.
4. `salario.teto_de()` e `esfera.esfera_de()` — pegam os formatos e as classificacoes.

**Oraculo:** fixture gravada da resposta real do MCP (capturada em 22/11/2026) e tabelas de caso escritas a
mao a partir da secao 4. Nenhum valor esperado sai recalculado do jeito que o codigo calcula.

**A SPEC fecha quando:**

- [ ] a suite passa inteira (296 testes verdes em 23/11/2026, sem regressao) e os testes novos cobrem cada
      regra numerada;
- [ ] uma rodada `--dry-run` na area TI, com o MCP ligado e o filtro ativo, mostra `filtrado` para os
      municipais inflados e para os de teto abaixo do corte, e `entra` para Sul, federal e teto acima;
- [ ] nenhum concurso do Sul e nenhum federal aparece como filtrado nessa rodada;
- [ ] o deploy no notebook roda uma varredura completa com `exit=0` e o Lucas recebe o primeiro Telegram sem o
      ruido de fora do Sul.

## 6. Fora do escopo

- **Trocar o blog do Gran pela API do WordPress** (o `PLANO_EVOLUCAO_AGENTICA.md` secao 3.4). A porta do Gran
  fica como esta, com LLM e tudo.
- **Deep-dive com LLM para estimar o salario do cargo** (plano antigo, secao 3.1). Decidido fora em 22/11/2026:
  mais caro e apoiado na peca que ficou um mes fora do ar.
- **Filtro nas areas EDUCACAO e SOCIOLOGIA_ARTES.** PED-04 limita a TI.
- **Apagar o `PciScraper` e o `PciNacionalScraper`.** Ficam como reserva (ADR-0001).
- **Rotacionar o token do Telegram** que vazou em 9 logs antigos (pendencia 2 do `HANDOFF.md`). E tarefa do
  Lucas, independente desta fase.
- **A busca `pesquisar_provas` do MCP** (provas anteriores com gabarito). Nao serve ao monitor.

## 7. Questoes em aberto

Nenhuma. As seis decisoes do dono estao na secao Pedido original e nas duas ADRs.

## 8. Ainda nao especificado (nevoa)

- **O que PED-01 ainda esconde.** O diagnostico de producao (ultimos 30 dias de log, contagem por fonte,
  estado do cron) nao foi lido: o acesso SSH ao notebook nao esta liberado para o agente. Esta fase entrega o
  script que coleta; a conclusao sobre o que mais esta quebrado vira ticket depois que o Lucas rodar.
- **Ajuste fino do corte e do limite de cargos.** O corte de R$ 10.000 e o limite de 10 cargos vem de uma
  medida de um dia (22/11/2026). Depois de algumas semanas de resumo semanal da para decidir se o corte sobe,
  se o limite de cargos desce ou se o municipal inflado precisa de regra melhor.
- **Termos de busca por area.** A lista de 13 termos de TI e a medida de hoje. Qual conjunto cobre melhor sem
  arrastar ruido ("redes", "software") so se sabe olhando algumas semanas de resumo.

## Revisoes

- 23/11/2026 r1 — criada, com as seis decisoes das duas rodadas de perguntas ja dentro.
- 23/11/2026 r2 — R-15 acrescentada ao escrever os tickets: avaliar as portas sem `regiao` poria
  selo de "nao verificado" em todo card do Gran. Banda de sanidade do `teto_de` (R$ 500 a
  R$ 80.000) registrada na secao 3.2.
