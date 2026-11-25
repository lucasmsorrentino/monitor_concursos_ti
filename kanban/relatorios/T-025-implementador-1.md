ENTREGUE
Esteira: implementador · agy-hydrogen (gemini-4-hydrogen) · nível P- · esforço medium · 2026-11-25 16:49 → 2026-11-25 16:55 (7 min)
Resumo: Atualizada a seção 8 (`### 8. Config efetiva`) de `docs/DIAGNOSTICO.md` para refletir a saída atual de `scripts/diagnostico_producao.sh`, incluindo a porta `pci_mcp` com a contagem de termos de `pci_mcp_cargos` e os parâmetros `filtro_salarial` (padrão `"desligado"`), `corte_fora_sul` (padrão `0`) e `resumo_filtrados` (padrão `"nunca"`), conforme a SPEC-001 seção 3.6. Nenhuma outra seção do documento foi alterada e nenhum segredo foi adicionado.
Arquivos: `docs/DIAGNOSTICO.md` (dentro do `toca`)
Commits: `c46481b` docs: atualiza secao 8 do DIAGNOSTICO.md com pci_mcp e filtro salarial
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 569 passed / 0 failed · ponta 569 passed / 0 failed (sem marcadores especiais; lint não configurado)
Testes que nascem verdes: nenhum (ticket de documentação, sem teste novo)
Desvios e riscos: nenhum
Pendências: nenhuma

## Conferência manual (`== Config efetiva ==` vs Seção 8)

Saída real de `bash scripts/diagnostico_producao.sh` na raiz do worktree (sem `MONITOR_TARGETS_JSON` configurado no ambiente):
```text
== Config efetiva ==
ausente: MONITOR_TARGETS_JSON (ambiente e /c/Users/Lucas/concursos-secrets/monitor.env)
```

Saída real de `bash scripts/diagnostico_producao.sh` com `MONITOR_TARGETS_JSON` de exemplo em memória:
```text
== Config efetiva ==
MONITOR_TARGETS_JSON (de variavel de ambiente):
  area TI (Tecnologia da Informacao)
    porta gran: ligada
    porta pci_cargos: desligada
    porta pci_nacional: desligada
    porta pci_mcp: ligada (2 termo(s))
    filtro_salarial: ativo
    corte_fora_sul: 10000
    resumo_filtrados: semanal
    token: ausente
    chat_ids: <omitido> (1)
```

Texto atualizado na seção 8 de `docs/DIAGNOSTICO.md`:
```markdown
### 8. Config efetiva

Áreas configuradas, portas ligadas e parâmetros de filtragem em cada uma (`gran` ligada pela URL; `pci_cargos`
quando há `pci_slugs`, com contagem de slugs; `pci_nacional` quando a flag está ligada; `pci_mcp` quando a flag
está ligada, com a contagem de termos de `pci_mcp_cargos`; além de `filtro_salarial` com padrão `"desligado"`
[`desligado` ou `ativo`], `corte_fora_sul` com padrão `0` e `resumo_filtrados` com padrão `"nunca"` [`nunca` ou
`semanal`]), lidos do `MONITOR_TARGETS_JSON` do ambiente de produção com `token` e `chat_ids` substituídos
por `<omitido>`; na sequência, os **nomes** das chaves encontradas no `.env` local e no arquivo de segredos.

- **Sinal de problema**: área esperada ausente; porta esperada desligada (ex.: `pci_nacional: desligada`
  explica estatal federal não aparecer; `pci_mcp: desligada` ou com `0 termo(s)` explica busca MCP não rodar);
  `filtro_salarial`, `corte_fora_sul` ou `resumo_filtrados` em desacordo com o esperado (ex.: valor inválido de
  `filtro_salarial` caindo em `desligado`); `MONITOR_TARGETS_JSON` ausente — a produção está no modo legado
  de URL única.
```
