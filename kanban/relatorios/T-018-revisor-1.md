APROVADO
Esteira: revisor · glm-go (opencode-go/glm-5.3) · nível M- · esforço padrão · 2026-11-25 00:22 → 2026-11-25 00:28 (7 min)
Resumo: A ADR-0004 cumpre o aceite inteiro: nasce no arquivo do `toca`, no molde da ADR-0003, e cada afirmacao bate com o codigo que cita — conferi todas em `src/database/manager.py`, `src/utils/logger.py`, `src/core/bot.py` e `src/core/resumo_filtrados.py`. Ticket de documentacao, sem fatia de codigo: medi eu mesmo base e ponta, 539 passed / 0 failed nas duas, iguais aos numeros do implementador.
Arquivos: `docs/adr/0004-fuso-do-banco-e-do-log.md` (unico arquivo do diff `2ea449f..f839804`, +39 linhas; exatamente o `toca`, nada fora, `fora_do_toca` vazio confirmado)
Commits: `f839804` docs: registra ADR do fuso do banco em UTC e log em hora local
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base `539 passed / 0 failed` (2ea449f, worktree destacado, 39.48s) · ponta `539 passed / 0 failed` (f839804, 38.83s)
Testes que nascem verdes: nenhum — ticket `docs`, sem teste novo (o plano de testes declara «costura: nenhuma»)
Desvios e riscos: nenhum desvio. Nota leve, sem peso: o texto ancora o deslocamento em «3 horas em Curitiba» (`docs/adr/0004:34`), verdade enquanto `America/Sao_Paulo` seguir sem horario de verao; o fuso ja esta nomeado na linha 8, entao um eventual desvio futuro e conserto de texto.
Pendencias: nenhuma

## Spec — entregou o que foi pedido?

Aceite, item a item, com a evidencia que achei:

1. **Nasce no formato das existentes** — sim: titulo `# ADR-0004 — ...`, `**Data:**`, `**Estado:**`, `## Contexto`, `## Decisao`, `## Consequencias` (`docs/adr/0004-fuso-do-banco-e-do-log.md:1-6,12,31`), o molde da `0003-sonda-barata-separada-do-conserto.md:1-8` (as mais antigas, 0001/0002, nem tem Data/Estado).
2. **Quem grava em UTC** — `docs/adr/0004:18`: coluna `ultima_atualizacao` de `editais`, `DEFAULT CURRENT_TIMESTAMP` na criacao (`DatabaseManager._create_v3_table`, `src/database/manager.py:168`, DEFAULT na `:190`) e na migracao (`_migrate_to_v3`, `:197`, DEFAULT na `:220`, `COALESCE(ultima_atualizacao, CURRENT_TIMESTAMP)` na `:229`), e `CURRENT_TIMESTAMP` explicito no UPDATE (`:422`) e no INSERT (`:440`) de `atualizar_concurso` (`:353`). Formato `AAAA-MM-DD HH:MM:SS` e o que o comentario de `listar_filtrados` declara (`:334-337`).
3. **Quem grava em hora local** — `docs/adr/0004:19`: `setup_logger` (`src/utils/logger.py:36`) com `FormatterSemSegredos(logging.Formatter)` (`:25`) e `datefmt='%Y-%m-%d %H:%M:%S'` (`:43`). O formatter so sobrescreve `format` (`:32-33`), nao `formatTime`, entao vale o padrao do Python (`time.localtime`) — a afirmacao «por padrao no Python» esta correta. Arquivo `logs/bot_concursos.log` (`:47-48`) e console (`:56-57`), ambos com o mesmo formatador.
4. **Quem le qual** — `docs/adr/0004:20-23`: `DatabaseManager.listar_filtrados` (`manager.py:322`) compara texto `ultima_atualizacao >= ?` (`:346,349`) com `desde` em UTC; `ConcursosBot._enviar_resumo_semanal` (`src/core/bot.py:797`) calcula `desde` em UTC (`:835-837`) e gera a chave da semana com `date.today()` (`:819`) passado a `marcador_da_semana` (`src/core/resumo_filtrados.py:88`); marcadores diarios em `_alerta_uma_vez_por_dia` (`bot.py:756`, `date.today()` na `:776`) e comparacao civil de encerramento em `_prazo_encerrado` (`:1131`, `date.today() > date.fromisoformat(...)` na `:1140`; campo `data_fim_inscricao` ISO em `manager.py:10`).
5. **Assimetria proposital registrada** — `docs/adr/0004:33`: corte de sete dias em UTC por causa da coluna, marcador da semana em data local, «intencional e nao deve ser "corrigida"». Bate com `bot.py:819` + `bot.py:835` e com o comentario preexistente em `bot.py:833-834`.
6. **Regra curta para o futuro** — `docs/adr/0004:25-29`: data ao banco em UTC, texto ao Lucas em hora local, comparacao converte antes. Consistente com o que o codigo ja pratica.
7. **O que nao se vai fazer** — `docs/adr/0004:36-39`: sem migracao de dado, sem reescrever coluna antiga, sem coluna de fuso, log continua em hora local porque quem le e humano. Todos os pontos do aceite.
8. **Sem segredo e sem T-0NNN** — `grep "T-0"` na ADR: 0 ocorrencias; `grep -i "token|chave|chat_id|secret|password|Bearer"`: so «chave da semana» (`:22`), chave de controle do marcador, nao segredo.

**Escopo** — `git diff --stat 2ea449f..f839804`: 1 arquivo, +39, exatamente o `toca`. Nenhum horario mudado, `FormatterSemSegredos` intacto, sem toque em `kanban/`, `.env`, `logs/`, `data/` — o «fora do escopo» foi respeitado.

**Spec** — o ticket cita R-20 e R-22: li `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:224-231`. A ADR documenta a implementacao daquelas regras sem contradize-las; nenhuma ADR existente trata de fuso, nao ha conflito em `docs/adr/`.

## Prova — o verde vale?

- **Ponta (f839804):** `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → `539 passed in 38.83s` (0 failed, 0 pulados, sem marcadores, sem variavel de ambiente especial). Implementador alegou 539/0: confere.
- **Base (2ea449f = `git merge-base main HEAD`):** worktree destacado em pasta curta, `pytest -q` com o cwd do worktree (workdir externo e negado pelo harness, entao o pytest foi lancado via `python -c "os.chdir(<worktree>); subprocess.call([sys.executable, '-m', 'pytest', '-q'])"`) → `539 passed in 39.48s`. Implementador alegou 539/0: confere. Worktree removido apos a medida.
- **Conta fecha:** 539 base + 0 testes novos (ticket docs) = 539 ponta.
- **Verificacoes do plano de testes (oraculo e o codigo):** `grep "CURRENT_TIMESTAMP" src/database/manager.py` → 7 ocorrencias (`:23,190,220,229,335,422,440`), igual ao implementador; `grep "timezone\.utc|date\.today\(\)" src/core/bot.py` → 7 (`:513,520,528,776,819,835,1140`), igual; `grep "T-0" docs/adr/0004-fuso-do-banco-e-do-log.md` → 0, como o ticket exige.
- **TDD:** nivel P−, basta o log: um unico commit `docs:` (`f839804`), o esperado para ticket tipo docs sem fatia de codigo. Nenhum par `test:` → `feat:` a exigir; vermelho e mutacao nao se aplicam — nao ha codigo sob teste, e o valor da ADR provei lendo o oraculo afirmacao por afirmacao (bloco Spec).
- **Push:** a regra «nao faca push» foi respeitada — `origin/t/T-018-...` nao existe entre as referencias rastreadas (`git branch -r`).

## Padroes — esta escrito como o projeto escreve?

- **REGRAS.md (`kanban/REGRAS.md`):** sem violacao. Corpo em portugues do Brasil sem acento, como as tres ADRs irmas; sem segredo; sem `T-NNN`; diff longe de `kanban/`, `.env`, `logs/`, `data/`; commit `docs:` sozinho fecha o ciclo que o ticket pede (sem codigo, nao ha `test:`/`feat:`).
- **GLOSSARIO.md:** termos corretos — «rodada», «marcador», «area», «filtrado»; nada da coluna «Evite».
- **Formato:** segue o molde da 0003. Nota informativa, sem peso de veredito: as tres irmas trazem secao nominal de alternativas («Alternativas consideradas»/«Alternativas recusadas») e a 0004 nao traz; «O que nao se vai fazer» (`docs/adr/0004:36-39`) cumpre o papel — e a lista do que foi recusado e por que — e o aceite nao pede alternativas.
- **Cheiros de codigo:** nao se aplicam a documento; nada a apontar (nomes de funcao e coluna corretos em todas as citacoes).

## Estado final

`git status --porcelain` no worktree do ticket: limpo, como encontrei; o unico efeito desta revisao e este relatorio em `.esteira/`.
