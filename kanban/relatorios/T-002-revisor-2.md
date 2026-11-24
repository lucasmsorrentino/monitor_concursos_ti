APROVADO COM RESSALVAS
Esteira: revisor · agy-neon (gemini-4-neon) · nível M+ · esforço high · 2026-11-23 18:10 → 2026-11-23 18:17 (8 min)
Resumo: Segunda volta de revisão de T-002 (`906faf2`). A entrega cumpre integralmente a SPEC-001 (seção 3.3), a ADR-0002 e todos os 10 itens do critério de aceite, sem arquivos fora do `toca` e com a suite completa verde (`369 passed / 0 failed / 0 skipped`, `296 + 73 = 369`). As 6 exigências do parecer anterior foram atendidas com 49 novos testes comportamentais na costura `esfera_de`, matando 59 de 64 mutações unitárias em worktree destacado. Ficam ressalvas não bloqueantes: 3 micro-lacunas de isolamento de mutação em testes, um padrão redundante e um termo `_Evite_` do glossário na docstring, além de uma ressalva de relatório sobre o commit de base citado.
Arquivos: `src/utils/esfera.py` (167 linhas, dentro do `toca`), `tests/test_esfera.py` (290 linhas, dentro do `toca`). Fora do `toca`: nenhum (`git diff --stat 768f60d..HEAD`).
Commits: `31d56f2` chore: esqueleto de src/utils/esfera.py com a assinatura de esfera_de · `717fc50` test: esfera_de classifica a esfera do orgao pelo nome (tabela do oraculo) · `826537d` feat: esfera_de com padroes declarados e precedencia entre esferas · `420f316` docs: contrato do modulo de esfera, precedencia e excecoes declaradas · `906faf2` test: precedencia entre esferas, padroes de cada esfera, excecoes e fallback DF na tabela do oraculo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (ambiente padrão, sem marcadores extras nem variáveis de ambiente adicionais; sem rede) → base `768f60d` 296 passed / 0 failed / 0 skipped (296 collected) · ponta `906faf2` 369 passed / 0 failed / 0 skipped (369 collected). Lint: não configurado no repo.
Testes que nascem verdes: os 49 casos acrescentados em `906faf2` (declarados honestamente no relatório do implementador como guardas de cobertura após o código já implementado e aprovado quanto à lógica em `420f316`; o primeiro commit `test:` `717fc50` nasceu genuinamente vermelho: 24 failed por `NotImplementedError`).
Desvios e riscos: Sem desvio de contrato nem bug em produção. Riscos residuais pequenos cobertos nas ressalvas abaixo: inversão isolada `_e_federal` ↔ `_e_distrital`, remoção isolada de `"transpetro"` e remoção isolada de `"universidade federal"` (por redundância de `"fundacao universidade federal"`) sobrevivem à suite atual; `CETESB - Companhia Ambiental do Estado de Sao Paulo - SP` permanece `None` (fail-open esperado conforme lista fechada do aceite).
Pendências: Sugestão de ticket P opcional para o arquiteto (ver seção **Padrões / Sugestão de ticket**), além das decisões de produto já pendentes para o arquiteto (casamento não contíguo de "Companhia ... do Estado" e eventual ampliação futura da lista fechada: STJ, TSE, MPU, DETRAN).

## Spec

1. **Critério de aceite cumprido (10/10):**
   - Assinatura e domínio fechado: `src/utils/esfera.py:145` expõe `esfera_de(nome: str | None) -> str | None` devolvendo apenas `"federal"`, `"estadual"`, `"distrital"`, `"municipal"`, `"conselho_profissional"` ou `None`, em conformidade com `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md:104-111`.
   - `municipal`: todos os 7 padrões do aceite (`_PADROES_MUNICIPAL`, `src/utils/esfera.py:56-63`, mais `" camara "` com exceção `" camara legislativa "` em `src/utils/esfera.py:123-126`) implementados e cobertos por `test_esfera_de_municipal`, `test_esfera_de_municipal_padroes_do_aceite` e `test_esfera_de_camara_legislativa_nao_e_municipal`.
   - `federal`: todos os 11 padrões de órgão e as 10 estatais federais do aceite (`_PADROES_FEDERAL`, `src/utils/esfera.py:68-89`, mais `" ministerio "` com exceção `" ministerio publico "` em `src/utils/esfera.py:129-134`) implementados e cobertos por `test_esfera_de_federal_universidade_e_instituto`, `test_esfera_de_federal_tribunal_e_ministerio`, `test_esfera_de_federal_tribunais_policia_e_justica`, `test_esfera_de_federal_estatais` e os dois testes de exceção do MP.
   - `estadual`: todos os 13 padrões do aceite (`_PADROES_ESTADUAL`, `src/utils/esfera.py:96-110`) implementados e cobertos por `test_esfera_de_estadual`, `test_esfera_de_estadual_padroes_do_aceite` e `test_esfera_de_ministerio_publico_estadual_e_estadual`.
   - `distrital`: `"do distrito federal"`, `"distrital"` (`_PADROES_DISTRITAL`, `src/utils/esfera.py:91-94`) e fallback pela UF `DF` no sufixo via `extrair_uf(nome) == "DF"` (`src/utils/esfera.py:165-166`) apenas quando nada mais decide, cobertos por `test_esfera_de_distrital`, `test_esfera_de_distrital_pelo_padrao_distrital`, `test_esfera_de_distrital_pela_uf_df_quando_nada_decide` e `federal_vence_sufixo_df`.
   - `conselho_profissional`: `"conselho regional"`, `"conselho federal"` e as 8 siglas (`_PADROES_CONSELHO`, `src/utils/esfera.py:43-54`), garantindo `Conselho Federal` como `conselho_profissional` conforme `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md:17-18`, cobertos por `test_esfera_de_conselho_profissional` e `test_esfera_de_conselho_pela_sigla`.
   - Precedência declarada `conselho_profissional > municipal > federal > distrital > estadual`: aplicada na ordem exata em `src/utils/esfera.py:153-162` e exercitada em `test_esfera_de_precedencia_entre_esferas` (`tests/test_esfera.py:111-162`).
   - Desconhecido / `None` / `""`: devolve `None` (`src/utils/esfera.py:147-148,167`), coberto por `test_esfera_de_desconhecido` (incluindo `APS - Associacao das Pioneiras Sociais`, `None` e `""`).
   - Normalização insensível a acento e caixa: reusa `normalizar_nome` (e `extrair_uf`) de `src/utils/text.py` sem editar `text.py`, coberto por `test_esfera_de_ignora_acento_e_caixa`.
   - Sem dependência externa: `src/utils/esfera.py:38` importa apenas `src.utils.text` (que usa só stdlib: `hashlib`, `re`, `unicodedata`).
2. **Escopo (`toca`):** `git diff --stat 768f60d..HEAD` toca exclusivamente `src/utils/esfera.py` (+167) e `tests/test_esfera.py` (+290). `src/utils/text.py` permanece intocado. Nenhum gancho ou comportamento fora do pedido.
3. **Conferência contra fixtures reais do PCI MCP:** Executado `esfera_de` sobre todos os 39 itens das fixtures em `tests/fixtures/pci_mcp/*.json` (`tools_call_analista_de_sistemas.json`: 9 itens; `tools_call_tecnico_em_informatica.json`: 30 itens; `tools_call_sem_resultado.json`: 0 itens). Todas as classificações conferem com o contrato e com fail-open (`UFMS`, `TRF3`, `IFSP`, `IFG` → `federal`; `DPDF` → `distrital`; `Banestes`, `SEAD`, `IMA`, `SECITECI` → `estadual`; prefeituras, câmaras, `IPAM`, `SEMSA` → `municipal`; `CETESB`, `CIS`, `SETEC` → `None`).

## Prova

1. **Números medidos vs. relatório do implementador:**

| Medição | Implementador afirmou | Revisor mediu | Comando e condição |
| :--- | :--- | :--- | :--- |
| Base do ticket (`git merge-base main HEAD` = `768f60d`) | Não mediu `768f60d`; citou `420f316` (`320 passed / 0 failed`) como base da 2ª volta | `296 passed / 0 failed / 0 skipped` (`296 tests collected in 0.77s`, `22.76s`) | Worktree destacado `C:\Temp\t002-base` em `768f60d`: `".venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q` (sem marcadores/env extras) |
| Primeiro `test:` (`717fc50`) | Não reexecutou na 2ª volta | `24 failed in 0.14s` — todos por `NotImplementedError` em `src/utils/esfera.py:6` | Worktree destacado `C:\Temp\t002-red` em `717fc50`: `".venv/Scripts/python.exe" -m pytest tests/test_esfera.py -q --tb=line` |
| Suite do módulo na ponta (`906faf2`) | `73` (implícito na tabela de mutações: `failed + passed = 73`) | `73 passed in 0.25s` (0 failed, 0 skipped) | Worktree do ticket em `906faf2`: `".venv/Scripts/python.exe" -m pytest tests/test_esfera.py -q -rs` |
| Suite completa na ponta (`906faf2`) | `369 passed / 0 failed` (0 pulados) | `369 passed in 23.39s` (`369 tests collected in 0.73s`, 0 failed, 0 skipped) | Worktree do ticket em `906faf2`: `".venv/Scripts/python.exe" -m pytest -q -rs` e `--collect-only -q` |
| Lint | Não configurado | Não configurado | N/A |

- **Fechamento da conta:** `296 (base 768f60d) + 73 (tests/test_esfera.py: 24 em 717fc50 + 49 em 906faf2) = 369 (ponta 906faf2)`. Conta fecha exatamente.
- **Ressalva de relatório (não vira ticket):** o implementador informou `base 420f316 320 passed` (ponta da 1ª volta) em vez da base do ticket na branch de integração (`768f60d`, `296 passed`). A diferença não esconde falha nem pulo e a conta fecha nos dois referenciais (`320 + 49 = 369` e `296 + 73 = 369`).

2. **TDD verificado:**
   - Ordem em `git log --format='%h %s' 768f60d..HEAD`: `31d56f2` (`chore:` esqueleto com `raise NotImplementedError`) → `717fc50` (`test:` 24 casos, comprovadamente vermelhos pelo motivo certo no worktree destacado) → `826537d` (`feat:`) → `420f316` (`docs:` separado do código) → `906faf2` (`test:` 49 casos de cobertura na 2ª volta, declarados como testes que nascem verdes).

3. **Qualidade dos testes e bateria de mutações (worktree destacado `C:\Temp\t002-mut` em `906faf2`, com `git diff --stat` conferido antes de cada `pytest`):**
   - Costura respeitada: todos os 73 casos chamam exclusivamente `esfera_de`. Zero acoplamento à implementação (não testa helpers privados nem faz assert de chamadas), zero tautologia (oráculo tabular independente), zero dublê fora da fronteira (sem mocks; `normalizar_nome` e `extrair_uf` rodam de verdade).
   - **Resultado da bateria exaustiva (64 mutações unitárias: 5 trocas adjacentes de precedência, 8 mutações de lógica/exceções/normalização, 51 deleções individuais de padrão):** **59 mortas, 5 sobreviventes**.
     - Todos os 10 itens de aceite têm mutações mortas (8/8 em `municipal`, 19/22 em `federal`, 13/13 em `estadual`, 3/3 em `distrital`, 10/10 em `conselho_profissional`, 3/4 trocas adjacentes de precedência, `None`/vazio, `normalizar_nome` e fronteira de palavra em `_algum`).
     - Análise das 5 sobreviventes:
       1. **Ressalva de código — troca adjacente `_e_federal` ↔ `_e_distrital` (`src/utils/esfera.py:157-160`):** sobreviveu (`73 passed`). O caso `federal_vence_sufixo_df` (`tests/test_esfera.py:145`) exercita `_e_federal` contra o fallback `extrair_uf(nome) == "DF"`, mas nenhum caso ativa `_e_federal` e `_e_distrital` (`"do distrito federal"` / `"distrital"`) ao mesmo tempo (ex.: `"TRE-DF - Tribunal Regional Eleitoral do Distrito Federal - DF"`).
       2. **Ressalva de código — remoção isolada de `"transpetro"` (`src/utils/esfera.py:83`):** sobreviveu (`73 passed`) porque o caso `"Transpetro - Petrobras Transporte S.A."` (`tests/test_esfera.py:230`) também contém `"Petrobras"`.
       3. **Ressalva de código — remoção isolada de `"universidade federal"` (`src/utils/esfera.py:69`):** sobreviveu (`73 passed`) apenas porque o único caso com a expressão (`"UFMS - Fundacao Universidade Federal de Mato Grosso do Sul - MS"`, `tests/test_esfera.py:36`) também casa o padrão redundante `"fundacao universidade federal"` na linha 70.
       4. **Mutante equivalente — remoção de `"fundacao universidade federal"` (`src/utils/esfera.py:70`):** sobreviveu porque é estritamente coberto por `"universidade federal"` (linha 69). Não é defeito de teste, e sim redundância na tupla (registrada em **Padrões**).
       5. **Não-problema de domínio — troca `_e_estadual` ↔ fallback `extrair_uf == "DF"` (`src/utils/esfera.py:161-166`):** sobreviveu; não há órgão estadual real com sufixo `- DF` no domínio, portanto não exige caso artificial.

## Padrões

1. **Regras do projeto (`kanban/REGRAS.md`) e `GLOSSARIO.md`:**
   - Português do Brasil, identificadores e comentários sem acento (único acento no diff é o dado de entrada `"prefeitura de ijuí - rs"` em `tests/test_esfera.py:100`, exigido pelo teste de acentuação).
   - Zero IDs do quadro (`T-002` / `T-NNN`) em código, docstring ou comentários.
   - Zero segredos, zero dependência nova, zero rede nos testes, sem `push`.
   - **Ressalva de vocabulário (`GLOSSARIO.md:45`):** `src/utils/esfera.py:3` escreve `"isenta do corte salarial"`, mas `GLOSSARIO.md:45` lista `corte salarial` em `_Evite_` (termo normativo: `corte fora do Sul`). O desvio foi herdado da seção Contexto do próprio ticket; fica como ressalva não bloqueante.
2. **Cheiros de código:**
   - **Possível código redundante (`src/utils/esfera.py:70`):** a entrada `"fundacao universidade federal"` em `_PADROES_FEDERAL` nunca alcança um nome que `"universidade federal"` (linha 69) já não tenha casado, porque toda string normalizada que contém `" fundacao universidade federal "` já contém `" universidade federal "`. Conserto: remover a entrada redundante (ou mantê-la apenas documentada) junto com a adição de um caso de teste de `"Universidade Federal"` sem `"Fundacao"`.
   - **Trivialidade de redação (`src/utils/esfera.py:1`):** docstring de abertura repete o substantivo (`"Classificacao da esfera do orgao pelo nome do orgao"`).
   - Demais funções (`_algum`, predicados por esfera, `esfera_de`) estão limpas, legíveis, coesas e idiomáticas no padrão do repositório.

## Sugestão de ticket (ressalvas de código)

- **Título:** Reforcar isolamento de testes e limpar redundancia em `esfera`
- **Nível:** P
- **Toca:** `[src/utils/esfera.py, tests/test_esfera.py]`
- **Escopo sugerido:** (1) em `tests/test_esfera.py`, acrescentar caso de precedência `federal_vence_distrital` com `"do Distrito Federal"` (ex.: `"TRE-DF - Tribunal Regional Eleitoral do Distrito Federal - DF"`), caso de `"Universidade Federal"` sem `"Fundacao"` (ex.: `"UFPR - Universidade Federal do Parana - PR"`) e isolar `"Transpetro"` sem `"Petrobras"` no mesmo nome; (2) em `src/utils/esfera.py`, remover `"fundacao universidade federal"` redundante de `_PADROES_FEDERAL` e trocar `"corte salarial"` por `"corte fora do Sul"` na docstring (`GLOSSARIO.md:45`).
