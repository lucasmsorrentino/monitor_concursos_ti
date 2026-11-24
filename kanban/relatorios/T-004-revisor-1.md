APROVADO COM RESSALVAS
Esteira: revisor · agy-argon (gemini-4-argon) · nível M+ · esforço high · 2026-11-23 17:37 → 2026-11-23 17:45 (9 min)
Resumo: Entrega de `PciMcpScraper` (subclasse de `BaseScraper`) revisada e aprovada com ressalvas. O código cumpre todos os 14 itens do critério de aceite de T-004, a SPEC-001 (§3.1 e §4.1 R-01..R-04, R-06) e a ADR-0001, tocando apenas os dois arquivos do `toca`. Os 17 testes do plano nasceram vermelhos por `NotImplementedError` no commit `bd98fdc` e todos os itens de aceite foram validados por mutação em worktree destacado; as ressalvas são um desvio de processo na ordem do commit de guarda (`b4307bc` após `docs:`) e três casos de borda do código que não têm teste dedicado na suíte.
Arquivos: src/scrapers/pci_mcp_scraper.py · tests/test_pci_mcp_scraper.py (nenhum arquivo fora do `toca`)
Commits: 947bc45 chore: esqueleto do scraper da porta MCP do PCI · bd98fdc test: mapeamento, uniao por id, SSE e falhas por termo da porta MCP · bf0ee6d feat: porta do PCI pelo servidor MCP (buscar_por_cargo) · ac296b9 docs: contrato da porta MCP (transporte JSON-RPC/SSE, envelope e regras) · b4307bc test: endpoint do servidor no POST da porta MCP (guarda)
Testes: "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs → base 296 passed / 0 failed (0 skipped) · ponta 314 passed / 0 failed (0 skipped)
Testes que nascem verdes: test_posta_para_o_endpoint_do_servidor (commit b4307bc, guarda adicionada após `feat:` e `docs:`; valor comprovado pela mutação M01)
Desvios e riscos: Ressalva de processo (para a retro): o commit `b4307bc` (`test:`) foi feito depois de `ac296b9` (`docs:`) e nasceu verde. Ressalva de código (sugestão de ticket opcional): três sub-ramos já implementados em `src/scrapers/pci_mcp_scraper.py` (`datas.em_breve` quando o título não infere `"edital_publicado"`, `datas.fim` vazio/ausente virando `None` e `resposta.status_code != 200`) sobrevivem à mutação de remoção do sub-ramo porque o plano de testes não incluía casos isolados para eles.
Pendências: Ligar `PciMcpScraper` no `ConcursoBot` e registrar `pci_mcp` em `saude_fontes` (SPEC-001 R-07); sugestão opcional de ticket P para cobrir os 3 casos de borda em `tests/test_pci_mcp_scraper.py`.

## Spec

1. **O aceite foi cumprido?** Sim. Todos os 14 itens do critério de aceite estão implementados em `src/scrapers/pci_mcp_scraper.py` e cobertos em `tests/test_pci_mcp_scraper.py`:
   - `PciMcpScraper(termos: list[str], tentativas: int = 3)` subclasse de `BaseScraper`, com `self.url == "https://mcp.pciconcursos.com.br/mcp"` (`src/scrapers/pci_mcp_scraper.py:61,67-77`; `tests/test_pci_mcp_scraper.py:269-277`).
   - `capturar_concursos() -> list[dict]` faz um POST `buscar_por_cargo` por termo, sem `uf`, devolvendo a união (`src/scrapers/pci_mcp_scraper.py:79-127,137-142`; `tests/test_pci_mcp_scraper.py:279-294`).
   - União por `id` (R-01) acumulando `cargos` sem repetição e `termos_origem` (`src/scrapers/pci_mcp_scraper.py:107-117`; `tests/test_pci_mcp_scraper.py:155-169`).
   - Formato exato da `SPEC-001` §3.1 (`CHAVES_DO_ITEM`), incluindo `ignorar: False`, `data_referencia: None`, `fonte: "pci_mcp"` e `pci_id` como `str` (`src/scrapers/pci_mcp_scraper.py:191-207`; `tests/test_pci_mcp_scraper.py:21-25,73-92`).
   - `nome` com sufixo `f"{titulo} - {uf}"` quando `uf` existe e só `titulo` quando `uf` é `None` (`src/scrapers/pci_mcp_scraper.py:193`; `tests/test_pci_mcp_scraper.py:81,105-115`).
   - `fase` calculada a partir de `datas.aberto` (`"inscricoes_abertas"`), depois `datas.em_breve` (`"edital_publicado"`), com fallback em `inferir_fase(noticia.titulo)` importado de `src.scrapers.pci_comum` (`src/scrapers/pci_mcp_scraper.py:59,196,210-216`; `tests/test_pci_mcp_scraper.py:116-143`).
   - `data_fim_inscricao` recebe `datas.fim` como vem (`datas.get("fim") or None`) (`src/scrapers/pci_mcp_scraper.py:197`; `tests/test_pci_mcp_scraper.py:145-151`).
   - `vagas_salario` preservado cru, sem parse (`src/scrapers/pci_mcp_scraper.py:205`; `tests/test_pci_mcp_scraper.py:88`).
   - Transporte (R-02): POST JSON-RPC 2.0 (`"method": "tools/call"`), cabeçalhos `Content-Type: application/json`, `Accept: application/json, text/event-stream` e `MCP-Protocol-Version: 2025-06-18`, leitura de JSON direto e SSE (`data: `), e segundo `json.loads` em `result.content` com `type == "text"` (`src/scrapers/pci_mcp_scraper.py:62,73-77,137-182`; `tests/test_pci_mcp_scraper.py:170-179,279-294`).
   - Termo sem resultado (R-03): resposta com `message` e `data` vazia logada em `info`, segue sem erro e sem repetir a chamada (`src/scrapers/pci_mcp_scraper.py:94-98`; `tests/test_pci_mcp_scraper.py:181-190`).
   - Termo que falha (R-04): erro de rede, HTTP diferente de 200, JSON inválido ou resposta sem `content` de texto logados em `warning`, seguindo com os outros termos e levantando `RuntimeError` apenas quando todos os termos falham (`src/scrapers/pci_mcp_scraper.py:85-92,119-122,144-169`; `tests/test_pci_mcp_scraper.py:193-242`).
   - Aviso de truncamento (R-06): `meta.total >= 200` gera `warning` contendo `"truncada"` (`src/scrapers/pci_mcp_scraper.py:63,100-105`; `tests/test_pci_mcp_scraper.py:243-256`).
   - Termo vazio ou só espaço descartado na construção (`src/scrapers/pci_mcp_scraper.py:72`; `tests/test_pci_mcp_scraper.py:260-267`).
   - `requirements.txt` intocado (`git diff --stat 768f60de452c8379cdd13f9948d1ef192615405b..HEAD`).
2. **Passou do escopo?** Não. `git diff --stat 768f60de452c8379cdd13f9948d1ef192615405b..HEAD` mostra alterações exclusivamente nos dois arquivos do campo `toca`:
   - `src/scrapers/pci_mcp_scraper.py` (+216 linhas)
   - `tests/test_pci_mcp_scraper.py` (+294 linhas)
   Nada foi ligado ao `ConcursoBot`, `base_scraper.py` e `requirements.txt` não foram tocados, e nenhuma ferramenta extra do MCP ou handshake de sessão foi implementado.
3. **Bate com a spec?** Sim. Conferido contra `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md` (§3.1 linhas 62-92 e §4.1 linhas 172-189) e `docs/adr/0001-mcp-como-unica-porta-do-pci.md` (linhas 1-27).
   - Sobre os dois pontos sinalizados pelo implementador: a precedência `datas.get("aberto")` antes de `datas.get("em_breve")` em `_fase` (`src/scrapers/pci_mcp_scraper.py:212-215`) segue `SPEC-001:90-91`, e o fallback `"status": noticia.get("titulo") or titulo` (`src/scrapers/pci_mcp_scraper.py:194`) é consistente com `SPEC-001:70` e com `PciScraper._parse` (`src/scrapers/pci_scraper.py:129`).
   - **Ressalva de código (casos de borda do aceite implementados no código, mas sem asserção isolada na suíte):**
     1. Em `test_fase_vem_de_em_breve` (`tests/test_pci_mcp_scraper.py:124-130`), o item `295546` da fixture real possui `datas.em_breve: true`, mas seu `noticia.titulo` (`"Prefeitura de Santa Luzia - MG abre concurso público..."`) também resulta em `"edital_publicado"` via `inferir_fase`. O código em `src/scrapers/pci_mcp_scraper.py:214-215` está correto, mas apagar `if datas.get("em_breve"):` não quebra o teste se o título da fixture não for neutro.
     2. Em `src/scrapers/pci_mcp_scraper.py:197`, `"data_fim_inscricao": datas.get("fim") or None` converte string vazia ou ausente em `None` conforme o aceite (`SPEC-001:73`), mas não há teste exercitando `datas.fim == ""` ou `None`.
     3. Em `src/scrapers/pci_mcp_scraper.py:149-150`, `if resposta.status_code != 200: raise RuntimeError(...)` cumpre `SPEC-001:182` (R-04), mas `TestTermoQueFalha` não inclui um caso com `RespostaFake(..., status_code=500)`.
     - **Sugestão de ticket novo (opcional, a critério do arquiteto):**
       - Título: `Testes de borda da porta MCP (em_breve sem pista no título, datas.fim vazio e HTTP != 200)`
       - Nível: `P`
       - `toca`: `[tests/test_pci_mcp_scraper.py]`

## Prova

4. **Os números são reais?** Sim. Medições executadas pelo revisor no venv do repositório, sem variáveis de ambiente ou marcadores extras:
   - Comando: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs`
   -Comparação:
     - **Base** (`768f60de452c8379cdd13f9948d1ef192615405b`, em worktree destacado): implementador afirmou `296 passed / 0 failed` · revisor mediu `296 passed in 23.12s` (0 failed, 0 skipped).
     - **Ponta** (`b4307bc4011edbd865e70851f127afa7673975ce`): implementador afirmou `314 passed / 0 failed (18 novos, 0 pulados)` · revisor mediu `314 passed in 28.38s` (0 failed, 0 skipped).
     - **Conta:** 296 + 18 = 314. A conta fecha exatamente. Lint não configurado no repositório.
5. **O TDD foi de verdade?** Sim para os 17 testes do plano, com uma ressalva de processo no 18º teste (guarda):
   - No commit `bd98fdc` (`test: mapeamento, uniao por id, SSE e falhas por termo da porta MCP`), medido em worktree destacado com `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_pci_mcp_scraper.py -q`, o resultado foi `17 failed in 0.43s`, todos por `NotImplementedError` em `PciMcpScraper.capturar_concursos` (`src/scrapers/pci_mcp_scraper.py:23`).
   - **Ressalva de processo (para a retro, não gera ticket):** o commit `b4307bc` (`test: endpoint do servidor no POST da porta MCP (guarda)`) foi commitado depois de `ac296b9` (`docs:`) e já nasceu verde (declarado pelo implementador no relatório). Pela regra do ciclo TDD (`chore:` → `test:` → `feat:` → `docs:`, onde `docs:` fecha), o teste deveria ter entrado no commit `test:` antes do `feat:`.
6. **Os testes provam comportamento?** Sim. Todos os 18 testes usam a costura pública `PciMcpScraper.capturar_concursos()` e `scraper.url`, dublando exclusivamente `src.scrapers.pci_mcp_scraper.requests.post` na fronteira HTTP e comparando com literais lidos à mão das fixtures reais em `tests/fixtures/pci_mcp/`. Não há teste tautológico, acoplado a método privado ou com dublê fora da fronteira.
   - **Prova por mutação em worktree destacado (`HEAD` `b4307bc`):**
     - `M01_endpoint_url` (`URL_SERVIDOR` trocado por `.../errado`): **1 failed** (`test_posta_para_o_endpoint_do_servidor`) — comprova o valor da guarda `b4307bc`.
     - `M02_envia_uf` (`"uf": "SP"` em `arguments`): **1 failed** (`test_nao_envia_parametro_uf`).
     - `M03_uniao_id` (`if existente:` → `if False:` em `pci_mcp_scraper.py:110`): **1 failed** (`test_uniao_por_id_nao_repete_concurso`).
     - `M04_formato_pci_id_fonte` (`"pci_id": bruto.get("id")` sem `str()` em `pci_mcp_scraper.py:199`): **8 failed** (`test_capturar_mapeia_item_completo` e mais 7).
     - `M05_nome_uf_sufixo` (`"nome": f"{titulo} - {uf}"` sem condicional em `pci_mcp_scraper.py:193`): **1 failed** (`test_nome_sem_uf_fica_so_o_titulo`).
     - `M06a_fase_aberto` (`if datas.get("aberto"):` → `if False:` em `pci_mcp_scraper.py:212`): **1 failed** (`test_fase_vem_de_aberto`).
     - `M06c_fase_em_breve_wrong_val` (`return "edital_publicado"` → `return "previsto"` em `pci_mcp_scraper.py:215`): **1 failed** (`test_fase_vem_de_em_breve`).
     - `M06d_fase_fallback_titulo` (`return inferir_fase(titulo)` → `return None` em `pci_mcp_scraper.py:216`): **1 failed** (`test_fase_cai_no_titulo_sem_as_duas_datas`).
     - `M07a_data_fim` (`"data_fim_inscricao": None` em `pci_mcp_scraper.py:197`): **1 failed** (`test_data_fim_vem_de_datas_fim`).
     - `M08_vagas_salario_cru` (`vagas_salario` alterado com `.lower()` em `pci_mcp_scraper.py:205`): **1 failed** (`test_capturar_mapeia_item_completo`).
     - `M09_transporte_sse` (`if linha.startswith("data: "):` → `if False:` em `pci_mcp_scraper.py:179`): **1 failed** (`test_le_resposta_em_sse`).
     - `M10b_termo_sem_resultado` (`if payload.get("message") and not payload.get("data"):` → `if False:` em `pci_mcp_scraper.py:94`): **1 failed** (`test_termo_sem_resultado_nao_quebra`).
     - `M11a_termo_falha_continua` (`falharam += 1` → `raise` em `pci_mcp_scraper.py:91`): **4 failed** (`TestTermoQueFalha`).
     - `M11b_todos_falham_levanta` (`if self.termos and falharam == len(self.termos):` → `if False:` em `pci_mcp_scraper.py:119`): **1 failed** (`test_todos_os_termos_falhando_levanta`).
     - `M12_truncamento_200` (`>= LIMITE_TRUNCAMENTO` → `>` em `pci_mcp_scraper.py:101`): **1 failed** (`test_avisa_truncamento_em_200`).
     - `M13_termo_vazio` (`self.termos = list(termos)` em `pci_mcp_scraper.py:72`): **1 failed** (`test_termo_vazio_e_descartado`).
     - As três sub-mutações que sobreviveram (`M06b_fase_em_breve_deleted`, `M07b_data_fim_vazio` e `M11c_http_status_code`) correspondem aos três casos de borda apontados como ressalva no bloco Spec.

## Padrões

7. **Regras e padrões do projeto (`kanban/REGRAS.md`, `GLOSSARIO.md`, `docs/adr/0001-mcp-como-unica-porta-do-pci.md`):** Cumpridos integralmente.
   - Termos do `GLOSSARIO.md` usados corretamente (`porta`, `rodada`, `fase`, `teto do concurso`).
   - Código, docstrings, logs e mensagens de commit em português do Brasil; identificadores e comentários sem acento.
   - Nenhum ID de ticket (`T-NNN`) em código, docstring, comentário ou mensagem de commit.
   - Sem segredo, sem dependência nova, sem rede nos testes e sem uso de LLM.
   - Herança de `BaseScraper` sem editar `base_scraper.py` nem reusar `get_html`, com o motivo documentado em `src/scrapers/pci_mcp_scraper.py:132-135` conforme exigido nas notas do arquiteto.
8. **Cheiros de código:** Nenhum cheiro identificado. O módulo `src/scrapers/pci_mcp_scraper.py` tem responsabilidades claras, métodos curtos e simetria direta com `src/scrapers/pci_scraper.py`.
