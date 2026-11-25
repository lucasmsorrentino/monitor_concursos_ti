APROVADO COM RESSALVAS
Esteira: revisor · glm-go (opencode-go/glm-5.3) · nível M+ · esforço high · 2026-11-24 23:58 → 2026-11-25 00:07 (10 min)
Resumo: A entrega cumpre os nove itens de aceite: assercoes do loader estreitadas contra o padrao da SPEC, contadores e selo `sem_evidencia` afirmados na costura do bot, cegueira afirmada depois de `executar()`, janela de 7 dias inspecionada com valor calculado a mao, e as quatro ocorrencias novas de `varredura` trocadas por `rodada` sem tocar as legadas. Medi eu mesmo base (539) e ponta (545) e reproduzi por mutacao propria 12 das 13 linhas da tabela do implementador; a linha M1a nao se reproduz como descrita (detalhe em Prova) — ressava de relatorio, nao de codigo.
Arquivos: `src/core/bot.py`, `tests/test_config_loader.py`, `tests/test_concurso_bot.py` — o diff nao toca nada fora do `toca`; `src/core/bot.py` mudou so as duas palavras de texto autorizadas (comentario e log).
Commits: `cf9cc0e` test: estreita assercoes do loader · `fb01ddc` test: afirma contadores no resumo final, cegueira apos executar, selo sem_evidencia e janela de 7 dias · `82db274` chore: troca varredura por rodada nos quatro trechos novos (ordem conferida no log).
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` (sem variaveis de ambiente, sem marcadores; lint nao configurado) → base (2ea449f) 539 passed / 0 failed (41.84s) · ponta (82db274) 545 passed / 0 failed (45.34s; refeita apos as mutacoes: 545 passed, 38.47s). Conta fecha: 539 + 6 testes novos = 545.
Testes que nascem verdes: todos, por desenho (nota do arquiteto no ticket); a prova e a tabela de mutacao, que confirmei com medida propria — 12 de 13 linhas reproduzidas mortas; a 13a (M1a) nao reproduz como escrita.
Desvios e riscos: (i) ressava de relatorio: a linha M1a da tabela do implementador afirma mutacao de uma linha so em `src/core/bot.py:262` morta pelo teste da cegueira; eu medi essa mutacao e ela SOBREVIVE (detalhe em Prova). O teste em si esta correto e com dentes. (ii) desvio de metodo meu, causado pelo sandbox: worktree destacado em pasta externa foi negado (`external_directory`, tentei dois caminhos); medi a base por checkout in-place da arvore 2ea449f com restauracao imediata do HEAD e `git status` conferido, e fiz as mutacoes in-place com `git checkout HEAD -- <arquivo>` apos cada uma — o mesmo metodo que o implementador declara ter usado. Estado final do worktree: limpo, suíte verde.
Pendencias: nenhuma de codigo. A ressava de relatorio vai marcada para a retro (nao vira ticket).

## Spec

1. **Aceite cumprido, item a item.**
   - `ufs_sem_corte` com lista diferente do padrao: o modo legado por variaveis usa `"mg, ba"` e afirma `["MG", "BA"]`; o teste dedicado usa `"mg, ba,sp"` e afirma `["MG", "BA", "SP"]` — nenhum dos dois colide com o padrao `["PR", "SC", "RS"]` da SPEC-001 (secao 3.6). ✓
   - `esferas_sem_corte=[]`: teste dedicado `test_esferas_sem_corte_vazia_manda_e_nao_cai_no_padrao`, espelhando o que ja existia para UFs. ✓
   - Cargos com maiuscula: `test_pci_mcp_cargos_aceita_csv_e_preserva_ordem` agora escreve `"Analista de Sistemas, informatica"` e afirma a caixa preservada — mata tanto a mutacao `.lower()` quanto `.upper()`. ✓
   - Avisos separados: `COM_SLUGS` e `COM_NACIONAL` em dois testes, cada um com `len(avisos) == 1` e conteudo conferido (`"pci_slugs"` / `"pci_nacional"` na mensagem) — mais estreito que o `assert avisos` agrupado de antes. ✓
   - Contadores no texto: `novos_cont`/`atualizados_cont` afirmados na linha de log do resumo final (`bot.py:723`, "Ciclo finalizado") e `validos` no heartbeat enviado ao notificador (`bot.py:750`, "Analisei <b>N</b> concursos") — e onde os acumuladores de fato aparecem; nao so contagem de chamadas. ✓
   - Cegueira: `test_mcp_desligado_nao_instancia_scraper` agora chama `bot.executar()` e afirma `"gran" in fontes` antes de negar `"pci_mcp"`. ✓
   - Selo `sem_evidencia`: `test_selo_sem_evidencia_aparece_no_card` com `SEM_TETO` (teto desconhecido), afirmando o selo no card e `motivo_filtro == "sem_evidencia"` na gravacao — o caso que faltava ao lado do `nao_verificado`. ✓
   - Janela do resumo: `test_o_resumo_semanal_pede_sete_dias_ao_banco` dubla `src.core.bot.date` e `src.core.bot.datetime` e afirma `listar_filtrados.assert_called_once_with("2026-11-16 14:30:45")` — literal calculado a mao (2026-11-23 menos 7 dias), formato `AAAA-MM-DD HH:MM:SS`, nunca a expressao que o codigo usa. ✓
   - Vocabulario: `git grep -c varredura` — base 25 linhas em `src/core/bot.py` e 10 em `tests/test_concurso_bot.py`; ponta 23 e 8. Exatamente as 4 ocorrencias novas trocadas; legado intacto. ✓
2. **Escopo:** `git diff --stat 2ea449f..82db274` toca so os 3 arquivos do `toca`. A unica mudanca em producao e texto (duas palavras), como o ticket autoriza. Nenhum ganho de comportamento nao pedido.
3. **Bate com a spec:** sem mudanca de comportamento de producao — nada a conferir contra a SPEC alem do que os testes afirmam, e todos afirmam o que a tabela de padroes da secao 3.6 e o codigo atual fazem. O desvio do nome do teste de cargos (o plano sugeria `test_pci_mcp_cargos_minusculiza_termo_com_maiuscula`) e correto: `_normalize_pci_mcp_cargos` (`config/loader.py:115-123`) preserva a caixa, e o aceite pedia o termo com maiuscula no teste existente; o plano de testes e subordinado ao aceite. Desvio bem documentado pelo implementador.

## Prova

4. **Numeros reais, medidos por mim:**
   - ponta: 545 passed / 0 failed / 0 pulado (`-rs` nao listou nada), medido duas vezes (antes e depois das mutacoes);
   - base: 539 passed / 0 failed, medido no mesmo worktree com checkout da arvore 2ea449f e restauracao imediata (o sandbox negou worktree destacado externo; metodo documentado acima, `git status` limpo nas duas bordas);
   - conta fecha: 539 + 6 testes novos (`test_esferas_sem_corte_vazia...`, `test_pci_mcp_com_nacional...`, `test_contadores_do_mcp_e_do_gran...`, `test_validos_do_mcp_e_do_gran...`, `test_selo_sem_evidencia...`, `test_o_resumo_semanal_pede_sete_dias...`) = 545. Igual ao relatorio do implementador.
5. **TDD / prova por mutacao (desenho do ticket: tudo nasce verde, a prova e a tabela):** graduei pelo nivel M (uma mutacao por item de aceite) e reproduzi 12 das 13 linhas da tabela com edits proprios, cada um seguido de `pytest -k <teste> -q --tb=line` e `git checkout HEAD -- <arquivo>`:

   | Minha mutacao | Alvo | Teste | Resultado |
   |---|---|---|---|
   | devolver sempre o padrao `["PR","SC","RS"]` | `config/loader.py:101-102` | `test_ufs_sem_corte_aceita_csv...` + `test_chaves_por_area_no_modo_legado...` | morta (2 failed: `['PR','SC','RS'] != ['MG','BA','SP']`) |
   | `valor is None` → `not valor` (esferas) | `config/loader.py:110` | `test_esferas_sem_corte_vazia...` | morta (`['federal'] != []`) |
   | forcar `.lower()` nos cargos | `config/loader.py:123` | `test_pci_mcp_cargos_aceita_csv...` | morta (`'analista de sistemas' != 'Analista de Sistemas'`) |
   | `if target["pci_slugs"]:` → `if False:` | `config/loader.py:246` | `test_pci_mcp_com_slugs...` | morta (`0 == 1`) |
   | `if target["pci_nacional"]:` → `if False:` | `config/loader.py:248` | `test_pci_mcp_com_nacional...` | morta (`0 == 1`) |
   | remover `novos_cont += resultado == "novo"` | `src/core/bot.py:284` | `test_contadores_do_mcp_e_do_gran...` | morta |
   | remover `atualizados_cont += ...` | `src/core/bot.py:285` | idem | morta |
   | remover `validos += 1` do laco MCP | `src/core/bot.py:281` | `test_validos_do_mcp_e_do_gran...` | morta |
   | remover linha do selo no card | `src/core/bot.py:1041` | `test_selo_sem_evidencia...` | morta (card sem "⚠️") |
   | `timedelta(days=7)` → `days=1` | `src/core/bot.py:835` | `test_o_resumo_semanal_pede_sete_dias...` | morta (call not found) |
   | `"%Y-%m-%d %H:%M:%S"` → `"%Y-%m-%d"` | `src/core/bot.py:836` | idem | morta |

   **A ressava (M1a):** a tabela do implementador afirma que `if self.mcp_scraper:` → sempre-true em `bot.py:262` (porta desligada avaliada na saude) e morto por `test_mcp_desligado_nao_instancia_scraper`. Medi: essa mutacao de uma linha so **sobrevive** — `None.capturar_concursos()` levanta `AttributeError`, o `except` engole, e `"pci_mcp"` nunca chega ao diagnostico (1 passed). A mutacao composta que o item descreve (guard bypassado **e** coleta protegida: `itens_mcp = (... if self.mcp_scraper else [])`) e morta: `assert 'pci_mcp' not in ['gran', 'pci_mcp']`. Ou seja: **o teste tem dentes e o aceite esta provado**; o que nao se sustenta e a linha da tabela tal como escrita, que descreve uma mutacao que o teste nao pega. Provavelmente o implementador aplicou um edit composto e o resumiu como edit de linha. Vai para a retro: linha de tabela de mutacao descreve o edit exato, senao a prova nao e conferivel.
6. **Os testes provam comportamento:** pela costura (loader pela funcao que monta a config; bot por `executar()` com portas/notificador/banco dublados, dubles so na fronteira, relogio dublado como o plano pede). Oraculos independentes: literais escritos a mao (`["MG","BA","SP"]`, `"2 novos e 1 atualizações"`, `"2026-11-16 14:30:45"` com a conta no comentario). Nenhum tautologico, nenhum acoplado a funcao privada, nenhum duble fora da fronteira. A checagem imaginaria (condicao invertida, literal trocado, ramo apagado) foi feita de verdade, acima. Nenhum teste existente perdeu forca: todas as trocas sao de `truthy` → contagem exata, lista colidente → lista distinta, ausencia nua → ausencia apos execucao com assercao positiva junto.

## Padroes

7. **Regras do projeto:** idioma pt-BR nos commits e textos; identificadores sem acento; sem dependencia nova; teste sem rede (so dubles); sem segredo; sem push (branch local, ponta `82db274` bate com a do ticket); `kanban/` e `.esteira/` nao commitados; IDs do quadro fora do codigo; vocabulario conforme o `GLOSSARIO.md` (`varredura` → `rodada` so nos quatro trechos novos, legado preservado como o aceite manda). Commits `test:` → `test:` → `chore:`: sem `feat:` e sem `docs:` — coerente com o desenho do ticket (tudo nasce verde, unica mudanca em producao e texto; nao havia documentacao a atualizar). O `chore:` em vez de `docs:` para o texto de vocabulario e aceitavel: e texto de comentario/log, nao documento.
8. **Cheiros:** nenhum relevante. Os dois testes de contadores compartilham a montagem via `_montar`/`_item` como os vizinhos da classe; o `SEM_TETO` novo segue o padrao dos dicts de cenario ao lado. Nada a apontar.

## Veredito

`APROVADO COM RESSALVAS` — o aceite esta cumprido e provado com medida propria (suíte, base e ponta, e 11 mutacoes minhas matando os 9 itens); a ressava e so de relatorio: a linha M1a da tabela de mutacao do implementador nao se reproduz como descrita, ainda que o teste que ela cita esteja correto e com dentes (comprovado com a mutacao composta). Ressava de relatorio, para a retro, sem ticket novo.
