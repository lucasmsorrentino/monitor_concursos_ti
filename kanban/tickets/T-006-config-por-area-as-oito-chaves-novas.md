---
id: T-006
titulo: Config por area: as oito chaves novas
tipo: codigo
nivel: M-
status: backlog
repo: principal
spec: [SPEC-001, R-14]
depende_de: []
toca: [config/loader.py, tests/test_config_loader.py, .env.example]
recursos: []
afinidade:
retornos: 0
---
# T-006 · Config por area: as oito chaves novas

## Contexto

A porta do MCP e o filtro de elegibilidade sao **por area**: PED-04 do pedido diz "para o cargo de ti
especificamente", entao EDUCACAO e SOCIOLOGIA_ARTES nao podem mudar de comportamento. Toda configuracao de
area do projeto entra por `MONITOR_TARGETS_JSON`, lido em `config/loader.py`, que ja normaliza listas de
palavras-chave, slugs, booleanos e o modo de primeira carga.

Este ticket acrescenta as oito chaves da SPEC-001 secao 3.6 e nada mais: quem as consome vem depois.

O padrao a copiar esta no proprio arquivo: `_normalize_keywords`, `_normalize_slugs`, `_normalize_bool` e,
sobretudo, `_normalize_modo_carga`, que mostra como tratar valor invalido — ela loga `warning` e cai no padrao
seguro, em vez de aceitar bobagem ou levantar.

## Critério de aceite

- [ ] `load_monitor_targets` passa a devolver, em cada alvo, as oito chaves da SPEC-001 secao 3.6, com os
      padroes de la: `pci_mcp` (`False`), `pci_mcp_cargos` (`[]`), `filtro_salarial` (`"desligado"`),
      `corte_fora_sul` (`0.0`), `ufs_sem_corte` (`["PR","SC","RS"]`), `esferas_sem_corte` (`["federal"]`),
      `cargos_total_inflado` (`10`), `resumo_filtrados` (`"nunca"`).
- [ ] As oito valem **nos dois caminhos** do loader: no modo multi-area (`MONITOR_TARGETS_JSON`) e no modo
      legado (`URL_ALVO`), cada uma com a sua variavel de ambiente no legado, no mesmo estilo de `PCI_SLUGS` e
      `PCI_NACIONAL`.
- [ ] `filtro_salarial` aceita `"desligado"` e `"ativo"`, sem olhar caixa nem espaco nas bordas. **Valor
      invalido loga `warning` e cai em `"desligado"`** (fail-open do `kanban/REGRAS.md`: nunca cair no modo
      agressivo), como `_normalize_modo_carga` ja faz com `pci_primeira_carga`.
- [ ] `resumo_filtrados` aceita `"nunca"` e `"semanal"`, com a mesma regra: invalido loga e cai em `"nunca"`.
- [ ] `corte_fora_sul` aceita numero ou string de numero (`10000`, `10000.0`, `"10000"`, `"10000.50"`) e sai
      como `float`. Valor nao numerico ou negativo loga `warning` e cai em `0.0`.
- [ ] `cargos_total_inflado` sai como `int`. Valor nao inteiro ou menor que 1 loga `warning` e cai em `10`.
- [ ] `ufs_sem_corte` e `esferas_sem_corte` aceitam lista ou CSV, como `_normalize_slugs` faz. UF sai em
      **maiuscula**; esfera sai em **minuscula**. Lista vazia explicita e respeitada (vazia significa
      "ninguem isento"), e **chave ausente** cai no padrao.
- [ ] `pci_mcp_cargos` aceita lista ou CSV, descarta vazios, e preserva a ordem e a caixa que o Lucas
      escreveu (o servidor normaliza a busca sozinho).
- [ ] **`pci_mcp` ligado com `pci_mcp_cargos` vazia loga `error`** dizendo que a porta nao vai render nada, e
      devolve `pci_mcp` como `False`: porta ligada sem termo seria uma fonte morta que o diagnostico de saude
      denunciaria todo dia.
- [ ] **`pci_mcp` ligado junto com `pci_slugs` ou `pci_nacional` loga `warning`** dizendo que as portas de
      HTML sao reserva (ADR-0001) e que rodar as duas duplica trabalho na mesma rodada. Nao desliga nada: a
      escolha e do Lucas.
- [ ] `.env.example` ganha um bloco comentado com as oito chaves, o que cada uma faz e um exemplo completo da
      area TI com a porta do MCP ligada, o filtro ativo, corte 10000 e os 13 termos de cargo.
- [ ] Alvo sem nenhuma das oito chaves continua funcionando exatamente como hoje.

## Plano de testes

Costura: `config.loader.load_monitor_targets`, que e a interface publica do modulo, com o ambiente montado por
`monkeypatch.setenv`, como `tests/test_config_loader.py` ja faz. Pega os padroes, a normalizacao, o
fail-open de valor invalido e os dois avisos. **Nao pega** quem usa as chaves.

Oráculo: a tabela da SPEC-001 secao 3.6, transcrita a mao no teste como tabela de padroes esperados. Os
valores de entrada sao literais escritos no teste.

Testes que nascem vermelhos em `tests/test_config_loader.py`:

- `test_alvo_sem_as_chaves_novas_recebe_os_padroes` — alvo minimo volta com as oito chaves nos padroes da
  spec, conferidos contra um dict literal.
- `test_padroes_valem_no_modo_legado` — com `URL_ALVO` e sem `MONITOR_TARGETS_JSON`, as oito aparecem.
- `test_filtro_salarial_aceita_ativo` — `"ativo"`, `"ATIVO"` e `" ativo "` saem `"ativo"`.
- `test_filtro_salarial_invalido_cai_em_desligado` — `"sombra"`, `"1"`, `""` e `None` saem `"desligado"`, e o
  log traz `warning`.
- `test_resumo_filtrados_invalido_cai_em_nunca` — `"diario"` sai `"nunca"` com `warning`.
- `test_corte_aceita_numero_e_string` — `10000`, `"10000"`, `10000.5` e `"10000.50"` saem como `float`.
- `test_corte_invalido_cai_em_zero` — `"dez mil"`, `-5` e `None` saem `0.0` com `warning`.
- `test_cargos_total_inflado_invalido_cai_em_dez` — `"muitos"`, `0` e `-1` saem `10` com `warning`.
- `test_ufs_sem_corte_aceita_csv_e_normaliza_caixa` — `"pr, sc,rs"` sai `["PR","SC","RS"]`.
- `test_ufs_sem_corte_vazia_explicita_e_respeitada` — `[]` sai `[]`, nao o padrao.
- `test_esferas_sem_corte_normaliza_para_minuscula` — `["FEDERAL","Distrital"]` sai
  `["federal","distrital"]`.
- `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` — `"analista de sistemas, informatica"` sai com os dois
  termos nessa ordem.
- `test_pci_mcp_sem_cargos_e_desligado_com_erro` — `pci_mcp: true` e `pci_mcp_cargos: []` devolve
  `pci_mcp is False` e loga `error`.
- `test_pci_mcp_com_slugs_avisa_mas_nao_desliga` — `pci_mcp: true` com `pci_slugs` preenchida devolve as duas
  ligadas e loga `warning`.
- `test_uma_area_filtrando_nao_afeta_a_outra` — dois alvos no JSON, TI com `filtro_salarial: "ativo"` e
  EDUCACAO sem a chave: a segunda volta `"desligado"`. E a garantia de PED-04.

## Fora do escopo

- Construir o `PciMcpScraper` ou chamar a elegibilidade. Outros tickets.
- Instanciar nada no `ConcursoBot` nem tocar `src/core/bot.py` e `main.py`.
- Escrever valor no `.env` ou no `monitor.env` da producao. O `.env.example` e documentacao; segredo e
  configuracao de producao quem grava e o Lucas (`kanban/REGRAS.md`).
- Validar se os termos de cargo existem no PCI. Isso e resposta do servidor, nao do loader.

## Notas do arquiteto

- **M− e nao P:** sao oito chaves com quatro tipos de normalizacao, duas delas com regra de fail-open, mais
  dois avisos cruzados entre chaves. E mais que encanamento, mas o padrao de cada peca ja esta no arquivo e os
  casos de borda estao todos escritos no aceite, entao nao chega a `+`.
- A diferenca entre o `error` do `pci_mcp` sem termos e o `warning` do `pci_mcp` com slugs e proposital:
  o primeiro e configuracao que nao funciona (fonte morta, alerta diario de fonte parada), o segundo e
  configuracao que funciona e custa mais do que precisa.
- `ufs_sem_corte: []` tem de ser distinguivel de chave ausente. Em JSON isso e lista vazia contra `None`;
  nao use "falsy" para decidir, porque `[]` e falsy e cairia no padrao.
- A ordem de `pci_mcp_cargos` importa so para o log ficar legivel; a uniao e por `id`. Mas preserve, porque e
  a ordem em que o Lucas escreveu e ele vai ler isso no log.
- Os 13 termos para o exemplo do `.env.example`, medidos em 22/11/2026 (108 concursos distintos de TI):
  `analista de sistemas`, `tecnologia da informacao`, `desenvolvedor`, `programador`,
  `tecnico em informatica`, `informatica`, `analista de dados`, `ciencia da computacao`, `banco de dados`,
  `redes`, `suporte tecnico`, `computacao`, `software`.
