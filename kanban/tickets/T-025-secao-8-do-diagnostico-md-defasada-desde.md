---
id: T-025
titulo: Secao 8 do DIAGNOSTICO.md defasada desde a porta do MCP
tipo: docs
nivel: P-
status: backlog
repo: principal
spec: [SPEC-001, R-20, R-22]
depende_de: []
toca: [docs/DIAGNOSTICO.md]
recursos: []
afinidade:
retornos: 0
---
# T-025 · Secao 8 do DIAGNOSTICO.md defasada desde a porta do MCP

## Contexto

O revisor do ticket que levou a porta do MCP e o filtro salarial para o retrato do diagnostico apontou que o
`docs/DIAGNOSTICO.md`, na descricao da secao 8 (`== Config efetiva ==`), nao menciona a porta `pci_mcp` nem o
filtro salarial, que o `scripts/diagnostico_producao.sh` passou a imprimir. O documento descreve uma saida
que nao existe mais. O conserto nao entrou naquele ticket porque o arquivo estava fora do `toca` dele; o
registro da ressalva esta em `kanban/RESSALVAS.md`.

## Critério de aceite
- [ ] A descricao da secao 8 cita a porta `pci_mcp` com a contagem de termos, e `filtro_salarial`,
      `corte_fora_sul` e `resumo_filtrados` com os padroes da SPEC-001 secao 3.6
- [ ] O que o documento descreve bate com o que o script imprime hoje
- [ ] Nenhuma outra secao do documento muda
- [ ] Sem segredo no documento

## Plano de testes
Costura: nenhuma. Ticket de documentacao, sem teste novo.
Oráculo: a saida real de `bash scripts/diagnostico_producao.sh`, rodado na raiz do repo, e a tabela de
padroes da SPEC-001 secao 3.6.
- Conferencia manual: rodar o script, comparar o bloco `== Config efetiva ==` com o texto da secao 8, e colar
  as duas coisas lado a lado no relatorio.

## Fora do escopo
- Mexer no `scripts/diagnostico_producao.sh`. Ele esta correto.
- Reescrever qualquer outra parte do documento.

## Notas do arquiteto

**Por que P−:** mecanico, um arquivo, e o padrao esta no proprio documento, nas outras secoes.

Nasceu de ressalva de revisao, nao de pedido novo. E nao e `docs:` de cortesia: documento que descreve uma
saida que nao existe mais e **pior** que documento ausente, porque manda o leitor procurar o que nao esta la.
