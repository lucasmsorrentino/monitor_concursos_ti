---
id: T-023
titulo: Reparar as cinco linhas de identidade colidida
tipo: codigo
nivel: M-
status: backlog
repo: principal
spec: [SPEC-003, R-91, R-92, R-93, R-94]
depende_de: [T-020]
toca: [scripts/reparar_identidade.py, tests/test_reparar_identidade.py]
recursos: [notebook]
afinidade:
retornos: 0
---
# T-023 · Reparar as cinco linhas de identidade colidida

## Contexto

O spike de 24/11/2026 (`docs/CONTABILIDADE-POS-DEPLOY.md`, secao 5) confirmou **cinco** linhas em que dois
editais distintos se fundiram: `563`, `1131`, `1445`, `1587` e `1681`. A `1681` e a Prefeitura de Blumenau -
SC, elegivel, da Regiao Sul, e o segundo edital dela nunca foi notificado.

Depois do ticket da identidade o banco passa a aceitar as duas linhas, mas as cinco **ja** fundidas continuam
fundidas: o dado de um edital esta sobrescrito pelo do outro, e separar exige decidir o que pertence a quem.
E por isso que o reparo e script com plano antes de escrever, e nao parte da migracao.

## Critério de aceite
- [ ] O script tem `--dry-run` **como padrao**: sem uma flag explicita de escrita, ele nao escreve nada (R-91)
- [ ] O `--dry-run` imprime, por linha afetada, o que fica na linha original e o que vai para a linha nova
- [ ] O `estado_usuario` da linha original e preservado; a linha nova nasce com o padrao (R-92)
- [ ] Nada e notificado: a linha nova nasce como **ja notificada** (R-92)
- [ ] Os cinco `id` confirmados entram no reparo; `930` e `1113` **nao** entram (R-93)
- [ ] O script confere a contagem de linhas antes e depois e **aborta** se a diferenca nao for a esperada
      (R-94)
- [ ] O script e idempotente: rodado duas vezes, nao cria linha duplicada
- [ ] Nenhuma linha e apagada, em nenhum caminho do script
- [ ] Suite verde; o teste usa banco temporario, nunca o de producao

## Plano de testes
Costura: a funcao que monta o **plano** (decide o que separar, sem escrever) e a que **aplica** o plano,
sobre banco temporario em arquivo. Pega: o plano, a preservacao do `estado_usuario`, a idempotencia e o abort
por contagem. Nao pega: o banco de producao, que nunca entra na suite.
Oráculo: os dados reais das cinco linhas, transcritos a mao do `docs/CONTABILIDADE-POS-DEPLOY.md` secao 3.1
para uma fixture.

Testes que nascem vermelhos:

- `test_sem_flag_de_escrita_nao_escreve_nada`
- `test_plano_separa_os_dois_editais_da_linha_colidida`
- `test_estado_usuario_fica_na_linha_original`
- `test_linha_nova_nasce_como_ja_notificada`
- `test_os_dois_duvidosos_ficam_de_fora`
- `test_rodar_duas_vezes_nao_duplica`
- `test_aborta_quando_a_contagem_nao_fecha`

## Fora do escopo
- Decidir os duvidosos `930` (UNIFEI) e `1113` (UERJ). E decisao do dono, caso a caso.
- Rodar em producao: isso e o recurso `notebook`, passo humano, com backup do banco antes.
- Mexer no `src/database/manager.py`. A identidade e o outro ticket.

## Notas do arquiteto

**Por que M−:** a regra e conhecida e o modulo e um script novo, isolado. O risco nao esta no codigo, esta na
execucao, e por isso ela e passo humano com backup, e nao parte da entrega do agente.

**De onde vem o dado do segundo edital:** do log de producao, nao do banco, porque o banco guarda so o estado
final. A secao 3.1 do `docs/CONTABILIDADE-POS-DEPLOY.md` tem os `pci_id` e os nomes das duas pontas de cada
colisao.

**O risco de o reparo virar flood.** Se a linha nova nascer como inedita, a varredura seguinte manda card de
concurso que o Lucas ja viu, cinco vezes. Nascer «ja notificada» e requisito, nao detalhe de implementacao.

## Notas do Lucas
<!-- Ao rodar o reparo em producao, cole aqui a saida do --dry-run, a contagem antes e depois, o caminho do
     backup do banco e, no comeco de uma linha, a marca "Recurso notebook: feito". -->
