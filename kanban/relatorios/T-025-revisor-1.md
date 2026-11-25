APROVADO
Esteira: revisor · glm-go (opencode-go/glm-5.3) · nível M- · esforço padrão · 2026-11-25 16:56 → 2026-11-25 17:03 (7 min)
Resumo: Conferi a seção 8 nova de `docs/DIAGNOSTICO.md` contra a saída real de `scripts/diagnostico_producao.sh`, que rodei nos dois modos (sem `MONITOR_TARGETS_JSON` e com um de exemplo, token falso incluído). O texto cita `pci_mcp` com contagem de termos e os três parâmetros de filtragem com os padrões da SPEC-001 §3.6; nenhuma outra seção mudou, nenhum segredo entrou e o dif não sai do `toca`. Os 569 testes passam na minha medida.
Arquivos: `docs/DIAGNOSTICO.md` (dentro do «toca»)
Commits: `c46481b` docs: atualiza secao 8 do DIAGNOSTICO.md com pci_mcp e filtro salarial
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 569 passed / 0 failed · ponta 569 passed / 0 failed (sem variáveis de ambiente e sem marcadores; lint não configurado)
Testes que nascem verdes: nenhum (ticket de documentação, sem teste novo)
Desvios e riscos: nenhum no entregue. Da minha medição: a base não rodou em worktree destacado porque o harness da sessão negou execução fora do diretório de trabalho (`Permission denied: external_directory`); vale por construção — ver Prova, item 4 — e o número fecha com o afirmado pelo implementador.
Pendências: nenhuma

## Spec — entregou o que foi pedido?

1. **Aceite, item a item:**
   - *Cita a porta `pci_mcp` com a contagem de termos*: `docs/DIAGNOSTICO.md:84-85` («`pci_mcp` quando a flag está ligada, com a contagem de termos de `pci_mcp_cargos`»). O script imprime `porta pci_mcp: ligada (N termo(s))` (`scripts/diagnostico_producao.sh:103`), contando termos não vazios de lista ou string por vírgula (`:95-101`). ✓
   - *`filtro_salarial`, `corte_fora_sul` e `resumo_filtrados` com os padrões da SPEC-001 §3.6*: `docs/DIAGNOSTICO.md:85-87` — `filtro_salarial` padrão `"desligado"` [`desligado` ou `ativo`], `corte_fora_sul` padrão `0`, `resumo_filtrados` padrão `"nunca"` [`nunca` ou `semanal`]. Conferido com a tabela em `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:157-168` (filtro_salarial `:163`, corte_fora_sul `:164`, resumo_filtrados `:168`); os defaults do script são os mesmos (`scripts/diagnostico_producao.sh:106-117`). O exemplo do sinal de problema («valor inválido de `filtro_salarial` caindo em `desligado`», `docs/DIAGNOSTICO.md:92-93`) espelha a SPEC-001:163. ✓
   - *O que o documento descreve bate com o que o script imprime hoje*: conferência manual minha, na íntegra e lado a lado, em Prova, item 6. ✓
   - *Nenhuma outra seção muda*: `git diff d5fdae7..HEAD` tem um hunk só, contido em `### 8. Config efetiva` (`docs/DIAGNOSTICO.md:81-94`); o contexto acima (seção 7) e abaixo (`## Dica de leitura`) está intacto. ✓
   - *Sem segredo no documento*: grep no documento por token longo, identificador de 8+ dígitos e `Bearer`/`api_key` → nada; o texto só cita `<omitido>`. ✓
2. **Escopo:** `git diff --stat d5fdae7..HEAD` → 1 arquivo, `docs/DIAGNOSTICO.md` (9 inserções, 5 remoções) — exatamente o `toca`; nenhum arquivo fora, nenhum comportamento que ninguém pediu.
3. **Spec:** os três parâmetros batem com a §3.6. R-20/R-22 (`SPEC-001:226` e `:230`) descrevem o efeito de `resumo_filtrados: "semanal"`; a seção 8 descreve o retrato que o script imprime e cita a opção `semanal` — suficiente e fiel. De quebra, o texto novo apaga dois desacertos do antigo: «`gran` sempre ligada» (o script imprime `porta gran: sem url configurada` sem URL) e «quando há slugs» vira «quando há `pci_slugs`», o nome real da chave.

## Prova — o verde vale?

4. **Números, medidos por mim** (worktree do ticket, sem variáveis de ambiente, sem marcadores):
   - ponta `c46481b`: **569 passed / 0 failed / 0 skipped** em 105,95 s;
   - base `d5fdae7` (= `main`; `git merge-base main HEAD` confere): tentei medir em worktree destacado, mas o harness negou execução fora do diretório da sessão (`Permission denied: external_directory`; worktree criado e removido limpo). Vale por construção: o único arquivo que difere base→ponta é `docs/DIAGNOSTICO.md`; `pytest.ini` coleta só `tests/`; nenhum teste referencia `DIAGNOSTICO` ou `docs/` (grep sem ocorrência) e nenhum varre a árvore do repo (o único `rglob` é sobre `tmp_path`, `tests/test_diagnostico_producao.py:214`). Logo base = ponta = 569/0, número idêntico ao afirmado pelo implementador;
   - conta fecha: 569 + 0 testes novos = 569. Lint: não configurado (cabeçalho do ticket), nada a rodar.
5. **TDD (nível P−: basta o log):** `git log --format='%h %s' d5fdae7..HEAD` → um único commit `docs:`, formato esperado para ticket de documentação (plano de testes: «Costura: nenhuma... sem teste novo»). Sem vermelho a provar, sem mutação a fazer — não há código no dif.
6. **Testes provam comportamento?** Sem teste novo; o oráculo do ticket era a conferência manual, que executei. Saída do script lado a lado com a seção 8:

   Sem `MONITOR_TARGETS_JSON` no ambiente (rodado na raiz do worktree):
   ```text
   == Config efetiva ==
   ausente: MONITOR_TARGETS_JSON (ambiente e /c/Users/Lucas/concursos-secrets/monitor.env)
   ```
   → casa com o sinal de problema «`MONITOR_TARGETS_JSON` ausente — a produção está no modo legado de URL única» (`docs/DIAGNOSTICO.md:93-94`).

   Com `MONITOR_TARGETS_JSON` de exemplo em memória (`pci_mcp` ligada com 2 termos, `filtro_salarial: ativo`, `corte_fora_sul: 10000`, `resumo_filtrados: semanal`, token falso e 1 `chat_ids`):
   ```text
   == Config efetiva ==
   MONITOR_TARGETS_JSON (de variavel de ambiente):
     area TI (Tecnologia da Informacao)
       porta gran: ligada
       porta pci_cargos: ligada (2 slug(s))
       porta pci_nacional: desligada
       porta pci_mcp: ligada (2 termo(s))
       filtro_salarial: ativo
       corte_fora_sul: 10000
       resumo_filtrados: semanal
       token: <omitido>
       chat_ids: <omitido> (1)
   ```
   → linha a linha com `docs/DIAGNOSTICO.md:83-89`: áreas ✓ · `gran` ligada pela URL ✓ · `pci_cargos` com contagem de slugs ✓ · `pci_nacional` pela flag ✓ · `pci_mcp` com contagem de termos ✓ · três parâmetros de filtragem ✓ · `token`/`chat_ids` substituídos por `<omitido>` (o token falso não vazou) ✓. Na sequência o script lista «chaves em <arquivo> (valores omitidos)» — os «**nomes** das chaves» do texto ✓.

## Padrões — está escrito como o projeto escreve?

7. **Regras do projeto:** texto que o usuário lê pode ter acento ✓; sem código no dif — nada de dependência, rede ou schema; nenhum ID de quadro (T-NNN) no documento ✓; commit só local — a branch do ticket não tem upstream e não há ref dela em `refs/remotes` ✓; o commit carrega só `docs/DIAGNOSTICO.md`, sem `.esteira/` nem segredo ✓. «Porta» é o termo do `GLOSSARIO.md` (evite: fonte, endpoint, scraper) — o texto usa ✓.
8. **Cheiros:** nenhum no dif; o parágrafo denso em parênteses segue o estilo das outras oito seções do documento. Observação menor, sem ação: «lidos do `MONITOR_TARGETS_JSON` do ambiente de produção» é atalho preexistente — o script lê da variável **ou** do arquivo de segredos e imprime a origem; fora do aceite deste ticket.
