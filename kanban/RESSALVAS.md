# Ressalvas das aprovações
O `coletar` acrescenta uma linha aqui a cada «APROVADO COM RESSALVAS»; o arquiteto lê o relatório citado.
Marque `[x]` e escreva o destino (virou T-NNN, virou nota no ticket, aceita); o `metricas` conta as duas.

- [x] T-004 · T-004-revisor-1.md · 2026-11-23 · destino: virou T-014 (tres sub-ramos da porta do MCP)
- [x] T-006 · T-006-revisor-1.md · 2026-11-23 · destino: virou T-015 (quatro assercoes do loader)
- [x] T-001 · T-001-revisor-1.md · 2026-11-23 · destino: processo (agente deu push): vai para a retro, nao vira ticket
- [x] T-003 · T-003-revisor-1.md · 2026-11-23 · destino: virou T-013 (nove mutacoes e a constante MOTIVOS)
- [x] T-002 · T-002-revisor-2.md · 2026-11-23 · destino: virou T-014 (mutacoes da esfera); lista fechada e casamento nao contiguo ficam em nevoa, decisao de produto
- [x] T-009 · T-009-revisor-1.md · 2026-11-23 · destino: virou T-015 (contadores e cegueira); o defeito real do sem_materia_prima foi corrigido no T-010
- [x] T-010 · T-010-revisor-1.md · 2026-11-23 · destino: virou T-015 (janela de sete dias, selo sem_evidencia, vocabulario); risco entre fontes virou T-019
- [x] T-015 · T-015-revisor-1.md · 2026-11-25 · destino: retro. A linha M1a da tabela de mutacao do implementador nao reproduz como escrita: o edit de uma linha sobrevive, o composto mata. O teste tem dentes e o aceite esta provado; o que falhou foi a prova ser conferivel. Regra para a retro: linha de tabela de mutacao descreve o edit exato, nao o resumo dele
- [x] T-013 · T-013-revisor-1.md · 2026-11-25 · destino: retro (par fechou `test:` → `refactor:` sem `docs:`, coerente com o desenho do ticket, mas desvio registrado). O engano de metadata que o revisor achou foi corrigido aqui: o campo `spec:` citava R-01/R-02, que sao regras da porta do MCP, e virou [SPEC-001], porque a tabela da secao 4.2 nao tem id de requisito
- [x] T-016 · T-016-revisor-1.md · 2026-11-25 · destino: `docs/DIAGNOSTICO.md` secao 8 ficou defasada e esta fora do `toca` do ticket: virou o T-025. As duas bordas sem teste (`pci_mcp` ligado com `pci_mcp_cargos` vazio, e o ramo string da contagem) ficam em nevoa: o retrato relata e nao julga, pela ADR-0003
- [x] T-020 · T-020-revisor-6.md · 2026-11-26 · destino: virou T-029 (P+, constante duplicada e caso acentuado no teste da ordem sem pci_id). As duas sao do arquivo de teste e nenhuma de comportamento; o R-82 segue provado em ASCII por outros dois testes. A segunda e o MESMO defeito que o parecer 5 apontou em outro teste: `.upper()` em nome acentuado dentro de teste que depende de COLLATE NOCASE tem dois casos conhecidos neste arquivo, e isso vai para a retro como checagem automatica 
