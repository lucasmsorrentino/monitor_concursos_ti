---
id: T-011
titulo: Docs: README, CLAUDE.md e roteiro de deploy
tipo: docs
nivel: P+
status: integrado
repo: principal
spec: [SPEC-001]
depende_de: [T-010]
toca: [README.md, CLAUDE.md, CLASS_DIAGRAM.md, docs/DEPLOY-PCI-MCP.md]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-24T11:34-03:00
branch: t/T-011-docs-readme-claude-md-e-roteiro-de-deplo
executor: script
executor_impl: glm-flash
corpo_lancado: c463c14c2850
fora_do_toca: []
ponta: abd1e55de223024c8427c8744506ff57017772dd
executor_rev: agy-argon
executor_int: script
---
# T-011 · Docs: README, CLAUDE.md e roteiro de deploy

## Contexto

O codigo da fase esta integrado: o PCI passa a ser lido pelo servidor MCP e a area TI silencia o que nao paga
fora do Sul. Tres documentos ficaram desatualizados por isso, e falta o roteiro que o Lucas segue para por
isso em producao no notebook.

O `README.md` descreve a arquitetura multi-fonte com tres portas. O `CLAUDE.md` e o contrato de trabalho do
projeto para qualquer agente que chegue. E o deploy nao pode ser improvisado: a configuracao de producao vive
em `~/concursos-secrets/monitor.env`, fora do repo, e quem a edita e o Lucas.

## Critério de aceite

### `README.md`

- [ ] A secao de arquitetura passa a descrever **quatro** portas, com a do servidor MCP como a porta padrao do
      PCI, e diz em uma frase que as duas de HTML ficam como reserva, desligaveis por configuracao, apontando
      `docs/adr/0001-mcp-como-unica-porta-do-pci.md`.
- [ ] Ganha uma subsecao curta sobre a elegibilidade: o que ela decide, a tabela das nove regras (ou o
      ponteiro para a SPEC-001 secao 4.2), e a frase que explica a limitacao central — o PCI publica o teto do
      concurso, nao o salario do cargo — apontando `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`.
- [ ] O diagrama ou a lista de fluxo, se houver, reflete a porta nova.
- [ ] As duas versoes do texto (a inglesa e a portuguesa recolhivel) ficam coerentes entre si. Se manter as
      duas custar mais do que vale, mantenha so a portuguesa e diga no topo que a inglesa saiu.

### `CLASS_DIAGRAM.md`

- [ ] Traz `PciMcpScraper`, `elegibilidade`, `salario`, `esfera` e `resumo_filtrados` com as relacoes que o
      codigo integrado tem.

### `CLAUDE.md`

- [ ] A lista de fontes e a de modulos refletem o estado novo.
- [ ] Ganha a regra de que a elegibilidade e a decisao do bot e `estado_usuario` e a do Lucas, e que as duas
      nao se misturam.
- [ ] Ganha a regra de que dado do PCI nao passa pela LLM.
- [ ] Nao repete a SPEC nem as ADRs: aponta para elas.

### `docs/DEPLOY-PCI-MCP.md`

O roteiro que o Lucas executa. Cada passo com o comando pronto para copiar e o que ele deve ver se der certo.

- [ ] **Antes:** rodar `bash scripts/diagnostico_producao.sh` e guardar a saida, para haver um antes e um
      depois.
- [ ] **Trazer o codigo:** `git push` de `main` do Windows (o `origin/main` esta atras desde 22/10/2026),
      depois no notebook `git fetch`, `git checkout main`, `git pull`, e conferir o `HEAD`. Inclui voltar o
      notebook de `fix/ia-sem-login-e-zai` para `main`, que era a pendencia 1 do `HANDOFF.md`.
- [ ] **Dependencias:** dizer explicitamente que **nao ha** dependencia nova, e que `pip install -r
      requirements.txt` so e necessario se a venv estiver incompleta.
- [ ] **Configuracao:** o bloco exato para o `MONITOR_TARGETS_JSON` do `~/concursos-secrets/monitor.env`, com
      a area TI usando `pci_mcp: true`, os 13 termos de cargo, `filtro_salarial: "ativo"`,
      `corte_fora_sul: 10000`, `resumo_filtrados: "semanal"`, e com `pci_slugs` e `pci_nacional` **removidos
      ou vazios** (ADR-0001). As outras areas ficam como estao, sem nenhuma das chaves novas.
      O arquivo tem segredo: o documento mostra **so** o trecho do `MONITOR_TARGETS_JSON` e nao pede para
      colar token nenhum.
- [ ] **Ensaio:** `python main.py --dry-run` e o que conferir na saida — concurso do Sul e federal entrando,
      municipal inflado e teto abaixo do corte como `filtrado`, e **nenhum** concurso do Sul filtrado.
      Nesse modo nada e gravado e nada e enviado.
- [ ] **Primeira rodada real** e o que conferir depois: `exit=0` no fim do log do dia,
      `logs/.last_success_date` com a data de hoje, nenhum alerta de chave no log, e o primeiro Telegram sem o
      ruido de fora do Sul.
- [ ] **Depois:** rodar o diagnostico de novo e comparar com o antes.
- [ ] **Como voltar atras**, em um paragrafo: trocar `filtro_salarial` para `"desligado"` e `pci_mcp` para
      `false`, repondo `pci_slugs` e `pci_nacional`. Sem deploy de codigo, sem mexer no banco: as colunas novas
      ficam e sao ignoradas. A rodada seguinte volta ao comportamento antigo.
- [ ] **O que o Lucas faz e o que ele nao faz:** chave e token quem grava e ele; nenhum passo do roteiro pede
      que um agente escreva credencial (`kanban/REGRAS.md`).

## Plano de testes

Costura: nao ha costura de codigo, porque o ticket nao muda comportamento. A verificacao e por leitura e por
busca no texto.

Oráculo: o codigo integrado e a SPEC-001. Toda afirmacao dos documentos tem de poder ser conferida contra um
arquivo do repo.

Checagens que o aceite cobra, cada uma com o comando que prova:

- `grep -rn "PciMcpScraper" README.md CLASS_DIAGRAM.md CLAUDE.md` traz pelo menos uma linha em cada um dos
  tres.
- `grep -c "pci_slugs" docs/DEPLOY-PCI-MCP.md` e maior que zero (o roteiro fala de remove-los).
- `grep -rn "T-0" README.md CLAUDE.md CLASS_DIAGRAM.md docs/DEPLOY-PCI-MCP.md` **nao devolve nada**: ID do
  quadro nao entra em documentacao do repo (`kanban/REGRAS.md`).
- `grep -rniE "(TELEGRAM_TOKEN|ZAI_API_KEY|LLM_API_KEY)\s*=\s*[^<\s]" docs/DEPLOY-PCI-MCP.md` **nao devolve
  nada**: nenhum valor de segredo, so nome de chave.
- Cada comando do roteiro de deploy foi copiado para um terminal e, nos que podem rodar na maquina de
  desenvolvimento, nao da erro de sintaxe.
- A suite continua verde: `python -m pytest -q`.

## Fora do escopo

- Mudar codigo. Qualquer divergencia entre documento e codigo se resolve corrigindo o **documento**; se o
  codigo estiver errado, volte com `BLOQUEADO`.
- Executar o deploy. Isso e do ticket seguinte, que espera o Lucas.
- Reescrever o `PLANO_EVOLUCAO_AGENTICA.md`. Ele e plano antigo e nao normativo (`kanban/REGRAS.md`); no
  maximo, uma linha no topo dizendo que a parte do PCI e do filtro salarial foi superada pela SPEC-001.
- Atualizar o vault do AIOS (`connections.md`, `references/estado-do-aios.md`, `decisions/log.md`). E outro
  repo, e o Lucas cuida dele.
- Documentar as outras quatro ferramentas do servidor MCP.

## Notas do arquiteto

- **P+ e nao P−:** e escrita sobre codigo que ja existe, mas sao quatro arquivos e o roteiro de deploy e o
  documento de que depende uma operacao que o Lucas vai executar sozinho, num notebook, provavelmente de
  madrugada. Passo faltando ou comando errado ali custa a rodada do dia.
- **O roteiro e o `passos` do recurso do dono.** O `esteira.json` aponta `docs/DEPLOY-PCI-MCP.md` como a lista
  do que o Lucas faz; e por isso que o caminho e o nome do arquivo nao podem mudar.
- Escreva o roteiro na ordem de execucao, com um comando por bloco, e sempre com "o que voce deve ver". O
  `HANDOFF.md` do repo e um bom exemplo de tom: direto, com tabela de onde cada coisa mora.
- O `git push` de `main` esta no roteiro de proposito: a branch local foi mesclada por fast-forward em
  23/11/2026, mas o `origin/main` continua em `1eb1a1f`. Sem o push, o `git pull` no notebook nao traz nada.
- Confira o `README.md` antes de reescrever: ele e longo e bilingue. Alterar as duas versoes de forma
  inconsistente e pior do que assumir uma so.

## Histórico
- 2026-11-23 18:16 backlog → pronto · liberado: onda 0 revisada e integrada; segue para a fase de fiacao, docs e deploy
- 2026-11-24 11:13 pronto → fazendo · implementador · glm-flash P+ high
- 2026-11-24 11:31 fazendo → entregue · implementador: ENTREGUE · relatório T-011-implementador-1.md · 18 min
- 2026-11-24 11:31 entregue → revisando · revisor · agy-argon M- medium
- 2026-11-24 11:34 revisando → aprovado · revisor: APROVADO · relatório T-011-revisor-1.md · 4 min
- 2026-11-24 11:34 aprovado → integrando · integrador · script
- 2026-11-24 11:34 integrando → integrado · integrador: INTEGRADO · relatório T-011-integrador-1.md · 0 min
