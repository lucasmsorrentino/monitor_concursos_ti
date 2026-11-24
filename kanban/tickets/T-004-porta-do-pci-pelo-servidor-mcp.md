---
id: T-004
titulo: Porta do PCI pelo servidor MCP
tipo: codigo
nivel: M+
status: integrado
repo: principal
spec: [SPEC-001, R-03]
depende_de: []
toca: [src/scrapers/pci_mcp_scraper.py, tests/test_pci_mcp_scraper.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T17:53-03:00
branch: t/T-004-porta-do-pci-pelo-servidor-mcp
executor: script
executor_impl: glm
corpo_lancado: 7bfbac42eb14
fora_do_toca: []
ponta: b4307bc4011edbd865e70851f127afa7673975ce
executor_rev: agy-argon
executor_int: script
---
# T-004 · Porta do PCI pelo servidor MCP

## Contexto

O PCI publicou um servidor MCP oficial que devolve, ja estruturado, o que as duas portas de HTML do repo
(`PciScraper`, por pagina de cargo, e `PciNacionalScraper`, pela lista nacional) liam raspando HTML — mais o
que elas nunca tiveram: `regiao`, `cargos_total`, o teto do concurso e as datas de inscricao ja calculadas.
O porque da troca esta em `docs/adr/0001-mcp-como-unica-porta-do-pci.md`.

Este ticket entrega a **porta** nova (`GLOSSARIO.md`) como uma classe de scraper, no mesmo formato de item que
o `PciScraper` ja devolve, com quatro campos a mais. Ninguem a liga no bot aqui: a fiacao vem depois.

Endpoint: `https://mcp.pciconcursos.com.br/mcp`. **Sem autenticacao, somente leitura.** Verificado em 20, 22 e
23/11/2026. O contrato do item esta na SPEC-001 secao 3.1 e as regras na secao 4.1.

**As fixtures ja estao gravadas no repo**, em `tests/fixtures/pci_mcp/`, capturadas da resposta real em
23/11/2026. Nao chame o servidor: nem no teste (proibido pelo `kanban/REGRAS.md`) nem para conferir.

- `tools_call_analista_de_sistemas.json` — envelope cru, 9 itens, com um `NACIONAL` de `uf: null` (TRF3), uma
  universidade federal (UFMS) e um distrital (DPDF).
- `tools_call_tecnico_em_informatica.json` — 30 itens, com 8 do Sul, dois institutos federais e dois
  `"Cadastro de reserva ate R$ ..."` (um com `r` minusculo, outro maiusculo).
- `tools_call_sem_resultado.json` — o caso de `message`, com `data: []`.
- `tools_call_analista_de_sistemas.sse.txt` — a mesma carga do primeiro, enquadrada em SSE.

## Critério de aceite

- [ ] `src/scrapers/pci_mcp_scraper.py` expoe `PciMcpScraper`, subclasse de
      `src.scrapers.base_scraper.BaseScraper`, construida com a lista de termos de cargo:
      `PciMcpScraper(termos: list[str], tentativas: int = 3)`. `self.url` e o endpoint do servidor.
- [ ] `capturar_concursos() -> list[dict]` faz **uma chamada `buscar_por_cargo` por termo**, sem o parametro
      `uf` (sem `uf` a busca cobre todos os estados e os nacionais), e devolve a uniao dos itens.
- [ ] **Uniao por `id`** (R-01): o mesmo concurso visto por varios termos aparece **uma vez**, acumulando em
      `cargos` os cargos novos (sem repetir) e em `termos_origem` os termos que o trouxeram. E o que o
      `PciScraper` ja faz com slugs em `capturar_concursos`.
- [ ] Cada item sai no formato da SPEC-001 secao 3.1, com as chaves exatas de la, incluindo `ignorar: False`,
      `data_referencia: None`, `fonte: "pci_mcp"` e `pci_id` como **string**.
- [ ] `nome` leva a UF no sufixo: `f"{titulo} - {uf}"` quando `uf` existe, so `titulo` quando e `None`.
      Sem isso o `extrair_uf` e o `mesma_entidade` de `src/utils/text.py` nao casam o mesmo concurso vindo do
      Gran, e o dedup entre fontes quebra.
- [ ] `fase` vem das datas, nao do titulo: `datas.aberto` verdadeiro vira `"inscricoes_abertas"`;
      `datas.em_breve` verdadeiro vira `"edital_publicado"`; nenhum dos dois cai no
      `inferir_fase(noticia.titulo)` de `src/scrapers/pci_comum.py` (importe, nao recopie).
- [ ] `data_fim_inscricao` recebe `datas.fim` como vem (ja ISO `AAAA-MM-DD`); ausente ou vazio vira `None`.
- [ ] `vagas_salario` vai **cru**, sem parse. O numero e assunto de outro modulo.
- [ ] **Transporte** (R-02): `POST` JSON-RPC 2.0 com `"method": "tools/call"`, cabecalhos
      `Content-Type: application/json`, `Accept: application/json, text/event-stream` e
      `MCP-Protocol-Version: 2025-06-18`. A resposta e lida nas **duas** formas: JSON direto no corpo, ou SSE
      com uma linha `data: ` carregando o JSON. O payload util e o primeiro item de `result.content` com
      `type == "text"`, cujo `text` e um JSON em string que precisa de um segundo `json.loads`.
- [ ] **Termo sem resultado** (R-03): resposta com o campo `message` e `data` vazia e logada em `info` e
      segue sem erro. Nao se repete a chamada com o mesmo termo.
- [ ] **Termo que falha** (R-04): erro de rede, HTTP diferente de 200, JSON invalido ou resposta sem o
      `content` esperado sao logados em `warning` e a varredura **segue com os outros termos**.
      `capturar_concursos` so levanta excecao se **todos** os termos falharem, para a fonte poder ser
      diagnosticada como parada.
- [ ] **Aviso de truncamento** (R-06): termo cujo `meta.total` chega a 200 e logado em `warning` dizendo que o
      servidor cortou a lista. Nenhum termo de TI alcanca isso hoje (o maior media 69), mas `professor`
      devolve exatamente 200.
- [ ] Termo vazio ou so espaco e descartado na construcao, como `PciScraper` faz com os slugs.
- [ ] Nenhuma linha nova em `requirements.txt`: use `requests`, que ja esta la.

## Plano de testes

Costura: `PciMcpScraper.capturar_concursos()`, com o `POST` dublado (`mocker.patch` sobre o `requests.post`
que o modulo usa) devolvendo as fixtures de `tests/fixtures/pci_mcp/`. Pega a uniao por `id`, o mapeamento de
cada campo, a leitura de SSE, o termo sem resultado e o termo que falha. **Nao pega** a rede de verdade, nem o
que o bot faz com os itens.

Oráculo: as fixtures sao resposta real gravada do servidor; os valores esperados de cada campo estao escritos
a mao abaixo, lidos dessas fixtures. Nenhum esperado se obtem chamando o proprio mapeador.

Testes que nascem vermelhos em `tests/test_pci_mcp_scraper.py`:

- `test_capturar_mapeia_item_completo` — com a fixture de "analista de sistemas", o item de `id` 296654
  (Prefeitura de Italva) sai com `nome == "Prefeitura de Italva - RJ"`, `pci_id == "296654"`, `uf == "RJ"`,
  `regiao == "SUDESTE"`, `cargos_total == 53`, `fonte == "pci_mcp"`, `ignorar is False`,
  `data_referencia is None` e `vagas_salario` igual ao texto cru da fixture.
- `test_capturar_usa_link_da_noticia` — `link` e `noticia.link`, nao um link montado.
- `test_nome_sem_uf_fica_so_o_titulo` — o item `NACIONAL` do TRF3 (`uf: null`) sai com
  `nome == "TRF3 - Tribunal Regional Federal da 3a Regiao"`, sem sufixo nem " - None".
- `test_fase_vem_de_aberto` — item com `datas.aberto` verdadeiro sai `fase == "inscricoes_abertas"`.
- `test_fase_vem_de_em_breve` — item com `datas.em_breve` verdadeiro sai `fase == "edital_publicado"`.
- `test_fase_cai_no_titulo_sem_as_duas_datas` — fixture editada com `aberto` e `em_breve` falsos e titulo
  "... abre concurso publico ..." sai `fase == "edital_publicado"`, pela funcao de `pci_comum`.
- `test_data_fim_vem_de_datas_fim` — `data_fim_inscricao == "2026-12-16"` para o item de Italva.
- `test_uniao_por_id_nao_repete_concurso` — dois termos cujas fixtures compartilham um `id` devolvem esse
  concurso uma vez so, com os `cargos` dos dois somados sem repeticao e os dois termos em `termos_origem`.
- `test_le_resposta_em_sse` — com a fixture `.sse.txt`, o resultado e igual ao da fixture JSON.
- `test_termo_sem_resultado_nao_quebra` — a fixture de `message` nao contribui item e nao levanta.
- `test_um_termo_que_falha_nao_derruba_os_outros` — dois termos, o primeiro levantando erro de rede: o
  resultado traz os itens do segundo e o log registra `warning`.
- `test_todos_os_termos_falhando_levanta` — com todos falhando, `capturar_concursos` levanta.
- `test_json_invalido_conta_como_falha_do_termo` — corpo que nao e JSON e tratado como o termo que falha.
- `test_resposta_sem_content_de_texto_conta_como_falha` — envelope com `result.content` vazio idem.
- `test_avisa_truncamento_em_200` — fixture editada com `meta.total = 200` gera `warning` com a palavra
  "truncad" (ou equivalente declarado) na mensagem.
- `test_termo_vazio_e_descartado` — `PciMcpScraper(["", "  ", "informatica"])` faz **uma** chamada.
- `test_nao_envia_parametro_uf` — o corpo enviado em cada chamada tem `arguments` com a chave `cargo` e
  **sem** `uf`.

## Fora do escopo

- Ligar a porta no `ConcursoBot`, registrar a fonte em `saude_fontes` ou mexer em `src/core/bot.py`.
- Parsear o teto do `vagas_salario` ou classificar a esfera. Outros tickets.
- As outras quatro ferramentas do servidor (`listar_concursos`, `pesquisar_concursos`, `buscar_por_cidade`,
  `pesquisar_provas`). So `buscar_por_cargo` entra. `listar_concursos` corta em 30 de 152 e nao serve.
- Apagar ou alterar `PciScraper` e `PciNacionalScraper`. Eles ficam como reserva (ADR-0001).
- Sessao MCP com `initialize` e `mcp-session-id`. O servidor respondeu `tools/call` direto, sem handshake, nas
  tres verificacoes. Nao implemente handshake sem evidencia de que ele passou a ser exigido.
- Usar a biblioteca `mcp` do Python. Seria dependencia nova para um unico `POST`.

## Notas do arquiteto

- **M+ e nao G:** o transporte e um `POST` com duas formas de resposta e o mapeamento e campo a campo, com
  regra conhecida. O que faz o sinal `+` sao os detalhes onde se erra: o JSON dentro do JSON
  (`result.content[0].text`), o sufixo de UF no `nome`, e a fase vindo das datas. Tudo isso o revisor pega
  rodando os testes contra as fixtures, que e o criterio de ficar no nivel de baixo com `+`.
- **Nao use `get_html` e nao edite `base_scraper.py`.** O `get_html` e `GET` de HTML; aqui e `POST` de
  JSON-RPC com leitura de SSE. Herde da `BaseScraper` pelo logger e pelo `tentativas`, e escreva o laco de
  tentativa e backoff dentro do modulo novo, com um comentario dizendo por que nao reusa o `get_html`. Tocar
  o arquivo base alargaria o raio do ticket sem ganho.
- O servidor devolve as descricoes das ferramentas com mojibake, mas os **dados** vem em UTF-8 correto. Leia
  o corpo como UTF-8 e nao tente "consertar" acento: ja esta certo.
- O campo `id` da resposta e o mesmo numero de noticia que o `PciScraper` extrai do `nXXXXXX` da classe CSS.
  Por isso `pci_id` continua sendo a chave de dedup e a troca de porta nao pede migracao de dado. Mantenha-o
  como string, que e o tipo da coluna.
- A fixture `.sse.txt` foi montada a partir dos mesmos bytes da fixture JSON, de proposito: o teste de SSE
  afirma **igualdade** com o resultado do JSON, o que prova que a forma do transporte nao muda o item.
- Nenhuma fixture tem item **sem** salario legivel. Se precisar desse caso, edite uma copia da fixture no
  proprio teste; nao saia buscando outro termo no servidor.

## Histórico
- 2026-11-23 11:16 backlog → pronto · liberado: OK do Lucas em 23/11/2026
- 2026-11-23 11:16 pronto → fazendo · implementador · glm M+ high
- 2026-11-23 11:28 fazendo → entregue · implementador: ENTREGUE · relatório T-004-implementador-1.md · 12 min
- 2026-11-23 17:37 entregue → revisando · revisor · agy-argon M+ high
- 2026-11-23 17:45 revisando → aprovado · revisor: APROVADO COM RESSALVAS · relatório T-004-revisor-1.md · 9 min
- 2026-11-23 17:53 aprovado → integrando · integrador · script
- 2026-11-23 17:53 integrando → integrado · integrador: INTEGRADO · relatório T-004-integrador-1.md · 0 min
