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

**Decisão do arquiteto (2026-11-26 15:01):** MEDIDA DE 26/11/2026 (leitura do banco e do log de producao, pela Tailscale): existe uma TERCEIRA classe de estrago, diferente das cinco linhas fundidas, e ela NAO esta no escopo deste ticket. Registro aqui para o dono decidir, porque o R-93 fixa a lista de cinco e mudar a lista e decisao dele.

O QUE EU MEDI. O banco tem 1.758 linhas (EDUCACAO 971, SOCIOLOGIA_ARTES 412, TI 375) e 159 sem pci_id. Quatro linhas carregam a PAGINA-INDICE do Gran no campo link, como se fosse link de edital: 1038, 1265, 1284 e 1404. O log traz 109 avisos de colisao de nome, e a linha id=1284 (area TI, sem pci_id, link da pagina-indice) aparece com TRES nomes diferentes ao longo do tempo: Francisco Macedo (PI), Serra Grande (PB) e, hoje, Luiz Alves (SC).

O QUE ISSO E, caso por caso, ja descontando o que e por design (a mesma vaga em areas diferentes e esperado, porque cada area e um feed proprio):
- id=1284 e DUPLICATA da id=1158 na mesma area TI. As duas sao o concurso da Prefeitura de Luiz Alves - SC; a 1158 tem a chave 296083 e link de edital, a 1284 nao tem chave e tem o link da pagina-indice. A 1284 e a linha onde os fallbacks fracos foram caindo, e e por isso que ela trocou de nome tres vezes.
- id=1265 e lixo: nome «Nome nao identificado», sem chave, link da pagina-indice.
- id=1404 (Nova Boa Vista RS, TI, sem chave) parece LEGITIMA: e vaga de Professor de Informatica, e o par com chave dela existe so na area EDUCACAO. Nao mexer.
- id=1038 tem a chave certa e o link errado. Identidade correta, nao e caso de reparo.

POR QUE NAO ENTRA NESTE TICKET: aqui o estrago e duas vagas numa linha, e o reparo SEPARA. Ali o estrago e uma vaga em duas linhas, e o reparo juntaria ou descartaria. E o criterio de aceite deste ticket diz, com razao, que nenhuma linha e apagada em nenhum caminho do script.

O QUE O T-020 JA FAZ COM ELAS, e isto e bom: depois da migracao, a 1284 ou recebe a chave na primeira rechave (R-81) ou nunca mais e casada, porque a busca por chave passa a ter desempate e sempre devolve a 1158. Ou seja, ela para de absorver identidade alheia. Ela fica no banco como linha morta, com estado_usuario «ativo», sem estrela do Lucas em risco.

RECOMENDACAO AO DONO: deixar como esta por enquanto. Linha morta sem estrela nao notifica, nao atrapalha e nao e urgente. Se um dia incomodar, e um ticket proprio de limpeza, com dry-run, e nao um apendice deste. Se quiser o contrario, e uma frase nas suas notas aqui.

## Notas do Lucas
<!-- Ao rodar o reparo em producao, cole aqui a saida do --dry-run, a contagem antes e depois, o caminho do
     backup do banco e, no comeco de uma linha, a marca "Recurso notebook: feito". -->
