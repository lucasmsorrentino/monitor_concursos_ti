ENTREGUE
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-25 16:49 → 2026-11-25 17:05 (17 min)
Resumo: `buscar_registro` passa a recusar, nos três fallbacks (link específico, `(area, nome)`, entidade), linha cujo `pci_id` é não nulo e diferente do item; linha de `pci_id` nulo continua casando e é rechaveada (ADR-0001). `_resolver_nome_sem_colisao` ganha o terceiro caso (mesmo órgão, dois concursos: não funde). A unicidade sai do `UNIQUE(area, nome)` de tabela para o índice único `idx_editais_identidade (area, nome, COALESCE(pci_id, ''))`, pela recriação da tabela que o dono autorizou (migração v7, uma transação, `id` e `sqlite_sequence` preservados, idempotente). Escrita que ainda assim bate na unicidade sai no log como `COLISAO DE IDENTIDADE`. ADR-0005 registra as duas opções e a escolha do dono.
Arquivos: src/database/manager.py · tests/test_database_manager.py · docs/adr/0005-identidade-do-concurso.md (todos no «toca»)
Commits:
  3deba35 test: identidade pelo pci_id e unicidade que admite dois editais do mesmo orgao
  47291be fix: o pci_id que discorda vence o nome, e a unicidade admite dois editais do mesmo orgao
  17537ba docs: ADR-0005, identidade do concurso e unicidade com o pci_id
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q (sem variável de ambiente nem marcador) → base (d5fdae7) 569 passed / 0 failed / 0 skipped · ponta (17537ba) 582 passed / 0 failed / 0 skipped. `pytest --collect-only -q` na ponta: «582 tests collected». Diferença = 13 testes novos. Lint: não configurado no projeto, não rodou.
  Vermelho visto no commit `test:` (tests/test_database_manager.py: 9 failed, 45 passed), todos por asserção ou pelo `IntegrityError` do corpo do código sob teste, nenhum de coleta/importação:
  - test_pci_id_diferente_nao_casa_por_nome / _por_link / _por_entidade → «assert {...} is None» (casava com a linha do 296044)
  - test_dois_editais_do_mesmo_orgao_viram_duas_linhas → «assert 1 != 1»
  - test_segunda_linha_nao_sobrescreve_o_prazo_da_primeira → «'2026-12-05' == '2027-01-04'» (o laço do IFSP reproduzido)
  - test_renomear_para_o_nome_do_outro_edital_nao_funde_as_linhas → falhou por asserção (a fusão apagava a linha do substituto)
  - test_colisao_irresolvivel_vira_erro_no_log_nao_silencio → «assert 1 == 0»
  - test_migracao_abre_a_unicidade_para_o_segundo_edital → «assert 1 == 4»
  - test_area_nome_is_unique (reescrito, ver desvios) → «sqlite3.IntegrityError: UNIQUE constraint failed: editais.area, editais.nome»
Testes que nascem verdes (guardas, declarados):
  - test_pci_id_casa_com_linha_sem_pci_id_e_rechaveia — R-81 é comportamento preservado da ADR-0001; guarda contra o filtro novo matar a rechave.
  - test_item_sem_pci_id_mantem_a_ordem_de_hoje — R-82, não-regressão do Gran e das portas de HTML.
  - test_migracao_preserva_id_estado_usuario_e_contagem — na base não há migração, então passa trivialmente; é guarda da recriação (compara cada linha com o literal escrito à mão, campo a campo, inclusive `seguindo`/`ignorado` e `ultima_atualizacao`).
  - test_migracao_rodada_duas_vezes_nao_muda_nada — compara os bytes do arquivo depois da 1ª e da 2ª abertura; na base também não há o que migrar.
  - test_unicidade_continua_barrando_nome_repetido_sem_pci_id — guarda do `COALESCE` (sem ele, duas linhas do Gran com o mesmo nome passariam).
Desvios e riscos:
  1. **Teste existente alterado: `TestSchemaCreation::test_area_nome_is_unique`** (tests/test_database_manager.py:99). Ele afirmava o texto `UNIQUE(area, nome)` no `CREATE TABLE`, que a SPEC-003 §4 item 1 (docs/specs/SPEC-003-identidade-do-concurso-e-cota-da-llm.md:184-185, «substituindo o UNIQUE(area, nome) de tabela») manda remover. O critério do ticket diz «nenhum teste existente afrouxado, renomeado ou apagado»; a spec vence o ticket. Mantive o nome e reescrevi o corpo para afirmar a unicidade nova por comportamento: nome repetido sem `pci_id` → IntegrityError; mesmo nome + mesmo `pci_id` → IntegrityError; mesmo nome com `pci_id` distintos → aceito. O revisor deve julgar se isso conta como afrouxar: a unicidade de fato ficou mais frouxa, por decisão do dono.
  2. **R-86, escopo do «erro nomeado».** Com a regra nova, `INSERT` não colide mais (todo par que bateria na unicidade é achado antes pela busca). O caminho que sobra é o `UPDATE` de nome; o teste usa um cenário real que o schema aceita (linhas do Gran «ifsp» e «IFSP», que a unicidade binária aceita e a busca NOCASE confunde). Para o cenário ser determinístico, a busca de conflito em `_resolver_nome_sem_colisao` ganhou `ORDER BY id` (antes era `fetchone()` sem ordem). O «alerta do dia» do R-86 é do `bot.py`, fora do «toca»: aqui só o log (é o que o critério do ticket pede).
  3. **`sqlite_sequence`.** A recriação devolve ao `sqlite_sequence` o maior id já emitido; sem isso, id de linha apagada em fusão voltaria a circular e botão antigo do Telegram apontaria para outro concurso. Coberto por `test_migracao_abre_a_unicidade_para_o_segundo_edital` (id esperado 4, com o 3 apagado).
  4. Banco novo agora nasce também com `idx_editais_pci` (antes só o recebia quem migrava pelo v5). Inócuo e idempotente.
  5. Docstrings das funções novas/alteradas foram no commit `fix:` (são contrato do código); a docstring do módulo (schema v7, ordem de identidade) foi no `docs:`.
  6. O prazo do edital 296044 (`2026-12-05`) foi escrito à mão: o repo não traz o prazo real dele. O 296538 (`2027-01-04`) e os links vêm da fixture `tests/fixtures/pci_mcp/tools_call_tecnico_em_informatica.json` e de `docs/CONTABILIDADE-POS-DEPLOY.md:162`.
  7. Para o revisor olhar: `_abrir_unicidade` em src/database/manager.py (transação explícita com `BEGIN`; se falhar, o `except` de `_ensure_schema` faz rollback e o banco fica no formato anterior, com o casamento novo ativo — nesse estado o segundo edital daria `COLISAO DE IDENTIDADE` no log, não silêncio).
Pendências:
  - CLAUDE.md (fora do «toca») ainda descreve a tabela como «schema v6» com `UNIQUE(area, nome)` na seção Database; precisa de uma linha para o v7 e a regra do `pci_id` discordante. Não editei.
  - Backup de `data/concursos.db` antes da primeira execução em produção (passo de deploy, ADR-0005).
  - Reparo das linhas que já colidiram (SPEC-003 §3.3) e o alerta do dia para `COLISAO DE IDENTIDADE` no `bot.py` (R-86, parte do alerta): outros tickets.
  - Sem push, conforme as regras do projeto.
