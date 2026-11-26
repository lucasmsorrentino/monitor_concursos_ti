BLOQUEADO
Esteira: implementador · opus (claude-opus-5-5) · nível G- · esforço high · 2026-11-26 13:11 → 2026-11-26 13:20 (10 min)
Resumo: Terceira rodada. O ACHADO 2 (critério de nulidade) está feito em test → fix → docs. O critério agora é um só: nulo é só NULL ou '', e qualquer outro valor é chave. Ele vale no Python (`_pci_id_ou_none`), no SQL (`_PCI_ID_SQL`) e no índice, e o bot já usava o mesmo. O ACHADO 1 (desempate dos fallbacks sem chave) está parado. Medi que a «ordem antiga» depende do banco: num v6 com `idx_editais_pci`, que é o formato do banco de produção, as três buscas já usavam o índice de PCI ANTES da migração e a migração não muda nada. Só num v6 sem esse índice, que é o do revisor, a ordem era a do nome em BINARY. O teste que a nota pede (ID 2 nos três fallbacks) codifica o banco do revisor. O princípio da nota («igual ao resultado de antes da migração para as linhas que existem hoje») codifica o de produção. Os dois exigem ORDER BY diferentes. Não consegui confirmar o formato da produção: o SSH de leitura foi negado.
Arquivos: src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md, CLAUDE.md. Todos estão no «toca».
Commits:
  0dda815 test: um criterio so de nulidade do pci_id na busca e na fusao
  59d67a6 fix: o pci_id tem um criterio so de nulidade, na busca, na fusao e no indice
  1482816 docs: o criterio unico de nulidade do pci_id na ADR-0005 e no CLAUDE.md
Testes: PYTHONDONTWRITEBYTECODE=1 "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs -p no:cacheprovider → base ff8e48d (o merge do arquiteto) «603 passed in 85.83s» · ponta 59d67a6 «607 passed in 65.16s», 0 failed, 0 skipped. O 1482816 só mexe em .md, então o código da ponta é o mesmo. A conta fecha: 603 + 4 testes novos (um parametrizado em 3 casos, mais 1). Não há variáveis de ambiente do projeto nem marcadores. Lint: não configurado.
  Vermelho do 0dda815, rodado com o mesmo executável, `-m pytest -q -p no:cacheprovider --tb=line tests/test_database_manager.py`: «3 failed, 63 passed in 0.91s». As falhas:
  - `[nome]` e `[entidade]` de `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks`: `buscar_registro` devolveu a linha de pci_id " " em vez de None. O SQL recusou e o fallback por entidade, que no Python tirava o espaço, aceitou.
  - `test_atualizacao_sem_pci_id_preserva_as_duas_linhas_e_as_duas_chaves`: «AssertionError: o pci_id gravado se perdeu». A fusão apagou a linha do 296044 e a chave não foi herdada.
  Verde: «66 passed in 1.07s» no módulo e 607 na suíte.
Testes que nascem verdes: `test_pci_id_legado_nao_vazio_recusa_outro_pci_id_nos_tres_fallbacks[link]`. O filtro SQL do link já recusava o " ". Fica como guarda das três camadas.
Desvios e riscos:
  1. ACHADO 2. Escolhi «nulo = NULL ou ''» e não «vazio depois de tirar espaço». Esse critério é o do índice que já existe (`COALESCE(pci_id, '')`), o do bot (`src/core/bot.py:959`, `dados.get('pci_id') or None`) e o que o revisor pediu («preservando valores legados não vazios»). Ele não troca a expressão do índice e não pede TRIM, que no SQLite só tira espaço enquanto o `strip()` do Python tira todo branco: seriam de novo duas camadas discordando. Não há caso especial para espaço: o `strip()` saiu. A consequência é que um `pci_id=" "` gravado pela API vira chave. Isso é coerente nas três camadas, e nenhum scraper produz esse valor.
  2. ACHADO 1: não implementado. É o motivo do bloqueio (pergunta abaixo).
  3. Fora do pedido, e não mexi: a busca pelo próprio `pci_id` (`WHERE area = ? AND pci_id = ?`) também não tem desempate. Desde o v7, duas linhas de nomes diferentes podem ter o mesmo pci_id. Hoje o plano usa `idx_editais_pci`, que desempata por id.
  4. A tentativa de ler o banco de produção (somente leitura, `mode=ro`, `PRAGMA index_list`) foi negada pelo classificador de permissões. Não houve outro acesso.
Pendências: o ACHADO 1, conforme a resposta abaixo. O R-97 fica no T-026 e o reparo das linhas colididas no T-023, como antes. O gate «OK do Lucas:» segue aberto.

## Pergunta (ACHADO 1): qual banco define a «ordem antiga»?

Evidência medida no SQLite 3.45.3, com as consultas reais (`SELECT *`) e o schema v6 completo. Linhas: (1, "ifsp", pci "100") e (2, "IFSP", pci "900"), com o mesmo link. Script em C:\Users\Lucas\AppData\Local\Temp\claude\1708a0d2d4d206f4\4bb43b2e-aa52-4ff0-9f2e-585919fc8355\scratchpad\plano2.py.

| Banco | Fallback | Plano | Ordem |
| --- | --- | --- | --- |
| v6 SEM idx_editais_pci (o do revisor) | link, nome, entidade | sqlite_autoindex_editais_1 | [2, 1] |
| o mesmo, migrado para v7 | link, nome, entidade | idx_editais_pci | [1, 2] ← a regressão relatada |
| v6 COM idx_editais_pci | link, nome, entidade | idx_editais_pci | [1, 2] |
| o mesmo, migrado para v7 | link, nome, entidade | idx_editais_pci | [1, 2] ← nada muda |

Quem tem o índice: o código antigo só criava `idx_editais_pci` no caminho do `ALTER TABLE ... ADD COLUMN pci_id`, que roda quando um banco anterior ao v5 é migrado. Um banco criado do zero depois de 08/08/2026 nascia sem o índice. O banco de produção existe desde a era só-Gran (junho de 2026), então passou pelo ALTER e muito provavelmente tem o índice. Não consegui confirmar.

Opções:
- **A. `ORDER BY nome, id`** nos três fallbacks, o que a nota pede ao pé da letra. Reproduz o banco do revisor e passa no teste pedido (ID 2). Se a produção tem o índice, isso MUDA a linha escolhida em produção sempre que dois candidatos empatam. É exatamente «mover história de um edital para outro em silêncio», só que causado pelo conserto e não pela migração.
- **B. `ORDER BY pci_id, id`** (NULL primeiro, que é a ordem do `idx_editais_pci`) nos três fallbacks. Num banco com o índice, é idêntico ao resultado de antes da migração e ao de hoje. Num banco criado do zero depois de 08/08 (cópias de desenvolvimento, testes), muda o resultado. O teste seria escrito em v6 COM o índice e afirmaria ID 1 nos três fallbacks, o contrário do que a nota pede.
- Não existe um ORDER BY que reproduza os dois bancos: antes da migração, eles próprios davam respostas diferentes.

Recomendação: **B, se a produção tiver o índice.** Para decidir com dado e não com palpite, rode no notebook (só leitura):

```
cd ~/monitor_concursos_ti && .venv/bin/python -c "import sqlite3; c=sqlite3.connect('file:data/concursos.db?mode=ro', uri=True); print(c.execute('PRAGMA index_list(editais)').fetchall()); print(c.execute(\"SELECT area, link, COUNT(*) FROM editais WHERE link IS NOT NULL AND link != '' GROUP BY area, link HAVING COUNT(*) > 1\").fetchall()); print(c.execute('SELECT area, LOWER(nome), COUNT(*) FROM editais GROUP BY area, LOWER(nome) HAVING COUNT(*) > 1').fetchall())"
```

A primeira linha diz se existe `idx_editais_pci`. Se existir, vale B, e o teste da nota troca o ID esperado. Se não existir, vale A. As duas outras linhas contam os empates de link e de nome que existem hoje em produção. Se derem vazio, nenhuma das opções muda uma linha de produção hoje, e a escolha só vale para o futuro.
