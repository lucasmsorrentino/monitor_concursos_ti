ENTREGUE
Esteira: implementador · agy-neon (gemini-4-neon) · nível M- · esforço medium · 2026-11-25 00:56 → 2026-11-25 01:00 (5 min)
Resumo: Atendidas integralmente as duas exigências do retorno do revisor em `docs/CONTABILIDADE-POS-DEPLOY.md` (commit `0f3e714`), após verificação independente das fontes primárias no notebook de produção (`file:...?mode=ro`, `bot_concursos.log:L3693–3698`, `bot_concursos.log:L3597` e `run_20261124.log:L756–758`). A 5ª colisão intrarrodada (`id=1681`, `Prefeitura de Blumenau - SC`, `elegivel`/`sul`, `pci_id=296321`, prazo `2026-12-09`) foi documentada no resumo inicial, na seção 3 / 3.1 e na lista de tickets da seção 5, e a referência ao DDL de `UNIQUE(area, nome)` foi corrigida para `src/database/manager.py:191`.
Arquivos: `docs/CONTABILIDADE-POS-DEPLOY.md` (dentro do `toca`; nenhum arquivo fora do `toca`).
Commits:
- `837dd77` docs: contabilidade pos-deploy, 59 rechaves e 4 colisoes de identidade
- `0f3e714` docs: incluir 5a colisao (id=1681) e corrigir linha do DDL
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → base (`2ea449f`, medida pelo revisor na volta anterior) `539 passed / 0 failed / 0 skipped` · ponta (`0f3e714`, medida nesta rodada sem marcadores nem variáveis extras) `539 passed / 0 failed / 0 skipped` (`44.72s`) · lint: não configurado.
Testes que nascem verdes: nenhum (ticket de spike; verificação em produção somente leitura).
Desvios e riscos: nenhum desvio do escopo; banco de produção acessado exclusivamente em `file:...?mode=ro` sem escritas, `src/` e `tests/` intactos, sem `git push`. Permanece em aberto para julgamento humano do Lucas apenas a classificação dos 2 pares duvidosos (`id=930` UNIFEI e `id=1113` UERJ), já destacados na seção 3.2 do documento.
Pendências: abertura dos tickets da fase seguinte listados na seção 5 de `docs/CONTABILIDADE-POS-DEPLOY.md` (correção estrutural da identidade em `src/database/manager.py` e reprocessamento dos 5 casos de colisão confirmados — `563`, `1131`, `1445`, `1587` e `1681` — mais decisão sobre `930` e `1113`).

---

## Resposta do spike (em uma frase)

A porta do servidor MCP reescreveu a coluna `fonte` de **59** linhas pré-existentes (e não 30 — o delta líquido de `−30` escondia `+29` inserções novas de `pci` em `EDUCACAO` e `SOCIOLOGIA_ARTES`), nenhuma linha foi perdida (`1629 + 71 = 1700`), a rechave de `fonte` é **desejada**, mas a rodada expôs um **defeito real de identidade** por `(area, nome)` que causou **5 colisões comprovadas** (`id`s `563`, `1131`, `1445` e `1587` em linhas pré-existentes rechaveadas + `id=1681` `Prefeitura de Blumenau - SC` em linha nova elegível do Sul, cujo segundo edital foi engolido em silêncio), além de **2 pares duvidosos** (`930` e `1113`).

## Atendimento às exigências do revisor

1. **Exigência 1 — 5ª colisão intrarrodada (`id=1681`, `Prefeitura de Blumenau - SC`) em `docs/CONTABILIDADE-POS-DEPLOY.md`:**
   - **Verificação independente das fontes primárias (em `2026-11-25 00:57 -0300`, via `ssh -i ~/.ssh/fleet_ed25519 lucas@100.98.50.59`, `mode=ro`):**
     - Banco `editais` (`id=1681`): `(1681, 'TI', 'Prefeitura de Blumenau - SC', 'pci_mcp', '296321', 'elegivel', 'sul', '2026-12-09', 'inscricoes_abertas', 'https://www.pciconcursos.com.br/noticias/prefeitura-de-blumenau-sc-abre-concurso-publico-para-a-area-da-educacao', '2026-11-25 03:37:36')`.
     - `~/monitor_concursos_ti/logs/bot_concursos.log:L3693–3698` (`2026-11-24 12:20:07`, `--dry-run`): dois eventos consecutivos `✨ [NOVO] Prefeitura de Blumenau - SC detectado pela primeira vez.` (ambos `id=0`), além de `L3597` (`🧮 [BACKFILL] UNESP ...`) explicando o empate em `25 novos` entre `--dry-run` e rodada real.
     - `~/monitor_concursos_ti/logs/run_20261124.log:L756–758` (`2026-11-24 12:38:59–12:39:26`): apenas um `[NOVO]` inserido como `id=1681`, seguido imediatamente por `Prefeitura de Sales - SP` (`L759`), confirmando o refresh silencioso do segundo edital sobre `id=1681`.
   - **Alterações feitas:**
     - `docs/CONTABILIDADE-POS-DEPLOY.md:3–11` (resumo inicial): atualizado para incluir as **5** linhas afetadas por colisão comprovada (**4** pré-existentes `563`, `1131`, `1445`, `1587` + **1** linha nova `id=1681`, `Prefeitura de Blumenau - SC`, elegível / Sul).
     - `docs/CONTABILIDADE-POS-DEPLOY.md:210–264` (seção 3 e seção 3.1): removida a afirmação falsa de 5ª colisão «invisível» / «que o log não mostra»; documentada a evidência primária de `bot_concursos.log:L3693–3698` e `L3597` cruzada com `run_20261124.log:L756–758` e `id=1681` no banco; adicionada a linha **`1681`** na tabela de colisões comprovadas e explicitada a decomposição das 5 linhas (4 pré-existentes + 1 nova) e das 5 colisões intrarrodada (`106 → 101`).
     - `docs/CONTABILIDADE-POS-DEPLOY.md:332–355` (seção 5): incluído `id=1681` na descrição do impacto do defeito e na lista `Tickets recomendados para a fase seguinte` (`id=1681` — Prefeitura de Blumenau - SC, elegível / Sul).

2. **Exigência 2 — Referência do DDL de `UNIQUE(area, nome)` em `docs/CONTABILIDADE-POS-DEPLOY.md`:**
   - **Verificação:** conferido `src/database/manager.py:191` (`UNIQUE(area, nome)` no `CREATE TABLE`) e `src/database/manager.py:24` (docstring do módulo).
   - **Alteração feita:** `docs/CONTABILIDADE-POS-DEPLOY.md:334` agora aponta explicitamente `src/database/manager.py:191` (indicando que também é descrito na docstring da linha 24).

## Busca do mesmo padrão no repositório inteiro

Comando executado após a edição:
```powershell
git grep -n -i -E "invis|que o log n|linha 24|manager\.py:24|4 colis" -- docs/ src/ tests/
```

Saída obtida:
```text
docs/CONTABILIDADE-POS-DEPLOY.md:334:   `UNIQUE(area, nome)` (`src/database/manager.py:191`, descrito também na docstring da linha 24) e
src/scrapers/base_scraper.py:58:                    # aparecia no log do dia, invisivel a qualquer filtro de nivel.
src/scrapers/pci_scraper.py:9:invisivel. A recomendacao "ingerir o PCI por slug de cargo" esta escrita
```

Validação complementar de regex em `docs/CONTABILIDADE-POS-DEPLOY.md` (`\bT-\d+`, `chat_id`, `bot\d+:`, `sk-`, `ghp_`, `AIza`, `token`, `invis[ií]vel`, `que o log n[aã]o mostra`): **0 ocorrências** em todos os padrões.
