ENTREGUE
Esteira: implementador · sonnet (claude-sonnet-5-5) · nível M- · esforço padrão · 2026-11-25 16:49 → 2026-11-25 17:02 (13 min)
Resumo: erro de cota com instante de reset legivel agora encerra as chamadas a LLM da rodada na primeira ocorrencia e expoe o instante em `IntelligenceUnit.cota_volta_em` (`datetime | None`).
O bot manda um alerta proprio (chave `llm_sem_cota`, global, 1x/dia) com a causa e a hora de volta, no lugar de «Varredura incompleta», e mantem `falhou`. Sem instante legivel, seguem as tres tentativas.
O catch-up horario NAO foi suspenso (R-89, fora do escopo).
Arquivos:
- src/intelligence/langchain_unit.py
- src/core/bot.py
- tests/test_intelligence_unit.py
- tests/test_concurso_bot.py
- CLAUDE.md (FORA do «toca»: ele descreve a ordem dos alertas de fim de rodada e o tratamento de falha do backend, que ficariam errados; so documentacao)
- README.md (FORA do «toca»: uma linha nova na tabela de comportamentos e um ajuste na tabela de testes; so documentacao)
Commits (sem push, conforme a regra do projeto):
- 2043b97 chore: declara o atributo do instante de volta da cota na IntelligenceUnit
- 3d2889c test: cota esgotada com hora de reset encerra a rodada na primeira ocorrencia
- f65bda7 feat: cota com hora de reset encerra as chamadas a LLM da rodada
- 564ec37 test: alerta de cota nomeia a causa e a hora de volta, uma vez por dia
- 45699a6 feat: alerta proprio de cota esgotada, com a causa e a hora de volta
- 12362ca docs: descreve o tratamento da cota esgotada da LLM e o alerta dela
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider → base (d5fdae7) 569 passed / 0 failed · ponta (12362ca) 582 passed / 0 failed
- Nenhum teste pulado apareceu no `-rs`, na base nem na ponta. `--collect-only -q` na ponta: `582 tests collected`.
- Condicao: nenhuma variavel `LLM_*`, `MONITOR_*` ou `ZAI_*` no ambiente do shell (contagem 0), sem filtro de marcador.
- 13 casos novos (569 + 13 = 582): 9 em test_intelligence_unit.py (`TestCotaEsgotada`, contando 4 parametrizados) e 4 em test_concurso_bot.py (`TestCotaDaLlmEsgotada`).
- Vermelho da fatia 1 (so test_intelligence_unit.py): `4 failed, 33 passed`, os 4 por assercao (`assert 3 == 1`, `assert 15 == 1`, `None == datetime(...)`, `assert 3 == 1`).
- Vermelho da fatia 2 (so test_concurso_bot.py): `4 failed, 103 passed`, os 4 por assercao (saia «Varredura incompleta», 0 alertas de cota, `falhou is False`).
- Antes do commit de teste da fatia 2, corrigi um cenario meu: o caso «perda abaixo do limite» usava 19 blocos ignorados, que nao entram na base da taxa, e por isso dava 100% de perda. Passou a usar 19 editais validos, e o vermelho virou `assert False is True` em `falhou`.
- Lint: nao configurado.
- Nenhum teste existente foi afrouxado. A unica mudanca em codigo de teste ja existente e `ai.cota_volta_em = None` na fixture `mock_deps` (sem isso o atributo do MagicMock seria verdadeiro), alem dos imports.
Testes que nascem verdes: 5 casos, todos guardas de fail-open (descrevem o comportamento que ja existia e nao pode mudar). Nao os provei por mutacao.
- `test_cota_sem_instante_de_reset_mantem_as_tres_tentativas` (4 casos: sem instante, instante em prosa, data impossivel, so a data). ATENCAO: o ticket o lista entre os que nascem vermelhos, mas isso nao e possivel sem fabricar o vermelho, porque as tres tentativas sao o comportamento anterior.
- `test_reset_de_conexao_com_hora_nao_passa_por_cota`.
Desvios e riscos:
- Costura: a do ticket (`extrair_dados` e `ConcursoBot.executar()` com o notificador dublado). Nos testes de cota do bot a `IntelligenceUnit` e a real e so `chain_extracao` (a chamada a LLM) e dublada, o que prova a ligacao entre unidade e bot. Para isso o teste atribui `bot.ai` depois de construir o bot, porque a fixture substitui a classe. A excecao e a primeira metade do teste «nao e calado pelo alerta de login», que usa o `ai` dublado da fixture.
- Decisao minha, para o revisor olhar: o alerta de cota e GLOBAL (`por_area=False`), copiando o de credencial. A R-88 diz so «uma vez por dia, como os outros». O motivo: a cota e uma so para as tres areas. Efeito: so o chat da primeira area que bater na cota recebe o aviso.
- Como na credencial, o alerta de cota vem antes de «degradado» e de «cego», marca `falhou` mesmo com perda abaixo de 20% e cala o alerta por porta naquela rodada. `LIMITE_ERRO_EXTRACAO` nao foi tocado.
- O reconhecimento exige duas provas: erro de cota (classe `RateLimitError`, ou texto `RateLimitError` / `Limit Exhausted`) E `reset(s) at AAAA-MM-DD HH:MM[:SS]`. Outro formato de instante (tempo relativo, epoch, mensagem em outro idioma) cai nas tres tentativas. Nao conferi o formato da mensagem de cota do backend `claude-cli`.
- A checagem de credencial continua em primeiro lugar: um erro que case com as duas (ex.: saldo zerado 1113) segue como credencial.
- Um limite curto (por minuto) que traga instante nesse formato tambem encerra a rodada. E o que a R-87 pede, ao pe da letra.
- Fuso: o valor sai sem conversao. Com a mensagem do z.ai ele e ingenuo, e o alerta diz «sem fuso declarado». Offset ou `Z` colado no horario e preservado (nao ha teste desse caso; em Python anterior ao 3.11 alguns desses formatos virariam `None`, ou seja, tres tentativas). Sufixo separado por espaco (ex.: « UTC») e ignorado. O codigo nao compara o instante com o relogio.
- Ate o ticket do catch-up entrar, a varredura inteira continua rodando de hora em hora enquanto a cota estiver esgotada, agora com uma chamada falha a LLM por area em vez de tres tentativas por item. Este ticket sozinho nao resolve os cards repetidos de 25/11.
- A contagem «(539 tests)» no CLAUDE.md ja estava desatualizada na base (569); nao mexi.
Pendencias:
- R-89/R-90: marcador em `logs/` e suspensao do catch-up no `run_daily.sh` (ticket proprio). Pode consumir `cota_volta_em`, tratando o fuso como advisory.
- `main.py` (`testar_llm`, fora do «toca»): em falha de cota, a linha final diz «veja os avisos acima» em vez de nomear a causa. A causa aparece no log de erro logo acima.
- CLASS_DIAGRAM.md nao lista os atributos de causa da `IntelligenceUnit` (nem o de credencial); nao mexi.
