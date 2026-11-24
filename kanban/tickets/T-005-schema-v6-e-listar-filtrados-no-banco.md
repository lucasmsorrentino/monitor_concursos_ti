---
id: T-005
titulo: Schema v6 e listar_filtrados no banco
tipo: codigo
nivel: M+
status: integrado
repo: principal
spec: [SPEC-001, R-10]
depende_de: []
toca: [src/database/manager.py, tests/test_database_manager.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T18:00-03:00
branch: t/T-005-schema-v6-e-listar-filtrados-no-banco
executor: script
executor_impl: glm
corpo_lancado: f9d4d69520b4
fora_do_toca: []
ponta: e6b399e670da0b534e566034ba4788422fa1ef8d
executor_rev: agy-argon
executor_int: script
---
# T-005 · Schema v6 e listar_filtrados no banco

## Contexto

A elegibilidade decide se um concurso vira notificacao. Essa decisao precisa **ficar gravada**: para nao
renotificar, para o resumo semanal poder lista-la, e para o Lucas poder auditar o silencio. Hoje a tabela
`editais` nao tem onde guardar nada disso, nem a UF, nem a regiao, nem o teto.

Este ticket entrega o schema v6 (aditivo) e a consulta que o resumo semanal usa. Ninguem grava elegibilidade
aqui ainda: a fiacao vem depois. O contrato esta na SPEC-001 secao 3.5.

O `DatabaseManager` ja migra schema de forma aditiva e idempotente em `_ensure_schema`, guardando cada
`ALTER TABLE ... ADD COLUMN` por uma checagem de `PRAGMA table_info`. Siga exatamente esse padrao: as colunas
`fonte` e `pci_id` do v5 sao o exemplo a copiar.

## Critério de aceite

- [ ] `_ensure_schema` passa a garantir sete colunas novas em `editais`, cada uma guardada pela checagem de
      `PRAGMA table_info`, como as do v5: `uf TEXT`, `regiao TEXT`, `esfera TEXT`, `cargos_total INTEGER`,
      `salario_teto REAL`, `elegibilidade TEXT`, `motivo_filtro TEXT`.
- [ ] `_create_v3_table` (a criacao do banco novo) passa a trazer as mesmas sete colunas, para banco novo e
      banco migrado terminarem com o **mesmo** conjunto de colunas.
- [ ] **Migracao idempotente:** abrir o banco duas, tres vezes seguidas nao levanta e nao duplica coluna.
- [ ] **Nada se perde:** banco com linhas do v5 (com `fonte` e `pci_id` preenchidos) mantem todas as linhas e
      todos os valores depois da migracao, e as colunas novas ficam `NULL`.
- [ ] `atualizar_concurso` aceita os sete campos novos como argumentos nomeados opcionais, com `None` por
      padrao, e os grava. No `UPDATE`, cada um entra com `COALESCE`, como `fonte`, `pci_id` e
      `data_fim_inscricao` ja fazem: fonte que nao conhece o campo **nao apaga** o que a outra ja descobriu.
- [ ] **Excecao ao `COALESCE`:** `elegibilidade` e `motivo_filtro` sao sobrescritos quando vem valor, e
      preservados quando vem `None`. Decisao nova vence decisao velha (R-13 da SPEC-001), mas rodada que nao
      avalia nao apaga a decisao.
- [ ] `buscar_registro` passa a devolver as sete colunas novas no dict, junto com as que ja devolve.
- [ ] `listar_filtrados(desde: str) -> list[dict]` devolve as linhas **da area do manager** com
      `elegibilidade = 'filtrado'` e `ultima_atualizacao >= desde`, ordenadas por `salario_teto` decrescente
      com `NULL` no fim. Cada dict traz ao menos `nome`, `uf`, `salario_teto`, `motivo_filtro` e `link`.
- [ ] `listar_filtrados` nao vaza area: linha filtrada de outra area nao aparece.
- [ ] `listar_filtrados` com `desde` no futuro devolve lista vazia, sem levantar.
- [ ] Linha anterior ao v6 tem `elegibilidade` nulo e **conta como elegivel**. Este ticket nao faz backfill,
      nao apaga nada e nao reavalia nada: so cria o espaco.

## Plano de testes

Costura: os metodos publicos do `DatabaseManager` — o proprio construtor (que dispara `_ensure_schema`),
`atualizar_concurso`, `buscar_registro` e `listar_filtrados` — sobre um banco em `tmp_path`, como
`tests/test_database_manager.py` ja faz. Pega a migracao, a gravacao, o `COALESCE` e a consulta.
**Nao pega** quem decide a elegibilidade nem como o resumo e escrito.

Oráculo: o conjunto de colunas esperado e a tabela da SPEC-001 secao 3.5, escrita a mao no teste; os valores
esperados sao literais inseridos pelo proprio teste. A conferencia de coluna sai de `PRAGMA table_info`, que e
fonte independente do codigo de migracao.

Testes que nascem vermelhos em `tests/test_database_manager.py`:

- `test_banco_novo_tem_as_colunas_do_v6` — banco criado do zero traz as sete colunas, conferidas por
  `PRAGMA table_info` contra uma lista literal.
- `test_migracao_do_v5_acrescenta_as_colunas` — monta a mao uma tabela no formato v5 com duas linhas, abre o
  manager, e as sete colunas aparecem com `NULL` sem perder as duas linhas nem os valores de `fonte` e
  `pci_id`.
- `test_migracao_e_idempotente` — abrir o mesmo banco tres vezes nao levanta, e a contagem de colunas nao
  muda da segunda para a terceira.
- `test_atualizar_concurso_grava_campos_novos` — insere com os sete campos e `buscar_registro` os devolve.
- `test_coalesce_preserva_uf_quando_vem_none` — grava `uf="PR"`, regrava o mesmo concurso com `uf=None`, e a
  `uf` continua `"PR"`.
- `test_coalesce_preserva_salario_teto_quando_vem_none` — idem para `salario_teto`.
- `test_elegibilidade_e_sobrescrita_quando_vem_valor` — grava `elegibilidade="filtrado"`, regrava com
  `elegibilidade="elegivel"`, e vale `"elegivel"`.
- `test_elegibilidade_e_preservada_quando_vem_none` — grava `"filtrado"`, regrava com `None`, e continua
  `"filtrado"`.
- `test_listar_filtrados_so_traz_filtrado` — tres linhas, uma `filtrado`, uma `elegivel`, uma `NULL`: so a
  primeira volta.
- `test_listar_filtrados_respeita_desde` — duas linhas filtradas com `ultima_atualizacao` diferentes; `desde`
  entre as duas traz uma.
- `test_listar_filtrados_nao_vaza_area` — dois managers de areas diferentes, cada um com uma linha filtrada:
  cada `listar_filtrados` traz so a sua.
- `test_listar_filtrados_ordena_por_teto_desc_com_null_no_fim` — tres linhas com teto 12000, 3000 e `NULL`
  voltam nessa ordem.
- `test_listar_filtrados_futuro_vazio` — `desde` em 2099 devolve `[]`.
- `test_linha_pre_v6_nao_e_tocada` — linha migrada com `elegibilidade` nulo segue nula depois de uma
  gravacao que nao passa o campo.

## Fora do escopo

- Decidir elegibilidade. Isso e de `src/core/elegibilidade.py`, noutro ticket.
- Chamar `listar_filtrados` ou montar o texto do resumo. Outros tickets.
- Backfill de `uf`, `esfera` ou `elegibilidade` em linha antiga. A SPEC-001 secao 3.5 diz que linha pre-v6
  conta como elegivel e nao se reavalia.
- `DROP COLUMN`, recriar tabela, migrar dado entre colunas. A migracao e so aditiva (`kanban/REGRAS.md`).
- Indice novo, a nao ser que um teste de `listar_filtrados` mostre necessidade. O banco tem centenas de
  linhas, nao milhoes.

## Notas do arquiteto

- **M+ e nao G:** o padrao de migracao aditiva idempotente ja esta escrito no arquivo e e so copiar, e o
  revisor confere coluna por coluna com `PRAGMA table_info`. O sinal `+` e por dois detalhes que mudam
  comportamento: as sete colunas tem de entrar **nos dois** caminhos (banco novo e banco migrado), e duas
  delas fogem do `COALESCE` de proposito.
- **Por que `elegibilidade` nao usa `COALESCE`:** as outras colunas descrevem o concurso e qualquer fonte que
  saiba o valor esta certa. A elegibilidade descreve uma **decisao**, e a decisao de agora vence a de ontem
  (o edital saiu, o teto mudou). Mas rodada em que o filtro esta desligado passa `None` e nao pode apagar a
  decisao gravada. Dai a assimetria.
- **Cuidado com a producao.** O banco de verdade (`data/concursos.db` no notebook) tem o historico de todos
  os concursos ja notificados e os `estado_usuario` que o Lucas marcou a mao nos botoes. `ALTER TABLE ADD
  COLUMN` nao mexe em linha existente, e e por isso que a migracao e so aditiva. Nenhum `UPDATE` em massa.
- O `estado_json_isolado` do `tests/conftest.py` ja desvia o estado em JSON para `tmp_path`, mas **nao** o
  banco: use `tmp_path` explicito no `db_path` do manager, como os testes que ja existem fazem.
- `listar_filtrados` compara `ultima_atualizacao >= desde` como texto. As duas pontas sao
  `AAAA-MM-DD HH:MM:SS` (`CURRENT_TIMESTAMP` do SQLite), formato em que ordem lexicografica e ordem
  cronologica. Documente isso num comentario para ninguem "melhorar" depois.

## Histórico
- 2026-11-23 11:16 backlog → pronto · liberado: OK do Lucas em 23/11/2026
- 2026-11-23 11:25 pronto → fazendo · implementador · glm M+ high
- 2026-11-23 11:51 fazendo → entregue · implementador: ENTREGUE · relatório T-005-implementador-1.md · 27 min
- 2026-11-23 17:53 entregue → revisando · revisor · agy-argon M+ high
- 2026-11-23 18:00 revisando → aprovado · revisor: APROVADO · relatório T-005-revisor-1.md · 7 min
- 2026-11-23 18:00 aprovado → integrando · integrador · script
- 2026-11-23 18:00 integrando → integrado · integrador: INTEGRADO · relatório T-005-integrador-1.md · 0 min
