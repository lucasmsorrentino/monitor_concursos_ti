---
id: T-009
titulo: Porta do MCP ligada na rodada do bot
tipo: codigo
nivel: M+
status: integrado
repo: principal
spec: [SPEC-001, PED-02, R-07]
depende_de: [T-004, T-006]
toca: [src/core/bot.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T18:44-03:00
branch: t/T-009-porta-do-mcp-ligada-na-rodada-do-bot
executor: script
executor_impl: glm
corpo_lancado: a0445ee124bf
fora_do_toca: []
ponta: 03c9b7bffbd97c49e926bf5c36af08cd3a7cd31d
executor_rev: agy-argon
executor_int: script
---
# T-009 · Porta do MCP ligada na rodada do bot

## Contexto

O `PciMcpScraper` existe e a config por area ja traz `pci_mcp` e `pci_mcp_cargos`, mas ninguem os usa: a
rodada do bot continua lendo o PCI pelas duas portas de HTML. Este ticket liga a porta nova na rodada, como
**quarta fonte**, sem nenhum filtro ainda.

E uma fatia inteira e entregavel: com ela, a troca de porta pedida em PED-02 esta feita e o projeto pode ir
para producao mesmo que o filtro atrase. O filtro vem no ticket seguinte, no mesmo arquivo.

O `ConcursoBot.executar` ja trata tres fontes com a mesma forma: a fonte devolve candidatos, o diagnostico de
saude registra a materia-prima, e cada item passa por `_decidir_e_notificar`. A fonte 2 (`self.pci_scraper`) e
o modelo mais proximo, porque tambem devolve dado estruturado que nao passa pela LLM.

## Critério de aceite

- [ ] `ConcursoBot.__init__` cria `self.mcp_scraper = PciMcpScraper(<termos>)` quando a config do alvo traz
      `pci_mcp` verdadeiro, e `None` quando nao. Mesmo padrao condicional de `self.pci_scraper` e
      `self.nacional_scraper`.
- [ ] `executar()` ganha a fonte nova **entre a fonte 2 (pagina de cargo) e a fonte 3 (lista nacional)**.
      Essa posicao e obrigatoria: a fonte 2 alimenta o conjunto de links do PCI ja vistos na rodada e a fonte 3
      o **le** para nao reprocessar o que ja passou. Entrando depois da 3, os links do MCP chegariam tarde.
      Para cada item ela: conta em `validos`, registra o `link` nesse conjunto, e chama
      `_decidir_e_notificar(item, url_indice=item["link"])`, somando em `novos_cont` e `atualizados_cont` como
      as outras fazem.
- [ ] **Nao chama `enriquecer`.** A pagina de cargo nao trazia prazo e obrigava uma requisicao extra por item
      novo; o MCP ja devolve `data_fim_inscricao`. Essa economia e metade do motivo da troca (ADR-0001).
- [ ] O diagnostico de saude recebe a fonte com o nome `pci_mcp` (R-07), por
      `_avaliar_fonte("pci_mcp", <assinaturas>)`, com a assinatura de cada item no mesmo formato que a fonte 2
      usa (`pci_id` e `status`), e o diagnostico entra na lista que `_alertar_fontes_doentes` recebe.
- [ ] `_url_da_fonte` passa a devolver o endereco do servidor MCP para a fonte `pci_mcp`, para o alerta de
      fonte parada oferecer um endereco que existe.
- [ ] **Falha da fonte nao derruba a rodada inteira, mas conta como falha:** se `capturar_concursos` levantar
      (o que o `PciMcpScraper` so faz quando **todos** os termos falharam), a excecao e tratada, a area e
      marcada como falha (`self.falhou`), as outras fontes da rodada **seguem**, e o `main.py` termina com
      codigo diferente de zero, para o `run_daily.sh` nao gravar o marcador de sucesso e o catch-up horario
      tentar de novo.
- [ ] Area com `pci_mcp` desligado se comporta exatamente como hoje: nenhuma chamada ao servidor, nenhuma
      fonte nova no diagnostico, nenhuma linha nova no log.
- [ ] A suite inteira continua verde (296 testes em 23/11/2026) sem alterar teste existente, a nao ser para
      acomodar a fonte nova em assercao que conta fontes.

## Plano de testes

Costura: `ConcursoBot.executar()`, com todas as portas dubladas (`mocker.patch` nas classes de scraper e no
`TelegramNotifier`), como `tests/test_concurso_bot.py` ja faz. Pega a fonte entrando na rodada, os
contadores, o diagnostico de saude, o tratamento de falha e a area desligada. **Nao pega** o transporte HTTP
nem o que os itens significam.

Oráculo: itens de entrada escritos a mao no teste, no formato da SPEC-001 secao 3.1, e os contadores
esperados contados a mao a partir deles.

Testes que nascem vermelhos em `tests/test_concurso_bot.py`:

- `test_mcp_desligado_nao_instancia_scraper` — config sem `pci_mcp`: `bot.mcp_scraper is None` e nenhuma
  chamada.
- `test_mcp_ligado_instancia_com_os_termos` — config com `pci_mcp: True` e dois termos: o scraper e criado com
  esses termos, nessa ordem.
- `test_itens_do_mcp_passam_pela_decisao` — porta devolvendo tres itens novos: `_decidir_e_notificar` e
  chamada tres vezes e o contador de novos fecha em 3.
- `test_mcp_nao_chama_enriquecer` — a porta dublada nao recebe chamada de `enriquecer` para item novo.
- `test_mcp_registra_a_fonte_na_saude` — `_avaliar_fonte` e chamada com `"pci_mcp"`, e o diagnostico dela
  chega em `_alertar_fontes_doentes`.
- `test_url_da_fonte_do_mcp` — `_url_da_fonte("pci_mcp")` devolve o endereco do servidor.
- `test_links_do_mcp_entram_no_conjunto_de_vistos` — a lista nacional, rodando depois, nao reprocessa um item
  cujo `link` o MCP ja trouxe.
- `test_falha_total_do_mcp_marca_a_area_e_segue` — porta levantando excecao: o Gran ainda e varrido,
  `bot.falhou` fica verdadeiro, e a rodada nao levanta para fora.
- `test_mcp_e_gran_na_mesma_rodada_somam_contadores` — duas fontes com itens novos: os contadores somam as
  duas.
- `test_dedup_entre_mcp_e_gran_pelo_pci_id` — o mesmo concurso vindo do Gran e do MCP, com `nome` no estilo
  do PCI e o mesmo orgao, grava **uma** linha no banco.

## Fora do escopo

- Elegibilidade, filtro, selo, resumo semanal, colunas novas no banco. Tudo isso e do ticket seguinte, no
  mesmo arquivo.
- Desligar `pci_slugs` ou `pci_nacional` no codigo. Eles se desligam por configuracao, no deploy (ADR-0001),
  e o loader ja avisa quando estao ligados junto com o MCP.
- Mexer em `src/scrapers/pci_mcp_scraper.py` ou em `config/loader.py`: os dois chegam prontos. Se faltar algo
  neles, volte com `BLOQUEADO` em vez de contornar aqui.
- Trocar a porta do Gran, mexer na LLM ou no `main.py`.

## Notas do arquiteto

- **M+ e nao G:** a forma de acrescentar fonte esta escrita tres vezes no mesmo metodo e e so seguir. O sinal
  `+` e pelos tres detalhes que o copia-e-cola nao da: nao chamar `enriquecer`, alimentar o conjunto de links
  vistos na ordem certa (antes da lista nacional), e marcar `self.falhou` sem derrubar a rodada.
- **Este ticket e o irmao mais barato do T-010, de proposito.** Os dois tocam `src/core/bot.py`, entao correm
  em sequencia e nao em paralelo. Separa-los faz a troca de porta (PED-02) poder integrar e ir para producao
  sem esperar a parte que decide silencio, que e a de risco. Se este integrar e o seguinte atrasar, o projeto
  ja melhorou.
- O conjunto de links vistos (`links_pci_vistos` na rodada) existe porque a lista nacional e a pagina de cargo
  mostram o mesmo concurso. O MCP cobre os dois casos, entao alimentar o conjunto e o que impede trabalho
  dobrado quando as tres portas ficam ligadas na mesma rodada durante a transicao.
- Nao mova a ordem das fontes existentes nem renumere as que ja estao la nos comentarios: a nova entra no
  meio, entre a pagina de cargo e a lista nacional, porque e a lista nacional que consome o conjunto de links.
  O aceite cobra essa posicao, e o teste do conjunto de vistos e o que a prova.

## Histórico
- 2026-11-23 18:16 backlog → pronto · liberado: onda 0 revisada e integrada; segue para a fase de fiacao, docs e deploy
- 2026-11-23 18:16 pronto → fazendo · implementador · glm M+ high
- 2026-11-23 18:34 fazendo → entregue · implementador: ENTREGUE · relatório T-009-implementador-1.md · 19 min
- 2026-11-23 18:34 entregue → revisando · revisor · agy-argon M+ high
- 2026-11-23 18:43 revisando → aprovado · revisor: APROVADO COM RESSALVAS · relatório T-009-revisor-1.md · 9 min
- 2026-11-23 18:43 aprovado → integrando · integrador · script
- 2026-11-23 18:44 integrando → integrado · integrador: INTEGRADO · relatório T-009-integrador-1.md · 1 min
