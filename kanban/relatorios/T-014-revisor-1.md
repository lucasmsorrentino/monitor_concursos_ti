APROVADO
Esteira: revisor · agy-neon (gemini-4-neon) · nível M+ · esforço high · 2026-11-25 00:01 → 2026-11-25 00:06 (6 min)
Resumo: A entrega cumpre integralmente os 9 itens do critério de aceite de T-014, respeita o campo `toca` sem alterar código de produção nem afrouxar testes existentes, e mata todas as 7 mutações sobreviventes (8 casos, desdobrando `datas.fim` vazia e ausente), confirmadas de forma independente em worktree destacado. A suíte completa fecha exatamente (`539 + 8 = 547 passed / 0 failed / 0 skipped`) e o código segue os padrões do repositório e do glossário.
Arquivos: `tests/test_esfera.py` (+32, no `toca`) · `tests/test_pci_mcp_scraper.py` (+65, no `toca`). Fora do `toca`: nenhum (`git diff --stat 2ea449f..HEAD`).
Commits: `84157cb` test: isola mutacoes sobreviventes da esfera (federal x distrital, transpetro, universidade federal sem fundacao e fail-open) · `105c19e` test: isola mutacoes sobreviventes da porta MCP (em_breve sem pista no titulo, datas.fim vazia/ausente e HTTP fora do 200)
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (venv padrão do repo, sem variáveis de ambiente ou marcadores extras, sem rede) → base `2ea449f` 539 passed / 0 failed (0 skipped, 539 collected) · ponta `105c19e` 547 passed / 0 failed (0 skipped, 547 collected). Lint: não configurado no repo.
Testes que nascem verdes: os 8 casos novos (`test_federal_e_distrital_nao_se_confundem`, `test_transpetro_e_federal`, `test_universidade_federal_sem_fundacao_e_federal`, `test_orgao_fora_da_lista_fechada_devolve_none`, `test_titulo_que_nao_infere_edital_publicado_usa_em_breve`, `test_data_fim_vazia_e_ausente_viram_none[fim-vazia]`, `test_data_fim_vazia_e_ausente_viram_none[fim-ausente]`, `test_resposta_fora_do_200`), por desenho explícito na nota do arquiteto (ticket de trava sem alteração de produção, validado por tabela de mutação).
Desvios e riscos: Nenhum desvio de contrato nem risco residual no escopo do ticket. Observações menores sem impacto no aceite: (1) o metadado do ticket cita `R-07`, mas o critério de HTTP != 200 da porta MCP corresponde a `R-04` (`docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:182-183`), corretamente exercitado; (2) o comentário em `tests/test_pci_mcp_scraper.py:286` reutiliza o termo `"varredura"` presente na docstring de `src/scrapers/pci_mcp_scraper.py:44` (em `GLOSSARIO.md:19`, o termo normativo é `rodada`; nomes de teste, identificadores e commits seguem o glossário).
Pendências: Nenhuma deste ticket. Mantidas fora do escopo, como definido pelo arquiteto: eventual ampliação da lista fechada de esfera (STJ, TSE, MPU, DETRAN), casamento não contíguo de `"Companhia ... do Estado"` e limpeza da entrada redundante `"fundacao universidade federal"` em `src/utils/esfera.py:70`.

## Spec

1. **Critério de aceite cumprido (9/9):**
   - **Inversão `_e_federal` ↔ `_e_distrital`** (`tests/test_esfera.py:297-302`): `test_federal_e_distrital_nao_se_confundem` usa `"TRE-DF - Tribunal Regional Eleitoral do Distrito Federal - DF"`, que ativa simultaneamente `_PADROES_FEDERAL` (`"tribunal regional eleitoral"`, `src/utils/esfera.py:75`) e `_PADROES_DISTRITAL` (`"do distrito federal"`, `src/utils/esfera.py:92`). Só devolve `"federal"` com a ordem correta em `src/utils/esfera.py:157-160`.
   - **Remoção de `"transpetro"`** (`tests/test_esfera.py:305-308`): `test_transpetro_e_federal` usa `"Transpetro"` (nome real do órgão como aparece na manchete em `tests/fixtures/pci_nacional.html:247`, sem `"Petrobras"` no mesmo texto), isolando `src/utils/esfera.py:83`.
   - **Remoção de `"universidade federal"`** (`tests/test_esfera.py:311-314`): `test_universidade_federal_sem_fundacao_e_federal` usa `"UFPR - Universidade Federal do Parana - PR"` (sem `"Fundacao"`), isolando `src/utils/esfera.py:69`.
   - **Fail-open com CETESB** (`tests/test_esfera.py:317-322`): `test_orgao_fora_da_lista_fechada_devolve_none` usa o nome nominal real do item `296537` da fixture `tools_call_analista_de_sistemas.json` (`"CETESB - Companhia Ambiental do Estado de São Paulo - SP"`), afirmando retorno `None` (`src/utils/esfera.py:167`).
   - **`datas.em_breve` sem pista no título** (`tests/test_pci_mcp_scraper.py:145-160`): `TestMapeamentoDoItem.test_titulo_que_nao_infere_edital_publicado_usa_em_breve` combina em memória as datas reais do item `295546` (`aberto=False, em_breve=True`) com o título real do item `296235` da fixture `tools_call_tecnico_em_informatica.json` (`"Prefeitura de São Julião - PI suspende concurso público"`, conferido `inferir_fase(...) is None`), isolando `src/scrapers/pci_mcp_scraper.py:214-215`.
   - **`datas.fim` vazia e ausente virando `None`** (`tests/test_pci_mcp_scraper.py:170-189`): `TestMapeamentoDoItem.test_data_fim_vazia_e_ausente_viram_none` é parametrizado em `fim-vazia` (`""`) e `fim-ausente` (chave removida), afirmando `data_fim_inscricao is None` em cada caso (`src/scrapers/pci_mcp_scraper.py:197`).
   - **`resposta.status_code != 200`** (`tests/test_pci_mcp_scraper.py:281-306`): `TestTermoQueFalha.test_resposta_fora_do_200` devolve HTTP 500 carregando corpo JSON-RPC válido (`tools_call_tecnico_em_informatica.json`, 30 itens) no 1º termo e HTTP 200 (`tools_call_analista_de_sistemas.json`, 9 itens) no 2º termo, validando que o termo com 500 é descartado (`len(itens) == 9`) e gera `WARNING` com `"HTTP 500"` (`src/scrapers/pci_mcp_scraper.py:149-150`).
   - **Suíte verde sem afrouxar testes existentes:** diff estritamente aditivo (`97 insertions(+), 0 deletions(-)`), `547 passed / 0 failed / 0 skipped`.
   - **Tabela das sete mutações no relatório do implementador:** presente, completa e verificada ponto a ponto abaixo.

2. **Escopo (`toca`):**
   - `git diff --stat 2ea449f..HEAD` mostra exclusivamente `tests/test_esfera.py` (+32) e `tests/test_pci_mcp_scraper.py` (+65), batendo com `toca: [tests/test_esfera.py, tests/test_pci_mcp_scraper.py]`.
   - Nenhum arquivo de produção foi alterado; nenhum termo foi adicionado à lista fechada da esfera; nenhum gancho fora do pedido foi introduzido.

3. **Alinhamento com spec e ADRs:**
   - Confere com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (§3.1 linhas 62-92 para `fase` e `data_fim_inscricao`; §3.3 linhas 104-111 para `esfera_de` e fail-open; §4.1 R-04 linhas 182-183 para falha HTTP != 200 seguindo com os outros termos; §5 linhas 235-245 para costuras e oráculo), `docs/adr/0001-mcp-como-unica-porta-do-pci.md` e `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`.
   - Nota de rastreabilidade: o frontmatter do ticket referencia `spec: [SPEC-001, R-07]`, mas R-07 (`SPEC-001:189-190`) refere-se ao registro em `saude_fontes`, enquanto o comportamento testado para HTTP != 200 está em **R-04** (`SPEC-001:182-183`). O teste cumpre corretamente o aceite e R-04.

## Prova

4. **Números medidos vs. relatório do implementador:**

| Medição | Implementador afirmou | Revisor mediu | Comando e condição |
| :--- | :--- | :--- | :--- |
| Base (`git merge-base main HEAD` = `2ea449f`) | `539 passed / 0 failed / 0 skipped` | `539 passed in 41.88s` (0 failed, 0 skipped; `539 tests collected in 1.39s`) | Worktree destacado `C:\Temp\t014-base` em `2ea449f`: `".venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q` (sem env/marcadores extras, sem rede) |
| Ponta (`105c19e`) — suíte completa | `547 passed / 0 failed / 0 skipped` | `547 passed in 44.68s` (0 failed, 0 skipped; `547 tests collected in 1.02s`) | Worktree do ticket em `105c19e`: `".venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q` |
| Ponta (`105c19e`) — `tests/test_esfera.py` | `77 passed` (73 + 4) | `77 passed in 0.29s` (0 failed, 0 skipped) | `".venv/Scripts/python.exe" -m pytest tests/test_esfera.py -q -rs` |
| Ponta (`105c19e`) — `tests/test_pci_mcp_scraper.py` | `22 passed` (18 + 4) | `22 passed in 0.18s` (0 failed, 0 skipped) | `".venv/Scripts/python.exe" -m pytest tests/test_pci_mcp_scraper.py -q -rs` |
| Lint | Não configurado | Não configurado | N/A |

- **Fechamento da conta:** `539 (base 2ea449f) + 4 (tests/test_esfera.py) + 4 (tests/test_pci_mcp_scraper.py: 1 em_breve + 2 fim parametrizado + 1 HTTP 500) = 547 (ponta 105c19e)`. Conta fecha exatamente.

5. **TDD / Processo:**
   - `git log --format='%h %s' 2ea449f..HEAD`: dois commits `test:` limpos e separados por módulo (`84157cb` para esfera, `105c19e` para porta MCP).
   - Pela nota do arquiteto, os testes deste ticket nascem verdes de propósito porque o código de produção já está correto e a prova é a tabela de mutação (sem `feat:`/`fix:`/`docs:`). Todos os 8 casos foram declarados como nascidos verdes no relatório do implementador.

6. **Qualidade dos testes e verificação independente das mutações:**
   - **Costura e defeitos:** todos os casos de esfera entram pela função pública `esfera_de` sem dublês; todos os casos da porta MCP entram por `PciMcpScraper(...).capturar_concursos()` dublando exclusivamente `src.scrapers.pci_mcp_scraper.requests.post` na fronteira HTTP (com fixtures reais e literais conhecidos). Zero acoplamento à implementação, zero tautologia, zero dublê fora da fronteira.
   - **Bateria independente de mutações** executada pelo revisor em worktree destacado `C:\Temp\t014-mut` (`HEAD` `105c19e`), com `git diff --stat` conferido antes de cada execução e `git checkout -- <arquivo>` após cada rodada (worktree removido ao final):

| # | Mutação aplicada (`arquivo:linha`) | Teste isolado (mutado) | Suíte do módulo (mutado) | Restaurado |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Inversão `_e_federal` ↔ `_e_distrital` (`src/utils/esfera.py:157-160`) | `1 failed` (`'distrital' == 'federal'`) | `1 failed, 76 passed` (só o novo falha) | `1 passed` |
| 2 | Remoção de `"transpetro"` (`src/utils/esfera.py:83`) | `1 failed` (`None == 'federal'`) | `1 failed, 76 passed` (só o novo falha) | `1 passed` |
| 3 | Remoção de `"universidade federal"` (`src/utils/esfera.py:69`) | `1 failed` (`None == 'federal'`) | `1 failed, 76 passed` (só o novo falha) | `1 passed` |
| 4a | Fail-closed no retorno final: `return None` → `return "estadual"` (`src/utils/esfera.py:167`) | `1 failed` (`'estadual' is None`) | `3 failed, 74 passed` (novo + 2 guardas antigas) | `1 passed` |
| 4b | Alargamento indevido: `"companhia do estado"` → `"do estado"` (`src/utils/esfera.py:108`) | `1 failed` (`'estadual' is None`) | `1 failed, 76 passed` (só o novo com CETESB falha) | `1 passed` |
| 5 | Remoção de `if datas.get("em_breve"): return "edital_publicado"` (`src/scrapers/pci_mcp_scraper.py:214-215`) | `1 failed` (`None == 'edital_publicado'`) | `1 failed, 21 passed` (só o novo falha) | `1 passed` |
| 6a | Remoção de `or None`: `datas.get("fim")` (`src/scrapers/pci_mcp_scraper.py:197`) | `1 failed, 1 passed` (`[fim-vazia]`: `'' is None`) | `1 failed, 21 passed` (só `[fim-vazia]` falha) | `2 passed` |
| 6b | Default não nulo: `datas.get("fim", "sem prazo") or None` (`src/scrapers/pci_mcp_scraper.py:197`) | `1 failed, 1 passed` (`[fim-ausente]`: `'sem prazo' is None`) | `1 failed, 21 passed` (só `[fim-ausente]` falha) | `2 passed` |
| 7 | Remoção de `if resposta.status_code != 200: raise RuntimeError(...)` (`src/scrapers/pci_mcp_scraper.py:149-150`) | `1 failed` (`38 == 9`) | `1 failed, 21 passed` (só o novo falha) | `1 passed` |

## Padrões

7. **Regras do projeto (`kanban/REGRAS.md`) e `GLOSSARIO.md`:**
   - Português do Brasil em nomes, docstrings, comentários e commits; identificadores e comentários sem acento (os únicos caracteres não-ASCII do diff são os dados reais das fixtures em `tests/test_esfera.py:322` e `tests/test_pci_mcp_scraper.py:154`).
   - Zero ocorrências de IDs do quadro (`T-NNN`) em código, docstrings, comentários ou commits.
   - Sem segredo, sem dependência nova, sem rede nos testes, sem alteração em arquivos proibidos e sem `push`.
   - Termos do `GLOSSARIO.md` respeitados em todos os nomes de teste, parâmetros e mensagens de commit. Apenas uma nota menor de redação: o comentário em `tests/test_pci_mcp_scraper.py:286` escreve `"varredura"` (`GLOSSARIO.md:19` prefere `rodada`), ecoando a frase já existente em `src/scrapers/pci_mcp_scraper.py:44`.
8. **Cheiros de código:** Nenhum cheiro identificado. Os testes novos seguem fielmente os helpers e o estilo já estabelecidos em ambos os arquivos, com comentários objetivos explicando exatamente a mutação que cada caso trava.
