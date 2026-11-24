APROVADO
Esteira: revisor · agy-argon (gemini-4-argon) · nível M- · esforço medium · 2026-11-24 11:31 → 2026-11-24 11:34 (4 min)
Resumo: Os quatro documentos (`README.md`, `CLAUDE.md`, `CLASS_DIAGRAM.md` e `docs/DEPLOY-PCI-MCP.md`) entregam integralmente os critérios de aceite da fase de integração do PCI por MCP e filtro salarial (SPEC-001, ADR-0001 e ADR-0002). Todas as checagens de busca, sintaxe de comandos do roteiro, validação do JSON de configuração da área TI e execução da suíte de testes (539 passed) foram medidas e confirmadas sem desvios ou arquivos fora do escopo.
Arquivos: README.md · CLAUDE.md · CLASS_DIAGRAM.md · docs/DEPLOY-PCI-MCP.md (novo) — nenhum arquivo fora do «toca»
Commits: abd1e55 docs: quatro portas no README e CLAUDE.md, elegibilidade no diagrama e roteiro de deploy do PCI por MCP
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q → base 539 passed / 0 failed (medida pelo integrar em 3a335fc) · ponta 539 passed / 0 failed (38.05s)
Testes que nascem verdes: nenhum
Desvios e riscos: nenhum bloqueador. Observação menor não-bloqueante em `docs/DEPLOY-PCI-MCP.md:38-39`: os títulos das seções de `scripts/diagnostico_producao.sh` são impressos com inicial maiúscula e texto completo (`== Identidade ==`, `== Ultimo sucesso ==`, `== Saude por dia (ultimos 30 dias) ==`, `== Erros recorrentes ==`, `== Falha de credencial ==`, `== Banco ==`, `== Agendamento ==`, `== Config efetiva ==`), enquanto o texto explicativo os resume em minúsculas.
Pendências: execução do deploy no notebook pelo Lucas (próximo ticket); eventual nota no topo de `PLANO_EVOLUCAO_AGENTICA.md` (fora do `toca` deste ticket).

## Spec

1. **O aceite foi cumprido?** Sim, item por item nos quatro arquivos:
   - **`README.md`:**
     - Descreve as **quatro portas** (`README.md:35-49` e `116-126`), com `PciMcpScraper` como a porta padrão do PCI e frase explícita explicando que as duas portas de HTML (`PciScraper` e `PciNacionalScraper`) ficam como reserva, desligáveis por configuração (`pci_slugs`, `pci_nacional`), apontando `docs/adr/0001-mcp-como-unica-porta-do-pci.md` (`README.md:44-48`).
     - Traz a subseção de elegibilidade (`README.md:58-90`): o que ela decide, a tabela das nove regras (0 a 8, primeira que casa vence), a limitação central (*"o PCI publica o teto do concurso, não o salário do cargo"*) apontando `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md` (`README.md:63-67`) e `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (`README.md:88-89`).
     - O fluxo de dados (`README.md:129-163`) e a árvore do projeto (`README.md:193-252`) refletem as quatro portas, a etapa de elegibilidade (`salario.teto_de` + `esfera.esfera_de` → `elegibilidade.decidir`) e o resumo semanal dos filtrados.
     - Mantém apenas a versão em português com nota explícita no topo (`README.md:9-11`) informando que a versão em inglês saiu, conforme autorizado pelo quarto item do aceite do `README.md`.
   - **`CLASS_DIAGRAM.md`:**
     - Inclui `PciMcpScraper` (herdando de `BaseScraper` e ligado a `ConcursoBot`), `elegibilidade` (`SELO_NAO_VERIFICADO`, `decidir`), `Candidato`, `Politica`, `Decisao`, `salario` (`teto_de`), `esfera` (`esfera_de`) e `resumo_filtrados` (`montar`, `marcador_da_semana`), além das assinaturas atualizadas em `ConcursoBot` (`_avaliar_elegibilidade`, `_politica_de`) e `DatabaseManager` (`atualizar_concurso` com as 7 colunas v6 e `listar_filtrados`). Todas as relações conferem com `src/core/bot.py`, `src/core/elegibilidade.py`, `src/core/resumo_filtrados.py`, `src/scrapers/pci_mcp_scraper.py`, `src/utils/salario.py`, `src/utils/esfera.py` e `src/database/manager.py`.
   - **`CLAUDE.md`:**
     - Lista de portas e módulos atualizada para o estado novo com as quatro portas e numeração 1 a 9 em `Architecture` (`CLAUDE.md:49-80`), cobrindo `PciMcpScraper`, `elegibilidade.py`, `salario.py`, `esfera.py`, `resumo_filtrados.py`, as chaves por área de `config/loader.py` (`CLAUDE.md:130-142`) e as sete colunas do schema v6 em `Database` (`CLAUDE.md:150-168`).
     - Regra explícita em `Key Design Decisions` (`CLAUDE.md:216`) de que `elegibilidade` é decisão do bot e `estado_usuario` é decisão do usuário (Lucas), em colunas separadas que não se misturam.
     - Regra explícita (`CLAUDE.md:78` e `217`) de que dado do PCI nunca passa pela LLM.
     - Aponta para `SPEC-001`, `ADR-0001`, `ADR-0002` e `GLOSSARIO.md` sem repetir as tabelas normativas (`CLAUDE.md:9-11`, `66`, `71`, `130`, `167`).
   - **`docs/DEPLOY-PCI-MCP.md`:**
     - **Antes (`DEPLOY-PCI-MCP.md:29-42`):** rodar `bash scripts/diagnostico_producao.sh | tee ~/diagnostico-monitor-antes-$(date +%F).txt` e o que ver.
     - **Trazer o código (`DEPLOY-PCI-MCP.md:44-85`):** `git push origin main` no Windows (`origin/main` parado em `1eb1a1f` desde 22/10/2026), seguido no notebook por `git fetch origin`, `git checkout main` (saindo de `fix/ia-sem-login-e-zai`, pendência 1 do `HANDOFF.md`), `git pull`, `git log --oneline -5` e `git status`.
     - **Dependências (`DEPLOY-PCI-MCP.md:87-98`):** declara explicitamente que não há dependência nova e que `pip install` só seria necessário se a venv estivesse incompleta.
     - **Configuração (`DEPLOY-PCI-MCP.md:100-170`):** mostra somente o trecho do objeto TI para `MONITOR_TARGETS_JSON` em `~/concursos-secrets/monitor.env` (sem pedir para colar token ou chave), com `pci_mcp: true`, os 13 termos em `pci_mcp_cargos`, `filtro_salarial: "ativo"`, `corte_fora_sul: 10000`, `resumo_filtrados: "semanal"`, sem `pci_slugs` e sem `pci_nacional`, mantendo `EDUCACAO` e `SOCIOLOGIA_ARTES` intocadas, e inclui script Python de validação com `dotenv_values`.
     - **Ensaio (`DEPLOY-PCI-MCP.md:171-209`):** `python main.py --dry-run` e conferências com `grep` garantindo que nada é gravado nem enviado, que há filtrados apenas por `abaixo_do_corte` ou `municipal_inflado`, que nenhum concurso do Sul ou federal foi filtrado e que Sul e federal entram normalmente.
     - **Primeira rodada real (`DEPLOY-PCI-MCP.md:210-257`):** execução de `scripts/run_daily.sh` e conferência de `exit=0` no fim de `logs/run_$(date +%Y%m%d).log`, `logs/.last_success_date` com a data do dia, `0` ocorrências de `🔑` no log e primeiro Telegram da área TI sem ruído fora do Sul.
     - **Depois (`DEPLOY-PCI-MCP.md:258-268`):** rodar `bash scripts/diagnostico_producao.sh` novamente e comparar com o arquivo do passo 1.
     - **Como voltar atrás (`DEPLOY-PCI-MCP.md:270-280`):** em um único parágrafo, explica a troca de `filtro_salarial` para `"desligado"` e `pci_mcp` para `false`, repondo `pci_slugs` e `pci_nacional`, sem deploy de código e sem mexer no banco (colunas novas ficam e são ignoradas).
     - **O que o Lucas faz e o que não faz (`DEPLOY-PCI-MCP.md:282-290`):** explicita que credenciais quem grava é o Lucas e que nenhum passo pede a um agente que escreva ou manuseie segredos.

2. **Passou do escopo?** Não.
   - `git diff --stat 3a335fc..HEAD` toca exclusivamente os 4 arquivos listados no `toca` do ticket (`CLASS_DIAGRAM.md`, `CLAUDE.md`, `README.md`, `docs/DEPLOY-PCI-MCP.md`). `fora_do_toca: []`.

3. **Bate com a spec?** Sim.
   - A tabela das 9 regras em `README.md:69-79`, o selo `⚠️ salario nao verificado`, os 9 motivos fechados, a precedência, o contrato de 14 chaves de `PciMcpScraper._mapear`, as 8 chaves de configuração por área com seus padrões (`SPEC-001 §3.6`), as 7 colunas do schema v6 (`SPEC-001 §3.5`) e as regras `R-01` a `R-22` batem com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md`, `docs/adr/0001-mcp-como-unica-porta-do-pci.md`, `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md` e com o código integrado.

## Prova

4. **Os números são reais?** Sim. Medidas executadas nesta revisão (Windows, Python 3.12 da `.venv` do repositório principal, sem variáveis de ambiente extras nem marcadores de filtro):
   - **Base (`3a335fc`):** `git merge-base main HEAD` → `3a335fc38f6fe4c334a92a7e26417a99c5157037` (mesmo commit já medido pelo `integrar` no prompt: `539 passed in 41.46s`).
   - **Ponta (`abd1e55`):** `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → `539 passed in 38.05s` (implementador reportou `539 passed / 0 failed (62.08s)`). A conta fecha: 539 na base + 0 testes novos (ticket tipo `docs`) = 539 na ponta.
   - **Checagens do plano de testes medidas no bash:**
     - `grep -rn "PciMcpScraper" README.md CLASS_DIAGRAM.md CLAUDE.md` → 12 linhas (4 em `README.md`: linhas 39, 118, 142, 231; 4 em `CLASS_DIAGRAM.md`: linhas 22, 52, 182, 202; 4 em `CLAUDE.md`: linhas 9, 49, 53, 66).
     - `grep -c "pci_slugs" docs/DEPLOY-PCI-MCP.md` → `4` (maior que zero).
     - `grep -rn "T-0" README.md CLAUDE.md CLASS_DIAGRAM.md docs/DEPLOY-PCI-MCP.md` → vazio (`exit=1`).
     - `grep -rniE "(TELEGRAM_TOKEN|ZAI_API_KEY|LLM_API_KEY)\s*=\s*[^<\s]" docs/DEPLOY-PCI-MCP.md` → vazio (`exit=1`).
     - Validação dos comandos do roteiro: os 19 blocos `bash` de `docs/DEPLOY-PCI-MCP.md` passaram por `bash -n` com `exit=0`; o bloco JSON da área TI foi parseado com `json.loads` e validado (14 chaves, `pci_mcp: True`, 13 termos em `pci_mcp_cargos`, `filtro_salarial: "ativo"`, `corte_fora_sul: 10000`, `resumo_filtrados: "semanal"`, sem `pci_slugs`/`pci_nacional`); e `bash scripts/diagnostico_producao.sh` executou com `exit=0`.

5. **O TDD foi de verdade?** Sim.
   - Ticket do tipo `docs` (nível `P+`), sem alteração de código de produção nem de testes. `git log --format="%h %s" 3a335fc..HEAD` registra um único commit `docs:` (`abd1e55 docs: quatro portas no README e CLAUDE.md, elegibilidade no diagrama e roteiro de deploy do PCI por MCP`), conforme as regras para documentação.

6. **Os testes provam comportamento?** Sim.
   - Como o ticket não tem costura de código, o plano de testes define a verificação por leitura e busca textual contra o oráculo (código integrado e `SPEC-001`). Todas as 6 checagens do plano de testes passaram.

## Padrões

7. **Regras e padrões do projeto:** Cumpridos integralmente.
   - **Vocabulário (`GLOSSARIO.md`):** uso consistente de *área*, *porta*, *rodada*, *fase*, *teto do concurso*, *esfera*, *elegibilidade*, *corte fora do Sul*, *municipal inflado* e *fail-open*.
   - **Hierarquia normativa:** `GLOSSARIO.md` e `docs/adr/` > `SPEC-001` > ticket respeitada e declarada tanto no `README.md` quanto no `CLAUDE.md` (incluindo o aviso de que `PLANO_EVOLUCAO_AGENTICA.md` é plano antigo e não normativo).
   - **Segredos:** nenhum token, chave ou `chat_id` real nos arquivos tocados; `docs/DEPLOY-PCI-MCP.md` reforça a edição manual de `~/concursos-secrets/monitor.env` pelo Lucas.
   - **IDs do quadro (`T-NNN`):** ausentes de todos os arquivos versionados.
   - **Sem `push`:** o trabalho permanece apenas em commit local na branch `t/T-011-docs-readme-claude-md-e-roteiro-de-deplo`.

8. **Cheiros de código:** Nenhum cheiro identificado no diff.
