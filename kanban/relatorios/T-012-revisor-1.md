APROVADO
Esteira: revisor · agy-argon (gemini-4-argon) · nível M- · esforço medium · 2026-11-24 12:59 → 2026-11-24 13:02 (3 min)
Resumo: Revisão de T-012 concluída e aprovada. O documento `docs/DIAGNOSTICO-POS-DEPLOY.md` consolida com fidelidade todas as evidências antes e depois do deploy no notebook de produção, comprova a ausência de falso corte (zero concursos do Sul ou federais filtrados), traz as instruções de rollback na primeira linha, confere os 4 itens de fechamento da SPEC-001 seção 5 e lista as pendências da névoa (SPEC-001 seção 8) sem expor segredos nem IDs do quadro.
Arquivos: `docs/DIAGNOSTICO-POS-DEPLOY.md` (dentro do `toca`; fora do `toca`: nenhum)
Commits: 0805b12 docs: diagnostico pos-deploy, comparacao antes/depois do notebook de producao
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 539 passed / 0 failed · ponta 539 passed / 0 failed (implementador afirmou: base 539 passed / 0 failed · ponta 539 passed / 0 failed; condição: base `1dd94370a055792c59846bd532851b734bec9cb8` sem alterações de código, sem variáveis de ambiente especiais; lint não configurado)
Testes que nascem verdes: nenhum
Desvios e riscos: A confirmação visual do primeiro Telegram (evidência 6 e metade humana do item 4 da SPEC-001 seção 5) permanece honestamente sinalizada como pendente do dono (`◐`), enquanto todas as evidências da máquina (`exit=0`, `logs/.last_success_date` = `20261124`, zero falhas de envio e zero falsos cortes) estão provadas.
Pendências: Confirmação visual do Lucas sobre os cards recebidos no Telegram e desdobramento dos achados da seção "O que ainda está quebrado ou em aberto" em tickets da próxima fase.

## Spec

1. **O aceite foi cumprido?** Sim. Todos os itens do critério de aceite foram verificados contra as Notas do ticket e contra `docs/DIAGNOSTICO-POS-DEPLOY.md`:
   - **Seis evidências nas Notas do ticket:** presentes nas subseções 1 a 6 das Notas do Lucas (`.esteira/revisor.md:361-685`), finalizadas com `Recurso notebook: feito`.
   - **Notebook em `main` (`1dd9437`), em dia com `origin/main`, fora de `fix/ia-sem-login-e-zai`:** confirmado na evidência 2 e refletido em `docs/DIAGNOSTICO-POS-DEPLOY.md:22`.
   - **Primeira rodada real com `exit=0` e `logs/.last_success_date` com a data do dia (`20261124`):** confirmado na evidência 4 e registrado em `docs/DIAGNOSTICO-POS-DEPLOY.md:23,39-41`.
   - **Nenhum alerta de chave de LLM (`🔑`) no log:** `0` ocorrências na rodada real e nos últimos 30 dias (`docs/DIAGNOSTICO-POS-DEPLOY.md:28,41`).
   - **Nenhum concurso do Sul (`PR`, `SC`, `RS`) e nenhum federal como `filtrado` no `--dry-run` (critério bloqueador):** confirmado na evidência 3 e na rodada real (evidência 4), documentado em `docs/DIAGNOSTICO-POS-DEPLOY.md:45-48`. Entraram regularmente Blumenau-SC, IMA-SC, Câmara de São Francisco do Sul-SC, TRT 4-RS, UFMS, IFSP, IFG e IFFar.
   - **Filtrados com os dois motivos previstos (`abaixo_do_corte` e `municipal_inflado`):** 56 filtrados no `--dry-run` e na rodada real, sendo 36 `abaixo_do_corte` e 20 `municipal_inflado` (`docs/DIAGNOSTICO-POS-DEPLOY.md:37-41`).
   - **Comparação antes e depois em `docs/DIAGNOSTICO-POS-DEPLOY.md`:** instrução de rollback logo na abertura (`docs/DIAGNOSTICO-POS-DEPLOY.md:3-9`, atendendo à nota do arquiteto), tabela "Antes × depois" (`linhas 18-30`) com `HEAD`/branch, contagens do banco por área e por fonte (+71 linhas no total, `pci_mcp` com 101 linhas), entradas vs. filtrados (`linhas 31-43`), portas ativas por área (`linhas 50-60`) e erros recorrentes (`linha 27`).
   - **Fechamento com o que ainda está quebrado/em aberto:** seção "O que ainda está quebrado ou em aberto" (`docs/DIAGNOSTICO-POS-DEPLOY.md:77-99`), um achado por item com a respectiva seção de evidência (SPEC-001 seção 8).
   - **Ausência de token, chave ou `chat_id`:** verificado por busca automatizada; zero ocorrências.
   - **Quatro itens de "A SPEC fecha quando" (`docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:247-255`):** conferidos um a um com evidência em `docs/DIAGNOSTICO-POS-DEPLOY.md:62-75`.
2. **Passou do escopo?** Não. `git diff --stat main..HEAD` mostra exclusivamente `docs/DIAGNOSTICO-POS-DEPLOY.md | 99 ++++++++++++++++++++++++++++++++++++++++++`, idêntico ao campo `toca` (`fora_do_toca: []`).
3. **Bate com a spec?** Sim. Os números e fatos batem exatamente com as seções 4, 5 e 8 de `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` e com o roteiro `docs/DEPLOY-PCI-MCP.md`.

## Prova

4. **Os números são reais?** Sim.
   - **Suíte de testes (medida pelo revisor):** `& "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → `539 passed in 40.41s` (0 failed, 0 skipped), sem variáveis de ambiente especiais. Como o commit `0805b12` sobre a base `1dd9437` altera apenas `docs/DIAGNOSTICO-POS-DEPLOY.md`, a base `1dd9437` e a ponta `0805b12` têm a mesma árvore de código e os mesmos `539 passed / 0 failed` relatados pelo implementador.
   - **Checagens do plano de testes do ticket (medidas pelo revisor):**
     - `Select-String -Path "docs/DIAGNOSTICO-POS-DEPLOY.md" -Pattern "bot[0-9]{6,}:|ZAI_API_KEY|TELEGRAM_TOKEN"` → 0 ocorrências.
     - `Select-String -Path "docs/DIAGNOSTICO-POS-DEPLOY.md" -Pattern "T-0" -CaseSensitive` → 0 ocorrências.
     - Conferência aritmética dos diagnósticos colados: banco `1629 → 1700` (+71); áreas `TI 321→363 (+42)`, `EDUCACAO 925→943 (+18)`, `SOCIOLOGIA_ARTES 383→394 (+11)` (`42+18+11 = 71`); fontes `pci 1439→1411 (-28)`, `gran 181→180 (-1)`, `pci_nacional 9→8 (-1)`, `pci_mcp 0→101 (+101)` (`101-30 = 71`); dia `20261124` antes `novos=9 atualizacoes=1` + rodada `25+17+10 = 52 novos` e `21+1+0 = 22 atualizacoes` → depois `novos=61 atualizacoes=23`.
5. **O TDD foi de verdade?** Ticket nível `P-` do tipo `infra`, cujo único entregável é documentação (`toca: [docs/DIAGNOSTICO-POS-DEPLOY.md]`) e cujo plano de testes explicita que não há mudança de código. O histórico `git log --format="%h %s" main..HEAD` registra o commit único `0805b12 docs: diagnostico pos-deploy, comparacao antes/depois do notebook de producao`, adequado ao escopo.
6. **Os testes provam comportamento?** As verificações de evidência na costura de produção (`--dry-run`, rodada real, marcador `.last_success_date`, diagnósticos antes/depois e greps de segurança) provam diretamente os critérios de aceite do ticket.

## Padrões

7. **Regras e padrões do projeto:** Cumpridos integralmente. Texto e commit em português do Brasil, vocabulário alinhado ao `GLOSSARIO.md` (porta, área, rodada, teto do concurso, corte fora do Sul, municipal inflado, elegibilidade), sem segredos, sem IDs `T-NNN` em arquivo versionado e sem `git push`.
8. **Cheiros de código:** Nenhum cheiro identificado (entrega exclusivamente documental, enxuta e direta).
