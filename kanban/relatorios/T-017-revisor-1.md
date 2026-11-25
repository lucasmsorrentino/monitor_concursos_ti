REPROVADO
Esteira: revisor · agy-neon (gemini-4-neon) · nível M+ · esforço high · 2026-11-25 00:48 → 2026-11-25 00:56 (8 min)
Resumo: A investigação reproduz com precisão quase integral a contabilidade (59 rechaves, `1629 + 71 = 1700`, `61 × +71`, 0 divergências nas 59 linhas conferidas no banco de produção e nos logs). Porém, o documento afirma falsamente na seção 3.1 que a 5ª colisão intrarrodada é «invisível» / «que o log não mostra», quando a própria fonte primária citada (`bot_concursos.log:L3693–3698`, `--dry-run` das `12:20:07`) identifica explicitamente a 5ª colisão: dois editais distintos da **`Prefeitura de Blumenau - SC`** (Região Sul, elegível) que colidiram sobre a linha nova **`id=1681`** (`run_20261124.log:L756–758`), engolindo o segundo edital em silêncio — e omitindo `id=1681` da lista de casos afetados para tickets seguintes na seção 5.
Arquivos: `docs/CONTABILIDADE-POS-DEPLOY.md` (dentro do `toca`; nenhum arquivo fora do `toca`).
Commits: `837dd77 docs: contabilidade pos-deploy, 59 rechaves e 4 colisoes de identidade`
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base (`2ea449f`, worktree destacado) `539 passed / 0 failed / 0 skipped` (`-rs`) · ponta (`837dd77`) `539 passed / 0 failed` (implementador afirmou `539 / 0` na base e `539 / 0` na ponta — bate) · lint: não configurado. Spike sem testes novos (plano de testes manda verificação em produção em `mode=ro`).
Testes que nascem verdes: nenhum (ticket de spike).
Desvios e riscos:
- A 5ª colisão intrarrodada não é invisível: `bot_concursos.log:L3693–3698` mostra dois `[NOVO]` consecutivos de `Prefeitura de Blumenau - SC`, que na rodada real (`run_20261124.log:L756–758`) colapsaram na linha `id=1681` (`pci_id=296321`, `elegivel`/`sul`, `2026-12-09`), silenciando um concurso elegível do Sul. Além de corrigir a afirmação falsa sobre a fonte primária, `id=1681` precisa constar na seção 5 para não ficar de fora dos tickets de reprocessamento.
- Referência menor de linha em `docs/CONTABILIDADE-POS-DEPLOY.md:312`: cita `UNIQUE(area, nome)` na «linha 24» de `src/database/manager.py` (que é a docstring do módulo); a restrição DDL real está em `src/database/manager.py:191`.
Pendências: corrigir `docs/CONTABILIDADE-POS-DEPLOY.md` conforme as exigências abaixo (incluir a 5ª colisão `id=1681` na resposta/seção 3.1 e na lista de tickets da seção 5).

---

## Spec

1. **Critérios de aceite (T-017):**
   - **As 30 linhas (→ 59) que mudaram de fonte, listadas por `id` com fonte antes/agora e explicação da diferença:** **ATENDIDO.** Todas as 59 linhas (`id <= 1641 AND fonte = 'pci_mcp'`) foram re-extraídas do banco de produção em `mode=ro` e batem campo a campo (`id`, `pci_id`, `elegibilidade`, `motivo_filtro`, `nome`, `link`) com **0 divergências**. A decomposição do saldo líquido (`−59` em TI + `+29` inserções novas de `pci` em `EDUCACAO` e `SOCIOLOGIA_ARTES` = `−30`) e a origem de `id=1128` (`gran → pci_mcp`) e `id=1446` (`pci_nacional → pci_mcp`, com a inferência sobre `id=1467` claramente marcada) foram confirmadas.
   - **Nenhuma linha foi perdida (`1629 + 71 = 1700`, sem subtração):** **ATENDIDO.** Reproduzido exatamente: `sqlite_sequence = 1712`, `COUNT(*) = 1700`, `id <= 1641` = `1629`, `1642..1712` = `71` (`42 TI + 18 EDUCACAO + 11 SOCIOLOGIA_ARTES`), 12 lacunas históricas (`18, 29, 31, 44, 49, 70, 82, 100, 101, 102, 103, 104`), 0 lacunas em `1642..1712`, 0 ocorrências de `Fundido id=` em `run_20261124.log`.
   - **Nenhum casamento errado (e lista de duvidosos para o Lucas):** **ATENDIDO para as 59 rechaveadas (`id <= 1641`), PARCIAL na contabilidade das colisões da rodada.** Conferi independentemente os nomes de criação de todas as 59 linhas nos logs históricos (`58/59` via `salvo no banco de dados` + `id=1434` CETESB via `[NOVO+INATIVO]` em `run_20261112.log:L132`) e desvios de monotonicidade de `pci_id` (`> 100` sobre a mediana dos vizinhos): para `id <= 1641`, as 4 colisões (`563`, `1131`, `1445`, `1587`) e os 2 duvidosos (`930`, `1113`) estão completos.
   - **Conciliação `61` do log × `+71` do banco (incluindo 56 filtrados):** **ATENDIDO.** Todas as 4 parcelas (`61 − 9 madrugada − 1 id=1445 + 18 filtrados inéditos + 2 [NOVO+INATIVO] = 71`) e a tabela `elegibilidade × motivo_filtro` foram reproduzidas no banco e em `run_20261124.log`.
   - **Fechar dizendo se a rechave é desejada ou defeito, e cada caso de defeito com `id` para ticket próprio:** **NÃO ATENDIDO INTEGRALMENTE (exigência).** O documento identifica corretamente a rechave de `fonte` como desejada (aderente a `docs/adr/0001-mcp-como-unica-porta-do-pci.md` e `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md`) e a colisão por `(area, nome)` como defeito real (`src/database/manager.py:191,256-281`). Porém:
     - Em `docs/CONTABILIDADE-POS-DEPLOY.md:227-234`, afirma que a 5ª colisão dos 106 itens do MCP (`106 → 101`) é *«1 invisível... a 5ª colisão, que o log não mostra»*.
     - Na fonte primária citada pelo próprio documento (`~/monitor_concursos_ti/logs/bot_concursos.log`, linhas 28 e 213), o ensaio `--dry-run` das `12:20:07` mostra explicitamente essa 5ª colisão em **`bot_concursos.log:L3693–3698`**: dois eventos consecutivos `✨ [NOVO] Prefeitura de Blumenau - SC detectado pela primeira vez.`. Na rodada real (`run_20261124.log:L756–758`), o primeiro item inseriu **`id=1681`** (`Prefeitura de Blumenau - SC`, `elegivel`/`sul`, `pci_id=296321`, `2026-12-09`) e o segundo colidiu por `(area, nome)` sobre `id=1681` em refresh silencioso — engolindo um segundo concurso **elegível do Sul** sem notificação.
     - Isso também explica por que `--dry-run` e rodada real empataram em `25 novos` (`dry-run`: `2× Blumenau + 0× UNESP 1445 [BACKFILL]` em `L3597`; real: `1× Blumenau + 1× UNESP 1445 [NOVO]` em `L658`).
     - Por tratar a 5ª colisão como invisível, o documento deixou **`id=1681` (`Prefeitura de Blumenau - SC`)** fora da seção 3.1 e fora da lista de casos afetados na seção 5 (`docs/CONTABILIDADE-POS-DEPLOY.md:326-332`), violando o critério 5 (*«Se for defeito, cada caso vira ticket proprio na fase seguinte, com o `id` do concurso»*) justamente num caso elegível da Região Sul.
   - **Sem token, chave, `chat_id` nem `T-0NNN`:** **ATENDIDO.** Verificado por regex sobre todo `docs/CONTABILIDADE-POS-DEPLOY.md` (`\bT-\d+`, `chat_id`, `bot\d+:`, `sk-`, `ghp_`, `AIza`, `token`): 0 ocorrências.

2. **Escopo:** `git diff --stat 2ea449f..HEAD` toca apenas `docs/CONTABILIDADE-POS-DEPLOY.md` (`+332` linhas), exatamente o campo `toca` do ticket. Nenhum arquivo de `src/`, `tests/`, `kanban/` ou banco foi tocado.

3. **Alinhamento com spec e ADRs:** Alinhado com `docs/adr/0001-mcp-como-unica-porta-do-pci.md` (rechave por `pci_id`) e `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (§2, §3.1, §3.5). Código citado conferido: `src/database/manager.py:411` (`fonte = COALESCE(?, fonte)`), `src/database/manager.py:256-281` (`buscar_registro`), `src/core/bot.py:1008-1010` (`inedito` sobre linha `filtrado`). Ressalva menor de referência: `docs/CONTABILIDADE-POS-DEPLOY.md:312` aponta `UNIQUE(area, nome)` na linha 24 de `src/database/manager.py` (docstring); o DDL real está na linha 191.

---

## Prova

Todas as medidas abaixo foram executadas independentemente nesta revisão (em `2026-11-25 00:49–00:54 -0300`, banco aberto exclusivamente em `file:...?mode=ro` via SSH `ssh -i ~/.ssh/fleet_ed25519 lucas@100.98.50.59`, e `pytest` local):

| Medição | Implementador | Revisor (medido) | Status |
| :--- | :--- | :--- | :--- |
| `pytest -q` base (`2ea449f`) | `539 passed / 0 failed` | `539 passed / 0 failed / 0 skipped` (`42.96s`, `-rs`, worktree destacado) | Bate |
| `pytest -q` ponta (`837dd77`) | `539 passed / 0 failed` | `539 passed / 0 failed` (`38.23s`) | Bate |
| `sqlite_sequence` / `COUNT(*)` / `MIN..MAX` | `1712` / `1700` / `1..1712` | `1712` / `1700` / `1..1712` (`mtime 2026-11-25 00:37:36`, `id > 1712 = 0`) | Bate |
| Split `id <= 1641` / `1642..1712` | `1629` / `71` | `1629` / `71` (lacunas `18, 29, 31, 44, 49, 70, 82, 100..104`) | Bate |
| Novas `1642..1712` por área/fonte/elegib. | `18 EDU, 11 SOC, 42 TI (17/4/3/12/6)` | `18 EDU, 11 SOC, 42 TI (17/4/3/12/6)` | Bate |
| Pré `id <= 1641` por área/fonte | `TI pci_mcp=59, pci=147, gran=107, pci_nacional=8` | Idêntico (`EDU 71/854`, `SOC 2/381`, `TI 107/147/59/8`) | Bate |
| Tabela das 59 rechaveadas (DB × doc) | 59 linhas | 59 linhas, **0 divergências** em `id`, `pci_id`, `elegibilidade`, `motivo_filtro`, `nome`, `link` | Bate |
| Diagnósticos antes/depois (`24/11 12:14` e `12:50`) | `1629 → 1700`, `9/1 → 61/23`, `1439/181/9 → 1411/180/8/101` | Conferidos nos dois arquivos `~/diagnostico-monitor-{antes,depois}-2026-11-24.txt` | Bate |
| `run_20261124.log` (`1163` linhas, `L566–761`) | `0` fusões; `56 [FILTRADO] (36+20) + 25 [NOVO] + 21 [TRANSICAO] = 102`, 4 dupes visíveis (`1131`, `1445×2`, `1587`) | Idêntico; todas as linhas citadas (`L54–55, L566, L582, L614, L658–661, L672, L708, L714, L732, L747`) e logs históricos (`0903..1121`) batem exatamente | Bate |
| **5ª colisão intrarrodada (`bot_concursos.log`)** | Afirmada como *«invisível... que o log não mostra»* (`docs/CONTABILIDADE-POS-DEPLOY.md:229-234`) | **Refutada pela fonte primária:** `bot_concursos.log:L3693–3698` (`12:20:07`) registra `2× [NOVO] Prefeitura de Blumenau - SC`, colidindo em **`id=1681`** (`run_20261124.log:L756–758`, `pci_id=296321`, `elegivel`/`sul`) | **Diverge** |

**Comandos executados:**
- Base (worktree destacado): `git worktree add --detach "$env:TEMP\t017b" 2ea449fa8d340b999e78cfdc925aace1683cdaa2` → `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → `git worktree remove`
- Ponta: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q`
- Produção (somente leitura): consultas `sqlite3.connect('file:.../concursos.db?mode=ro', uri=True)` e inspeção dos logs `~/diagnostico-monitor-{antes,depois}-2026-11-24.txt`, `~/monitor_concursos_ti/logs/run_20261124.log`, `~/monitor_concursos_ti/logs/bot_concursos.log` e `~/monitor_concursos_ti/logs/run_20260903..20261125.log` via `ssh -i ~/.ssh/fleet_ed25519 lucas@100.98.50.59`.

---

## Padrões

- **Vocabulário (`GLOSSARIO.md`):** conforme. Usa `porta`, `rodada`, `fase`, `teto do concurso`, `esfera`, `elegibilidade`, `corte fora do Sul`, `municipal inflado`. Nenhuma violação de termos «Evite» (a única ocorrência de `remuneracao` é dentro de uma URL do PCI na linha 147).
- **Idioma e regras do repo:** português do Brasil consistente, sem IDs `T-NNN`, sem segredos, sem alteração fora de `docs/`.
- **Cheiros de código:** não aplicável (entregável é documento de spike, sem código).

---

## Exigências para aprovação

1. **`docs/CONTABILIDADE-POS-DEPLOY.md` (resumo inicial L3–9, seção 3.1 L225–242 e seção 5 L320–332):**
   - Corrigir a afirmação em `L228–234` de que a 5ª colisão intrarrodada é «invisível» / «que o log não mostra». Registrar a evidência primária de `bot_concursos.log:L3693–3698` (`--dry-run` das `12:20:07`, dois `[NOVO]` consecutivos de `Prefeitura de Blumenau - SC`) cruzada com `run_20261124.log:L756–758` e o registro `id=1681` no banco (`pci_id=296321`, `elegivel`/`sul`, `2026-12-09`), deixando claro que 4 colisões ocorreram em linhas pré-existentes rechaveadas (`563`, `1131`, `1445`, `1587`, sendo 3 intrarrodada + 1 histórica) e 1 colisão intrarrodada ocorreu sobre uma linha nova (`1681`, `Prefeitura de Blumenau - SC`, engolindo um segundo edital elegível do Sul em silêncio — fechando exatamente as 5 colisões dos `106 → 101` itens do MCP).
   - Acrescentar **`id=1681` — Prefeitura de Blumenau - SC** (elegível / Sul; 2 editais distintos colidiram na rodada de 24/11 logo após a inserção) na lista de casos concretos afetados em `Tickets recomendados para a fase seguinte` (`L326–332`), e atualizar o resumo inicial (`L3–9`) para não omitir essa colisão.
2. *(Ajuste menor na mesma edição)* **`docs/CONTABILIDADE-POS-DEPLOY.md:312`:** apontar `src/database/manager.py:191` para o DDL real de `UNIQUE(area, nome)` (em vez de citar apenas a linha 24, que é a docstring do módulo).
