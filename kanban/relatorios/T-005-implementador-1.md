ENTREGUE
Esteira: implementador · glm (zai-coding-plan/glm-5.3) · nível M+ · esforço high · 2026-11-23 11:25 → 2026-11-23 11:51 (27 min)
Resumo: Schema v6 aditivo e idempotente (sete colunas em `_ensure_schema`, `_create_v3_table` e `_migrate_to_v3`), gravação dos sete campos em `atualizar_concurso` (COALESCE nas descrições, decisão que vence quando vem valor e preserva quando vem `None`) e a consulta `listar_filtrados` que o resumo semanal usa, em três fatias test:→feat: mais um chore: de esqueleto e um docs: final.
Arquivos: `src/database/manager.py` · `tests/test_database_manager.py` (ambos dentro do `toca`).
Commits (ordem):
- e9bcc9a test: schema v6 exige sete colunas em banco novo e migrado
- e72b5d2 feat: schema v6 aditivo com sete colunas no ensure_schema e no create
- dd35b3f chore: esqueleto dos campos v6 em atualizar_concurso e do listar_filtrados
- f5e66cf test: gravacao dos campos v6 com coalesce e decisao que vence
- f840b8b feat: atualizar_concurso grava os sete campos v6 no insert e no update
- 83d85f9 test: listar_filtrados exige so filtrado, da area, desde a data, teto desc
- a3e1218 feat: listar_filtrados consulta filtrados da area ordenados por teto desc
- e6b399e docs: schema v6 no cabecalho do manager, regras de gravacao e contrato do listar_filtrados

Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q` → base 296 passed / 0 failed (medida por mim antes de qualquer mudança; o prompt não trouxe base do integrar) · ponta 310 passed / 0 failed · `--collect-only -q` → 310 tests collected. Lint: não configurado no repo, não rodou. Sem variáveis de ambiente ou marcadores especiais; sem testes pulados (`-rs` não listaria nada — 0 skipped em todas as corridas).
Vermelhos vistos (motivo certo, saída colada):
- fatia 1: `4 failed, 26 passed` em `tests/test_database_manager.py` — `AssertionError` de conjunto de colunas (`'elegibilidade'`, `'regiao'`, `'salario_teto'`, `'cargos_total'`... faltando no `PRAGMA table_info`), incluindo o `test_creates_table_on_fresh_db` atualizado.
- fatia 2: `5 failed, 31 passed` — `AssertionError` de valor não persistido (`assert None == 'filtrado'`), não `TypeError` (o esqueleto do chore: aceitava os kwargs).
- fatia 3: `5 failed, 36 passed` — `NotImplementedError` do esqueleto, em todos os cinco.
Testes que nascem verdes: `test_linha_pre_v6_nao_e_tocada` — guarda. Antes do feat da fatia 2 o UPDATE nem toca em `elegibilidade`, então ela passa por construção; existe para pegar a mutação `elegibilidade = ?` sem COALESCE (as outras guardas da assimetria, `test_coalesce_preserva_*` e `test_elegibilidade_e_preservada_quando_vem_none`, nasceram vermelhas porque o primeiro write também dependia do feat). Nenhum outro nasceu verde.
Desvios e riscos:
- **"Exceção ao COALESCE" de `elegibilidade`/`motivo_filtro`:** os dois comportamentos exigidos (sobrescrever quando vem valor, preservar quando vem `None`) têm como única implementação comum `COALESCE(?, col)` — atribuição pura apagaria com `None`, o que o ticket proíbe. A assimetria fica no comentário do SQL e no histórico v6 do módulo; a SPEC-001 (3.5, R-13) prescreve comportamento, não SQL, então não há discordância. Revisor: mutação `COALESCE(?, elegibilidade)` → `?` é pega por dois testes.
- `test_creates_table_on_fresh_db` (pré-existente, contava na base) teve o oráculo atualizado do conjunto v5 para o v6 (`COLUNAS_V6`): mudança de schema é o próprio objeto do ticket, não afrouxamento.
- `_migrate_to_v3` também ganhou as sete colunas no CREATE. Fora da letra do aceite, mas dentro do `toca`: o arquivo mantinha os dois CREATE com conjuntos idênticos, e o `_ensure_schema` aditivo cobriria o caminho v1/v2 de qualquer forma; a mudança evita drift entre os dois pontos de criação.
- `chore:` de esqueleto (dd35b3f): assinatura de `atualizar_concurso` estendida com os sete kwargs aceitos-e-ignorados + `listar_filtrados` levantando `NotImplementedError`, para o vermelho das fatias 2 e 3 nascer do corpo (asserção / `NotImplementedError`), não de `TypeError` de assinatura.
- Em `test_listar_filtrados_respeita_desde` o arranjo de `ultima_atualizacao` entra por SQL direto (a interface pública não retrodata timestamp); a verificação é só pela interface. Declarado em comentário no teste.
- `listar_filtrados` devolve exatamente `nome, uf, salario_teto, motivo_filtro, link` (o aceite pede "ao menos" esses cinco); a comparação `>= desde` como texto está documentada em comentário e na docstring, como o ticket pede.
Pendências: nenhuma deste ticket. Decidir elegibilidade (`src/core/elegibilidade.py`), chamar `listar_filtrados` e montar o resumo são outros tickets por design; a fiacao que grava elegibilidade vem depois.
