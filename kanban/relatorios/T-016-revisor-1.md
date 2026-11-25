APROVADO COM RESSALVAS
Esteira: revisor · glm-go (opencode-go/glm-5.3) · nível M- · esforço padrão · 2026-11-25 00:13 → 2026-11-25 00:22 (10 min)
Resumo: A entrega cumpre os cinco itens do aceite do T-016: o bloco `== Config efetiva ==` imprime a porta `pci_mcp` com contagem de termos e o filtro salarial (`filtro_salarial`, `corte_fora_sul`, `resumo_filtrados`) com os padroes literais da SPEC-001 secao 3.6. Medir eu mesmo confirmou os numeros (base 539, ponta 544, conta fecha), o vermelho do `test:` e o valor dos testes por mutacao. Ressalvas: `docs/DIAGNOSTICO.md` secao 8 ficou defasado (fora do `toca`) e duas bordas leves sem teste.
Arquivos: scripts/diagnostico_producao.sh, tests/test_diagnostico_producao.py (ambos dentro do «toca»; nada fora)
Commits: e0319c2 test: exige porta pci_mcp e filtro salarial na config efetiva do diagnostico · e3978cb feat: imprime porta pci_mcp e filtro salarial na config efetiva do diagnostico
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q → base 539 passed / 0 failed · ponta 544 passed / 0 failed (medidos por mim; iguais aos alegados; 539 + 5 novos = 544)
Testes que nascem verdes: `test_config_quebrada_degrada_e_o_script_sai_com_zero` (guarda; conferido no commit `test:`; o `PY_CONFIG` ja degradava JSON ilegivel com saida 0 antes da mudanca, como o implementador declarou)
Desvios e riscos: sem commit `docs:`; `docs/DIAGNOSTICO.md:83-84` descreve a secao 8 sem `pci_mcp` nem o filtro (ressalva de processo/relatorio, marcada como tal: corrigir exige `toca` maior, decisao do arquiteto). Bordas sem teste: `pci_mcp` ligado com `pci_mcp_cargos` vazio, e o ramo string da contagem (abaixo, em Padroes).
Pendencias: nenhuma do ticket. Sugestoes de ticket novo no fim do relatorio; o arquiteto decide.

## Spec

1. **Porta `pci_mcp` no bloco (aceite 1)** cumprido: `scripts/diagnostico_producao.sh:95-105` imprime `porta pci_mcp: ligada (N termo(s))` ou `desligada`, no mesmo estilo de `pci_cargos` (`ligada (N slug(s))`, script:88). Prova: `test_config_mostra_a_porta_do_mcp_ligada_com_a_contagem_de_termos` (vermelho provado; mutacao A pega).
2. **Filtro salarial (aceite 2)** cumprido: `scripts/diagnostico_producao.sh:106-117` imprime `filtro_salarial`, `corte_fora_sul` e `resumo_filtrados`; chave ausente/vazia cai nos padroes `desligado`, `0`, `nunca` — conferidos contra `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:163-168` (secao 3.6). Prova: `test_config_mostra_o_filtro_salarial_com_corte_e_resumo` e `test_area_sem_as_chaves_novas_mostra_os_padroes_da_spec` (mutacao B pega).
3. **Sem segredo novo (aceite 3)** cumprido: as chaves novas sao config (termos, modo, corte, resumo), nao credencial. Measured: `bash scripts/diagnostico_producao.sh | grep -ciE "bot[0-9]{6,}:|ZAI_API_KEY=[^<]"` → `0`, na raiz do worktree, com sessao sem nenhuma variavel `MONITOR_*`. `test_a_saida_nova_nao_traz_segredo` cobre token, `chat_ids` e `ZAI_API_KEY` na saida nova.
4. **Somente leitura e exit 0 (aceite 4)** preservado: o diff so acrescenta `print`s no `PY_CONFIG`; a degradacao de JSON ilegivel (`invalido: JSON ilegivel`, script:67-71) e o `exit 0` do script (script:434) sao pre-existentes; chave ausente coberta por `test_area_sem_as_chaves_novas_mostra_os_padroes_da_spec` (codigo 0) e arquivo ausente por `test_script_sai_com_zero_em_arvore_minima`.
5. **Suite verde (aceite 5)**: 544 passed / 0 failed medidos por mim na ponta.
6. **Escopo**: `git diff --stat 2ea449fa..HEAD` toca exatamente os dois arquivos do `toca` (23 + 79 linhas, so insercoes); `fora_do_toca: []` confere. Nenhum comportamento extra visivel ao usuario alem do pedido.
7. Achado menor (nao exigencia, spec nao fechada pelo aceite): com `filtro_salarial` de valor invalido, a SPEC-001:163 manda o carregamento cair em `desligado`, mas o retrato imprime o valor bruto — o bloco mostra o JSON bruto, como ja fazia para as chaves pre-existentes (molde das tres portas). Coerente com o «relata, nao julga» do cabecalho e com a ADR-0003; registrado para o arquiteto, sem acao exigida.
8. Borda do aceite sem teste (nao pedida pelo plano): `pci_mcp` ligado com `pci_mcp_cargos` vazio imprime `ligada (0 termo(s))`; a SPEC-001:162 chama isso de erro de config, e o retrato relata sem julgar — ok pela ADR-0003, mas sem caso de teste.

## Prova

- **Minha medida** (condicao: Windows + Git Bash, `.venv` do repo principal, sessao sem variaveis `MONITOR_*`, sem marcadores; o `pytest.ini` aplica `-ra --strict-markers --tb=short`):
  - ponta: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → **544 passed / 0 failed** em 48.48s, no worktree do ticket;
  - base: mesmo comando apontado a um worktree destacado no merge-base `2ea449fa` → **539 passed / 0 failed** em 39.28s. Vale a medida: `tests/conftest.py:7-9` ancora o `sys.path` no proprio worktree, entao imports e script medidos sao os da base (nao ha pacote instalado no `.venv`).
  - Conta fecha: 539 + 5 testes novos = 544. Iguais aos numeros alegados pelo implementador.
- **TDD**: `git log --format='%h %s' main..HEAD` tem o par `test:` (e0319c2) → `feat:` (e3978cb), sem `docs:` (ver Desvios). Nivel P-, mas provei o vermelho mesmo assim: worktree destacado em e0319c2, `pytest -q tests/test_diagnostico_producao.py` → **4 failed / 13 passed**. As 4 falhas (`test_config_mostra_a_porta...`, `test_config_mostra_o_filtro...`, `test_area_sem_as_chaves...`, `test_a_saida_nova_nao_traz_segredo`) sao de assercao (a linha esperada nao existe na saida do script antigo), nao de coleta ou importacao; a 5a nasce verde (guarda declarada no relatorio do implementador).
- **Mutacoes** (worktree destacado em HEAD, cada mutacao conferida com `git diff` antes de rodar; worktrees temporarios removidos ao fim):
  - A — condicao da porta invertida (`if item.get("pci_mcp")` → `if not item.get("pci_mcp")`): **3 testes falham**;
  - B — os tres padroes trocados (`"desligado"`→`"inativo"`, `0`→`999`, `"nunca"`→`"jamais"`): **`test_area_sem_as_chaves_novas_mostra_os_padroes_da_spec` falha**.
  Os testes pegam codigo errado de proposito: o verde vale.
- **Qualidade dos testes**: costura pela interface publica (o script inteiro via `bash`, com raiz de mentira em `tmp_path`); oraculo literal escrito a mao no `monitor.env` de mentira (3 termos → `ligada (3 termo(s))`); nenhum duble, nenhum acesso ao banco por fora; nenhum dos tres defeitos (acoplado, tautologico, duble fora da fronteira) achado.

## Padroes

- **Vocabulario (GLOSSARIO.md)**: porta, area, termos — usados certos; commits e mensagens em portugues do Brasil; codigo sem acento (o diff segue o padrao do repo).
- **Regras do projeto**: sem dependencia nova; teste nao toca a rede (arvore falsa, subprocess com timeout); nenhum `T-NNN` em codigo/doc (grep vazio); nenhum segredo no diff; nada commitado em `kanban/` ou `.esteira/`; nenhum push.
- **Ressalva de processo/relatorio**: o ciclo TDD fecha com `docs:`, e o relatorio do implementador alega «Nao ha documentacao a atualizar» — inexato: `docs/DIAGNOSTICO.md:83-84` descreve a secao 8 do retrato listando so `gran`, `pci_cargos` e `pci_nacional`, e ficou defasado. O arquivo esta fora do `toca`, entao o implementador nao podia mexer sem parar; a alegacao e que inexata, nao a conduta. Marca pesa na retro, nao vira ticket por si.
- **Cheiros** (julgamento, cada um ressalva):
  - possivel codigo duplicado: o tripe `item.get(...)` → default → `print` repete tres vezes seguidas (`scripts/diagnostico_producao.sh:106-117`). Raso e no estilo do bloco vizinho; conserto: extrair helper `campo(item, chave, padrao)` se o bloco crescer com a sonda da SPEC-002.
  - possivel generalidade especulativa: o ramo `isinstance(raw_termos, str)` (`scripts/diagnostico_producao.sh:98-99`) aceita string separada por virgula em `pci_mcp_cargos`, caso que a SPEC-001:162 nao define (lista) e que nenhum teste cobre. Conserto: ou testa o caso ou apaga o ramo (degradaria para `ligada (0 termo(s))`, honesto tambem).

**Sugestoes de ticket novo** (o arquiteto decide):
1. «DIAGNOSTICO.md: secao 8 sem a porta pci_mcp e o filtro salarial» · nivel P- · toca: [docs/DIAGNOSTICO.md]
2. «Retrato do diagnostico: decidir o ramo string do pci_mcp_cargos (spec nao define; sem teste)» · nivel P- · toca: [scripts/diagnostico_producao.sh, tests/test_diagnostico_producao.py]

Estado final: `git status` do worktree do ticket limpo como encontrado (o relatorio em `.esteira/` nao e versionado); worktrees temporarios da revisao removidos.
