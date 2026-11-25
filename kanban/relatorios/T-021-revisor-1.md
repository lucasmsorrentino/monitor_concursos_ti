APROVADO
Esteira: revisor · agy-neon (gemini-4-neon) · nível M+ · esforço high · 2026-11-25 17:02 → 2026-11-25 17:11 (10 min)
Resumo: A entrega cumpre integralmente os seis criterios de aceite de T-021 e os requisitos R-87 e R-88 da SPEC-003. Os testes na base (569) e na ponta (582) foram medidos independentemente e batem com o relatorio do implementador, o TDD foi provado no vermelho nos dois commits `test:`, e todas as 9 mutacoes aplicadas em worktree destacado foram pegas pela suite. Os dois arquivos fora do `toca` (`CLAUDE.md` e `README.md`) sao ajustes pequenos de documentacao devidamente justificados no relatorio.
Arquivos:
- src/intelligence/langchain_unit.py
- src/core/bot.py
- tests/test_intelligence_unit.py
- tests/test_concurso_bot.py
- CLAUDE.md (FORA do «toca» — justificado: documentacao da ordem dos alertas de fim de rodada e do tratamento de cota esgotada)
- README.md (FORA do «toca» — justificado: linha na tabela de comportamentos e atualizacao da tabela de testes)
Commits:
- 2043b97 chore: declara o atributo do instante de volta da cota na IntelligenceUnit
- 3d2889c test: cota esgotada com hora de reset encerra a rodada na primeira ocorrencia
- f65bda7 feat: cota com hora de reset encerra as chamadas a LLM da rodada
- 564ec37 test: alerta de cota nomeia a causa e a hora de volta, uma vez por dia
- 45699a6 feat: alerta proprio de cota esgotada, com a causa e a hora de volta
- 12362ca docs: descreve o tratamento da cota esgotada da LLM e o alerta dela
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → base (`d5fdae7`) 569 passed / 0 failed / 0 skipped · ponta (`12362ca`) 582 passed / 0 failed / 0 skipped (condicao: 0 variaveis `LLM_*`/`MONITOR_*`/`ZAI_*` no shell, sem filtro de marcador; `--collect-only -q`: 569 na base, 582 na ponta; lint nao configurado)
Testes que nascem verdes: 5 casos de guarda de fail-open ja declarados pelo implementador — `test_cota_sem_instante_de_reset_mantem_as_tres_tentativas` (4 casos parametrizados: `sem_instante`, `instante_em_prosa`, `data_impossivel`, `so_a_data`) e `test_reset_de_conexao_com_hora_nao_passa_por_cota`. Ambos foram validados nesta revisao por mutacao (`M3a` e `M3b`, ambas pegas).
Desvios e riscos:
- O ramo de fuso explicito (`volta.tzinfo` em `src/core/bot.py:672-675` e sufixo `(?:Z|[+-]\d{2}:?\d{2})?` em `src/intelligence/langchain_unit.py:64`) nao possui teste dedicado; no caso real do z.ai o instante chega ingenuo e esta coberto, e o comportamento defensivo esta alinhado a nota do arquiteto sobre parse tolerante sem inferir fuso.
- A escolha de alerta global (`por_area=False`) em `src/core/bot.py:688` copia o padrao de `llm_sem_login` e faz sentido porque a cota e compartilhada pelas tres areas; efeito esperado: apenas o chat da primeira area que encontrar a cota recebe o aviso do dia.
- Redacao menor em `src/core/bot.py:683`: «foram `<b>{erros}</b>` publicações nesta varredura» omite «sem leitura» (presente no alerta irmao `llm_sem_login` em `src/core/bot.py:653`), sem prejuizo de clareza porque a oracao anterior ja diz «fica sem leitura em todas as áreas».
Pendências:
- R-89 e R-90 (marcador em `logs/` e suspensao do catch-up horario em `scripts/run_daily.sh`), ja previstos em ticket proprio fora do escopo de T-021.
- `main.py:143` (`testar_llm`, fora do `toca`): continua reportando apenas `ai.falha_autenticacao` na linha final, sem mencionar `ai.cota_volta_em` (o erro ja aparece no log logo acima).

## Spec

1. **Criterios de aceite (6/6 cumpridos):**
   - **Curto-circuito na primeira ocorrencia e resto da rodada (R-87):** cumprido em `src/intelligence/langchain_unit.py:417-418` (`if self.falha_autenticacao or self.cota_volta_em:`) e `src/intelligence/langchain_unit.py:441-447`; provado por `tests/test_intelligence_unit.py:249-264` (`test_cota_esgotada_com_reset_nao_tenta_tres_vezes`, `test_cota_esgotada_curto_circuita_as_chamadas_seguintes_da_rodada`) e `tests/test_intelligence_unit.py:276-285` (`test_cota_reconhecida_pela_classe_do_erro`).
   - **Instante de reset extraido e legivel por quem chama:** cumprido em `IntelligenceUnit.cota_volta_em: datetime | None` (`src/intelligence/langchain_unit.py:133`, `441`) e `_instante_de_volta_da_cota` (`src/intelligence/langchain_unit.py:69-87`); provado por `tests/test_intelligence_unit.py:266-285` (`test_cota_esgotada_expoe_o_instante_de_reset`, `test_cota_reconhecida_pela_classe_do_erro`).
   - **Erro de cota sem instante legivel mantem 3 tentativas (fail-open):** cumprido em `src/intelligence/langchain_unit.py:69-87` (devolve `None` sem levantar excecao quando falta evidencia de cota, padrao de data+hora ou quando `datetime.fromisoformat` levanta `ValueError`); provado por `tests/test_intelligence_unit.py:287-315` (`test_cota_sem_instante_de_reset_mantem_as_tres_tentativas` com 4 casos e `test_reset_de_conexao_com_hora_nao_passa_por_cota`).
   - **Alerta nomeia a causa e a hora de volta, 1x por dia, sem usar «varredura incompleta» (R-88):** cumprido em `src/core/bot.py:665-690` com chave propria `"llm_sem_cota"` e `por_area=False` (copiando `"llm_sem_login"`), sem reutilizar `falha_autenticacao`; provado por `tests/test_concurso_bot.py:781-828` (`test_alerta_de_cota_nomeia_a_causa_e_a_hora_de_volta`, `test_alerta_de_cota_sai_uma_vez_por_dia`, `test_alerta_de_cota_nao_e_calado_pelo_alerta_de_login_do_mesmo_dia`).
   - **Area continua marcada como `falhou` (catch-up fora de escopo):** cumprido em `src/core/bot.py:667` (`self.falhou = True`); `scripts/run_daily.sh` e `LIMITE_ERRO_EXTRACAO` nao foram tocados; provado por `tests/test_concurso_bot.py:813` e `tests/test_concurso_bot.py:829-850` (`test_cota_marca_falha_mesmo_com_perda_abaixo_do_limite`).
   - **Suite verde e nenhum teste existente afrouxado:** verificado em diff completo (`d5fdae7..HEAD`); a unica alteracao em teste preexistente e `ai.cota_volta_em = None` na fixture `mock_deps` (`tests/test_concurso_bot.py:38`), identica a linha 37 (`ai.falha_autenticacao = None`) para evitar `MagicMock` truthy.

2. **Escopo (`git diff --stat d5fdae7..HEAD`):**
   - 6 arquivos alterados (`+286/-7`): os 4 do `toca` mais `CLAUDE.md` (`+4/-2`) e `README.md` (`+2/-1`), ambos sinalizados pelo script, restritos a documentacao no commit `docs:` (`12362ca`) e justificados no relatorio do implementador. Nenhum arquivo proibido foi tocado.

3. **Aderencia a SPEC-003 e ADRs:**
   - **SPEC-003 R-87 (`docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:152-153`):** atendido integralmente; credencial continua tendo precedencia (`src/intelligence/langchain_unit.py:434`), evitando que saldo zerado (`1113`) passe por cota.
   - **SPEC-003 R-88 (`docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:154-155`):** atendido integralmente; alerta global (`por_area=False`) segue o padrao existente de `llm_sem_login` (`src/core/bot.py:658`) como orientado nas notas do arquiteto.
   - **ADR-0004 (`docs/adr/0004-fuso-do-banco-e-do-log.md:25-29`):** nenhuma divergencia — `cota_volta_em` nao e gravado no banco, o marcador diario usa `date.today()` local em `_alerta_uma_vez_por_dia` (`src/core/bot.py:806`), e o instante da mensagem sai sem conversao inventada de fuso, com aviso explicito ao usuario («sem fuso declarado»), seguindo a nota do arquiteto.
   - Caso de borda sem teste: o ramo `volta.tzinfo` em `src/core/bot.py:672-675` (fuso `Z`/`±HH:MM` aceito em `src/intelligence/langchain_unit.py:64`) nao tem caso de teste. Nao bloqueia porque e um tratamento defensivo coerente com Python 3.12 (`Python 3.12.9` no `.venv`) e com a diretriz de parse tolerante.

## Prova

1. **Medicoes proprias vs relatorio do implementador:**
   - Condicao da medicao: 0 variaveis de ambiente com prefixo `LLM_`, `MONITOR_` ou `ZAI_`; sem filtro de marcador; Python 3.12.9.
   - **Base (`d5fdae741e8874d8a3f7e2d34f1dcd10a484ea1e`, em worktree destacado):**
     - `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → **569 passed / 0 failed / 0 skipped** (130.52s) — implementador: `569 passed / 0 failed` (bate).
     - `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest --collect-only -q -p no:cacheprovider` → **569 tests collected**.
   - **Ponta (`12362ca36c84d488ba2c2af7b7670a28c84963cb`):**
     - `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider` → **582 passed / 0 failed / 0 skipped** (118.65s) — implementador: `582 passed / 0 failed` (bate).
     - `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest --collect-only -q -p no:cacheprovider` → **582 tests collected**.
   - **Fechamento da conta:** `569 + 13 = 582` (9 casos novos em `tests/test_intelligence_unit.py` + 4 casos novos em `tests/test_concurso_bot.py`).
   - **Lint:** nao configurado no repositorio.

2. **Prova do TDD (log + execucao dos commits `test:` em worktrees destacados):**
   - Historico em `git log --reverse --stat d5fdae7..HEAD`: `chore:` (`2043b97`) → `test:` (`3d2889c`) → `feat:` (`f65bda7`) → `test:` (`564ec37`) → `feat:` (`45699a6`) → `docs:` (`12362ca`). Codigo e documentacao em commits separados.
   - **Vermelho da fatia 1 (`3d2889c`):** `pytest tests/test_intelligence_unit.py -q --tb=short -p no:cacheprovider` → `4 failed, 33 passed in 9.61s`, todos por assercao (`assert 3 == 1`, `assert 15 == 1`, `assert None == datetime(2026, 11, 26, 8, 11, 28)`, `assert 3 == 1`).
   - **Vermelho da fatia 2 (`564ec37`):** `pytest tests/test_concurso_bot.py -k TestCotaDaLlmEsgotada -q --tb=short -p no:cacheprovider` → `4 failed, 103 deselected in 2.24s`, todos por assercao (saia «Varredura incompleta», `assert 0 == 1`, `assert 0 == 1`, `assert False is True`).

3. **Qualidade dos testes e prova por mutacao (worktree destacado em `HEAD`, todas com `git diff --stat` confirmado nao vazio):**
   - Costura respeitada (`IntelligenceUnit.extrair_dados` e `ConcursoBot.executar()`); `TestCotaDaLlmEsgotada` executa a `IntelligenceUnit` real dublando apenas a fronteira da LLM (`chain_extracao.invoke`). Sem acoplamento a funcao privada (`_instante_de_volta_da_cota` nao e chamada diretamente nos testes), sem assercoes tautologicas, sem duble fora da fronteira.
   - Resultados das 9 mutacoes (pelo menos 1 por item comportamental do aceite + guardas nascidas verdes):
     - `M1a` (remover `or self.cota_volta_em` em `src/intelligence/langchain_unit.py:417`) → `rc=1` (`1 failed, 8 passed`).
     - `M1b` (remover `return` precoce em `src/intelligence/langchain_unit.py:447`) → `rc=1` (`3 failed, 6 passed`).
     - `M2` (retornar `datetime(2000, 1, 1, 0, 0, 0)` em `src/intelligence/langchain_unit.py:85`) → `rc=1` (`4 failed, 9 passed`).
     - `M3a` (retornar data fixa quando `not achado` e `e_de_cota` em `src/intelligence/langchain_unit.py:83`) → `rc=1` (`3 failed, 6 passed` — pega os 3 casos sem formato de data; `data_impossivel` e coberto pelo `except ValueError`).
     - `M3b` (remover guarda `if e_de_cota` em `src/intelligence/langchain_unit.py:81`) → `rc=1` (`1 failed, 8 passed` — pego por `test_reset_de_conexao_com_hora_nao_passa_por_cota`).
     - `M4a` (trocar `por_area=False` por `por_area=True` em `src/core/bot.py:688`) → `rc=1` (`1 failed, 3 passed`).
     - `M4b` (trocar chave `"llm_sem_cota"` por `"llm_sem_login"` em `src/core/bot.py:677`) → `rc=1` (`1 failed, 3 passed`).
     - `M4c` (remover data e hora do texto do alerta em `src/core/bot.py:680`) → `rc=1` (`1 failed, 3 passed`).
     - `M5` (remover `self.falhou = True` em `src/core/bot.py:667`) → `rc=1` (`2 failed, 2 passed`).

## Padrões

1. **Regras do projeto:**
   - Idioma pt-BR, identificadores e comentarios sem acento, texto voltado ao usuario com acento: em conformidade.
   - Vocabulario de `GLOSSARIO.md`: termos corretos nos nomes de funcoes, testes e commits (`rodada` usada nos nomes e commits; «varredura» aparece apenas no texto ao usuario em `src/core/bot.py:683,686` espelhando `llm_sem_login` em `src/core/bot.py:653,656`).
   - Sem nova dependencia em `requirements.txt`, sem chamada HTTP real nos testes, sem segredos, sem IDs `T-NNN` em codigo/docstrings/comentarios/docs (`git diff d5fdae7..HEAD | Select-String 'T-\d{3}'` retornou vazio), sem `push`.
   - Estilo consistente com `_e_falha_de_credencial`, `falha_autenticacao` e `llm_sem_login`, como pedido nas notas do arquiteto.

2. **Cheiros de codigo (julgamento, nenhum bloqueante):**
   - **Possivel generalidade especulativa (leve):** `src/intelligence/langchain_unit.py:64` e `src/core/bot.py:672-675` tratam offset/fuso explicito (`Z`/`±HH:MM` → `UTC{volta:%z}`) sem haver teste para esse ramo e sem o provedor atual emitir fuso. Conserto opcional: adicionar um caso parametrizado com `Z` ou `+08:00` se o suporte continuar desejado.
   - **Possivel codigo duplicado (muito leve):** inspecao de `cls.__name__` em `type(exc).__mro__` aparece em `src/intelligence/langchain_unit.py:50` (`_e_falha_de_credencial`) e `src/intelligence/langchain_unit.py:78` (`_instante_de_volta_da_cota`). Por ser uma expressao curta e direta, manter inline preserva a legibilidade.
