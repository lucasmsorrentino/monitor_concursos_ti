---
id: T-020
titulo: Identidade do concurso: o pci_id que discorda vence o nome
tipo: codigo
nivel: G-
status: pronto
repo: principal
spec: [SPEC-003, R-80, R-81, R-82, R-83, R-84, R-85, R-86, R-99]
depende_de: []
toca: [src/database/manager.py, tests/test_database_manager.py, docs/adr/0005-identidade-do-concurso.md, CLAUDE.md]
recursos: []
afinidade:
retornos: 3
atualizado: 2026-11-26T14:57-03:00
branch: t/T-020-identidade-do-concurso-o-pci-id-que-disc
executor: codex
executor_impl: opus
corpo_lancado: 34d74ae4a9e8
sessao: 69c0b69e-cc45-4604-ad92-873be6a2fdf3
fora_do_toca: []
ponta: 09b4d0a0a12e7419e95f446aab99f8b600ff81db
executor_rev: codex
motivo: escopo reduzido por decisao do dono em 26/11/2026: a regra de nome e fusao saiu para o T-028 (R-100) e o R-99 conservador entra no lugar
---
# T-020 · Identidade do concurso: o pci_id que discorda vence o nome

## Contexto

Dois editais distintos do mesmo orgao, na mesma area, ocupam uma linha so do banco, e cada rodada
sobrescreve o dado do outro. Em 25/11/2026 isso rendeu as 68 transicoes do dia (IFSP 24, IFMS 24, IFPB 20)
e 12 cards de «detectado pela primeira vez» do UNESP: 80 notificacoes para quatro concursos. A medida e o
mecanismo estao na SPEC-003 secao 1. Nenhum requisito de notificacao foi violado: o que esta errado e a
premissa de que aquela linha representa um concurso so.

`buscar_registro` em `src/database/manager.py` **ja** aplica a ordem de identidade com o `pci_id` na frente,
e o `pci_id` ja e descrito como chave canonica desde o schema v5. O furo e a cadeia de fallback nao parar
quando a chave canonica **discorda**: item com `pci_id` que nao casa cai no fallback por link especifico, por
`(area, nome)` COLLATE NOCASE e por casamento de entidade, e acaba casando com a linha do outro edital do
mesmo orgao. O `_resolver_nome_sem_colisao` modela dois casos, mesmo orgao e orgaos distintos que disputam o
nome; falta o terceiro, mesmo orgao com dois concursos.

Corrigir so o casamento troca spam por silencio: o segundo edital vira um `INSERT` que bate no
`UNIQUE(area, nome)`, cai no `except sqlite3.Error` de `atualizar_concurso` e devolve `0`. Por isso a
unicidade tem de abrir junto, e e isso que faz deste um ticket de mao unica.

## Critério de aceite
- [ ] Item com `pci_id` **nao** casa com linha cujo `pci_id` seja nao nulo e diferente, nos tres fallbacks:
      link especifico, `(area, nome)` e casamento de entidade (R-80)
- [ ] Item com `pci_id` **casa** com linha de `pci_id` nulo e grava o `pci_id` nela, mantendo a rechave da
      ADR-0001 (R-81)
- [ ] Item **sem** `pci_id` mantem a ordem de identidade de hoje, sem mudanca de comportamento (R-82)
- [ ] As quatro buscas de identidade tem desempate explicito pelo menor `id`: nenhuma delas depende de qual
      indice o planejador do SQLite escolheu
- [ ] O `pci_id` tem **um** criterio de nulidade (`NULL` ou vazio; qualquer outro valor e chave), o mesmo na
      busca, na escrita e no indice
- [ ] Dois editais do mesmo orgao e da mesma area coexistem como duas linhas, cada uma com o seu `pci_id`,
      `data_fim_inscricao` e `fase` (R-83)
- [ ] A migracao preserva `id`, `estado_usuario` e todos os campos de todas as linhas; a contagem de linhas
      antes e depois e a mesma; nenhuma linha e apagada e nenhuma e fundida (R-84)
- [ ] A migracao **nao** divide linha que ja colidiu (R-85)
- [ ] A migracao e idempotente: rodada duas vezes no mesmo banco, a segunda nao muda nada
- [ ] Colisao de identidade que o codigo nao consiga resolver entra no log como erro nomeado, nunca como
      silencio (R-86)
- [ ] O `_resolver_nome_sem_colisao` e **conservador**: o nome novo so vence quando nenhuma outra linha da
      area o ocupa (COLLATE NOCASE); havendo qualquer conflito, mantem o nome atual e loga (R-99)
- [ ] **Nenhum caminho** do `atualizar_concurso` funde linha ou apaga linha. O `_fundir` sai do arquivo, e a
      regra do `estado_usuario` que ele carregava (`seguindo` > `ignorado` > `ativo`, de qualquer das duas
      linhas) fica registrada na ADR-0005 como o que o T-028 tem de preservar quando reescrever a fusao
      (R-99)
- [ ] `docs/adr/0005-identidade-do-concurso.md` registra a decisao da unicidade, as duas opcoes da SPEC-003
      secao 4 item 1 e qual o dono escolheu, e **remete ao T-028** a tabela de decisao do nome (R-100)
- [ ] Suite inteira verde; nenhum teste existente afrouxado, renomeado ou apagado, com **uma** excecao
      nomeada: teste que afirma o `UNIQUE(area, nome)` de tabela muda de forma, porque trocar essa unicidade
      e o objeto deste ticket. Teste que afirma fusao de linha sai junto com o comportamento, e o relatorio
      lista cada um pelo nome

## Plano de testes
Costura: `DatabaseManager.buscar_registro` e `DatabaseManager.atualizar_concurso`, sobre banco temporario em
**arquivo** (nao `:memory:`, para a migracao ser exercitada de verdade). Pega: a ordem de identidade, o
desempate, o criterio de nulidade, o `INSERT` de dois editais do mesmo orgao, a migracao e a idempotencia
dela. Nao pega: a decisao de notificar, que e do `src/core/bot.py` e nao muda neste ticket.
Oráculo: literais escritos a mao a partir dos dados reais de 25/11 (os dois editais do IFSP, com `pci_id`
distintos e prazos distintos) e a tabela de requisitos da SPEC-003 secao 3.1.

Testes que nascem vermelhos:

- `test_pci_id_diferente_nao_casa_por_nome` — linha com `pci_id` gravado, item com outro `pci_id` e o mesmo
  `nome`: devolve `None`.
- `test_pci_id_diferente_nao_casa_por_link` — o mesmo caso, com o link especifico igual nos dois.
- `test_pci_id_diferente_nao_casa_por_entidade` — o mesmo caso, com o nome escrito de outra forma, daquelas
  que o `_buscar_por_entidade` casaria.
- `test_pci_id_casa_com_linha_sem_pci_id_e_rechaveia` — linha de `pci_id` nulo: casa, e a linha sai com o
  `pci_id` gravado.
- `test_item_sem_pci_id_mantem_a_ordem_de_hoje` — guarda de nao-regressao do Gran e das portas de HTML.
- `test_busca_empatada_escolhe_a_linha_mais_antiga` — nas quatro buscas, com empate plantado.
- `test_pci_id_vazio_conta_como_nulo_na_busca_e_na_escrita` — o criterio unico de nulidade.
- `test_dois_editais_do_mesmo_orgao_viram_duas_linhas` — dois `atualizar_concurso` com `pci_id` distintos e o
  mesmo nome: dois `id` distintos, os dois prazos preservados.
- `test_segunda_linha_nao_sobrescreve_o_prazo_da_primeira` — o caso exato do IFSP. **E o teste que mata o
  laco de renotificacao**, e o que prova o PED-07.
- `test_migracao_preserva_id_estado_usuario_e_contagem` — banco no schema anterior, com linhas, inclusive uma
  marcada `seguindo`.
- `test_migracao_rodada_duas_vezes_nao_muda_nada`
- `test_colisao_irresolvivel_vira_erro_no_log_nao_silencio`
- `test_nome_novo_vence_quando_ninguem_ocupa` — R-99, o unico caminho em que o nome muda.
- `test_nome_em_conflito_mantem_o_nome_atual_e_loga` — R-99, com o conflito sendo do mesmo orgao numa
  execucao e de outro orgao na outra: **o resultado e o mesmo nas duas**, e e isso que o teste afirma.
- `test_nenhum_caminho_funde_ou_apaga_linha` — bateria de cenarios, afirmando a contagem de linhas antes e
  depois e que todos os `id` continuam no banco.
- `test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5` — **a regressao do quarto defeito, pelo cenario
  exato do parecer**: `id=1` IFSP - SP, chave `296538`, link `/a`; `id=2` TJPR, chave `296044`, link `/b`;
  `atualizar_concurso` com nome TJPR, link `/a` e sem `pci_id`. Afirma que `id=1` continua IFSP - SP e que
  `buscar_registro("TJPR")` devolve `id=2`, nao `id=1`.

## Fora do escopo
- Reparar as linhas que **ja** colidiram. E outro ticket (T-023), que depende deste.
- Mexer na matriz de decisao ou na elegibilidade. Foram conferidas e estao corretas.
- Dividir linha colidida durante a migracao: o R-85 proibe, porque separar exige julgamento sobre qual dado
  pertence a qual edital.
- Ampliar a lista fechada de esfera, ou qualquer outra mudanca no `_buscar_por_entidade` alem de passar a
  respeitar o `pci_id`.
- **A regra de nome e de fusao.** Saiu deste ticket em 26/11/2026, por decisao do dono (SPEC-003 secao 4
  item 6), e virou o **T-028**, com requisito proprio (R-100) e a tabela de decisao como primeira entrega.
  Aqui vale o R-99, que e conservador de proposito. Nao reintroduza fusao, nem «so para o caso obvio».
- Concorrencia, WAL, `BEGIN IMMEDIATE`: viraram o T-027 (R-98), com medida registrada.

## Notas do arquiteto

**Por que G−:** decide a identidade do concurso, que e o contrato que todo o resto do sistema consome, e
carrega migracao de schema sobre 1.700 linhas de producao onde vivem as estrelas do Lucas. Errar para um lado
funde concursos distintos, que e o defeito de hoje; para o outro divide um concurso em duas linhas e
renotifica. Nao e volume de codigo, e densidade de consequencia.

**Porta de mao unica, e e por isso que o integrador espera o OK do dono.** A migracao altera a unicidade da
tabela `editais`. A SPEC-003 secao 4 item 1 poe as duas opcoes e recomenda o indice unico por expressao
`(area, nome, COALESCE(pci_id, ''))`, que exige recriar a tabela uma vez e colide com a regra «migracao e
aditiva, nunca recriar tabela com dado dentro» do `kanban/REGRAS.md`. Essa regra e do dono. **Nao escolha
sozinho:** se o OK dele no ticket nao disser qual caminho, pare e pergunte em vez de adivinhar.

O `COALESCE` nao e enfeite: em SQLite `NULL` nao colide com `NULL` numa chave unica, entao um
`UNIQUE(area, nome, pci_id)` cru deixaria passar duas linhas do Gran com o mesmo nome, que e exatamente a
duplicata que o `_resolver_nome_sem_colisao` foi escrito para matar depois da varredura de 08/08/2026. O
SQLite de producao e 3.45.1, e indice por expressao existe desde a 3.9.

Se o caminho escolhido for recriar a tabela, siga o procedimento documentado do SQLite (criar a nova, copiar,
trocar os nomes), dentro de uma transacao, e use o `_migrate_to_v3` do proprio arquivo como molde: ele ja faz
isso. O backup do arquivo do banco e passo de producao, nao deste ticket.

**Nao reescreva o `_buscar_por_entidade`.** Ele existe para o mesmo orgao escrito de formas diferentes entre
o Gran e o PCI, e continua necessario. O que muda e so que um `pci_id` discordante passa a bloquea-lo.

**Decisão do arquiteto (2026-11-25 15:21):** Decisao do dono, 25/11/2026, no chat: «Recria a tabela». O caminho e o indice unico por expressao (area, nome, COALESCE(pci_id, '')), substituindo o UNIQUE(area, nome) de tabela, pelo procedimento documentado do SQLite: criar a nova, copiar, trocar os nomes, dentro de uma transacao. O _migrate_to_v3 do proprio arquivo e o molde. A excecao a regra «nunca recriar tabela com dado dentro» foi aberta por escrito no kanban/REGRAS.md, com escopo: vale para a unicidade da tabela editais, neste ticket, e nada mais. O que esta decidido e o CAMINHO. O gate de integracao (a linha «OK do Lucas:») segue em aberto de proposito: migracao de schema sobre 1.700 linhas de producao e porta de mao unica, e o dono olha o diff antes de ela entrar.

**Decisão do arquiteto (2026-11-25 17:16):** Veredito do revisor (Codex, G- high): BLOQUEADO, e com razao nos tres achados. Decisao do arquiteto, 25/11/2026.

ACHADO 1, a regressao do R-82: CONFIRMADA, e a causa raiz e mais funda do que o parecer diz. O parecer diz que `_resolver_nome_sem_colisao` escolhe o candidato de menor id. E verdade, mas o defeito real e que ela resolve UM conflito quando pode haver VARIOS. O `fetchall` passou a trazer a lista inteira e o `next(...)` continua levando um so; qualquer duplicata do mesmo orgao que sobrar ainda ocupa o nome, o UPDATE seguinte bate na unicidade, da rollback e devolve 0.
O `ORDER BY id` que a entrega acrescentou e o que trocou o resultado na pratica. Sem ele, o plano do SQLite varria o indice `(area, nome)` em ordem BINARY, e maiuscula vem antes de minuscula em ASCII: com `IFSP`, `IFSP - SP` e `ifsp` no banco, o primeiro candidato era o de nome exato, que fundia e nao deixava colisao para tras. Com `ORDER BY id`, vem o de menor id, que pode ser a variante de caixa, e o de nome exato fica no banco.
Isso nao e cenario de laboratorio: sao exatamente as linhas legadas que o T-023 existe para reparar, e elas vao estar no banco na primeira varredura depois da migracao.
Conserto pedido: funda TODOS os conflitos que sao o mesmo orgao e nao sao outro edital (`pci_id` nao nulo e diferente), em vez do primeiro. Se sobrar conflito que nao e o mesmo orgao, mantenha o nome atual, como hoje. Teste pela interface publica com as tres linhas (`IFSP`, `IFSP - SP`, `ifsp`), atualizando pelo link especifico da primeira, e afirme: retorno igual ao id da linha casada, status novo gravado, uma linha so no fim.

ACHADO 2, string vazia contra nulo (R-80/R-81): CONFIRMADO. A busca trata `""` como ausente (linhas 358 e 392) e a escrita persiste `""` (linha 544). Normalize na escrita, com `pci_id` vazio entrando como NULL, e use na resolucao de conflito o mesmo critario de nulidade da SPEC-003 linha 134. O bot ja normaliza na entrada, entao isto protege linha legada e chamada direta da API, nao o fluxo de hoje.

ACHADO 3, lacuna de rechave: CONFIRMADO por mutacao sobrevivente, que e a prova que vale. Acrescente os dois testes que o parecer pede: rechave pelo link com nomes de entidade distintos, e rechave por entidade com nomes diferentes e sem link especifico. Nos dois, afirme pela interface publica o id original e o `pci_id` novo.

Mais tres, menores, do mesmo parecer:
- O teste da linha 918 escreve pelo SQLite e observa a excecao dessa API, fora da costura declarada do ticket. Mova para a interface publica.
- A docstring de `_ensure_schema` (linha 114) ainda diz que toda migracao e aditiva. Corrija, citando a excecao da `kanban/REGRAS.md`.
- `CLAUDE.md` linhas 150 e 156 ainda descrevem v6 com `UNIQUE(area, nome)`. Passa a fazer parte do `toca` deste ticket: a verdade do schema anda junto com a mudanca do schema.

O que a entrega acertou e fica registrado: preservar a sequencia de ids na migracao, que ninguem pediu por escrito, evita que um id reciclado faca um botao antigo do Telegram apontar para outro concurso. E seguir a SPEC-003 contra o criterio do ticket no `test_area_nome_is_unique` foi a hierarquia certa, declarada em vez de escondida.
O que o parecer acertou: achou a regressao por experimento diferencial em copias do banco, nao por leitura, e achou a lacuna de rechave por mutacao. Verde nenhum pegaria os dois.

ACHADO 4, o alerta do dia do R-86: e decisao de escopo, do dono, nao do arquiteto. Perguntei ao Lucas. Nao toque em `src/core/bot.py` ate a resposta entrar aqui como segunda nota.

O gate de integracao (a linha «OK do Lucas:») segue em aberto, como desde o inicio.

**Decisão do arquiteto (2026-11-25 18:31):** ACHADO 4 decidido, 25/11/2026: o dono respondeu «Ticket separado». O alerta do dia saiu deste ticket e virou o T-026, com o requisito partido em R-86 (log, aqui) e R-97 (alerta, la), registrado na SPEC-003 secao 4 item 5. Portanto: NAO toque em src/core/bot.py nesta rodada. O log nomeado que voce ja entregou e exatamente o escopo do R-86 e esta aceito. A segunda rodada e so os tres achados confirmados da nota anterior, mais os tres itens menores. O parecer completo do revisor esta em kanban/relatorios/T-020-revisor-1.md, no repo: leia antes de comecar, ele tem os numeros das linhas e os cenarios exatos que ele reproduziu. O CLAUDE.md entrou no toca deste ticket.

**Decisão do arquiteto (2026-11-26 13:09):** Terceira rodada. Decisao do arquiteto, 26/11/2026, sobre o REPROVADO do revisor (Codex, G- high). Os dois achados sao reais e confirmei os dois. Mas um deles NAO deve ser implementado como esta escrito, e e por isso que esta nota existe.

ACHADO 1, a escrita no edital errado: CONFIRMADO, e e o grave. A causa raiz nao e a migracao: e que as buscas de fallback sem chave NAO TEM DESEMPATE. Elas pegam a primeira linha que o indice devolver, e qual e a primeira depende de qual indice o SQLite escolhe. Antes, o plano usava o `sqlite_autoindex_editais_1` do `UNIQUE(area, nome)`, em ordem BINARY, onde maiuscula vem antes de minuscula. Depois da migracao o plano usa o `idx_editais_pci`, e a primeira linha muda. Com `(1, "ifsp", pci 100)` e `(2, "IFSP", pci 900)` no mesmo link, a mesma atualizacao sem `pci_id` acertava o id 2 e passou a acertar o id 1. Isso e **mover historia de um edital para outro em silencio**, que e exatamente o que este ticket existe para impedir.
Restricao do conserto, e aqui esta a parte que o parecer nao diz: o desempate tem de ser deterministico **e** igual ao resultado de antes da migracao para as linhas que existem hoje. So `ORDER BY id` e deterministico e esta ERRADO, porque muda a resposta e reatribui dado entre dois editais. Reproduza a ordem antiga de proposito, e escreva no codigo por que ela e essa, senao a proxima pessoa a "limpa". O teste tem de ter os ids em ordem oposta a dos nomes, em banco v6 migrado, afirmando pelos tres fallbacks qual id foi escolhido, o status novo num e o status original no outro.

ACHADO 2, o `pci_id` de um espaco: CONFIRMADO, mas **o espaco nao e o defeito**. O defeito e que ha DOIS critarios de nulidade em duas camadas: no Python, `" "` conta como ausente, entao a fusao e autorizada e a chave da outra linha e descartada; no SQL, `NULLIF(pci_id, '')` conta como presente, entao a chave valida nao e herdada. Qualquer valor em que as duas camadas discordem destroi uma chave canonica valida. O espaco e so a testemunha.
Portanto: **nao acrescente caso especial para espaco em branco.** Unifique o critario de nulidade num lugar so e use o mesmo na escrita, na busca, na fusao e no indice. Se o critario passar a ser "vazio depois de tirar espaco", o indice tambem precisa ver isso.
E nao discuta se um espaco chega do scraper. Nao importa: o conserto e barato e a consequencia de ele acontecer e perder o `pci_id`, que e a pior coisa que este modulo pode fazer.

PLUMBING, e isso te afeta: a base deste worktree e anterior ao commit da spec. A copia da SPEC-003 que esta aqui dentro ainda tem a redacao ANTIGA do R-86, pedindo log e alerta do dia. A redacao normativa esta na `main`. Vou relancar com `--atualizar-base`, entao voce vai receber o T-021 e o T-025 na base e a spec correta. **Nao reintroduza o alerta do dia**: ele e o R-97, no T-026, por decisao do dono.

Do parecer, duas coisas ficam registradas como acerto. O revisor achou os dois defeitos por experimento diferencial em bancos temporarios, nao por leitura: e a segunda vez na mesma rodada que isso acontece, e nenhum teste verde pegaria. E ele foi conferir a spec normativa na `main` em vez de confiar na copia do worktree, que estava velha.

Aviso de processo, para voce saber onde pisa: esta foi a PRIMEIRA reprovacao. Uma segunda bloqueia o ticket, e ai eu o quebro ou subo o nivel. Se chegar nisso, o corte ja esta pensado e nao e pelo meio: a migracao em si esta provada (R-84, R-85, idempotencia, preserva id e `sqlite_sequence`, arquivo igual na segunda abertura), e todos os defeitos das duas rodadas vivem na logica de identidade conversando com linha legada. O corte seria migracao e schema de um lado, determinismo dos fallbacks legados do outro.

O gate de integracao (a linha «OK do Lucas:») segue em aberto.

**Decisão do arquiteto (2026-11-26 13:11):** Plumbing, correcao de detalhe da nota anterior: o --atualizar-base so vale para o revisor, entao trouxe a main para esta branch por merge, a mao, em 26/11/2026. O merge foi limpo, sem conflito, inclusive no CLAUDE.md que o T-021 tambem havia tocado, e rodei a suite depois para descartar conflito semantico: 603 passed. Portanto a base desta rodada NAO e mais o d5fdae7: e o merge, com 603 testes, que ja inclui o T-021, o T-025 e a spec normativa. Medir contra 582 ou 569 agora da numero errado.

**Decisão do arquiteto (2026-11-26 13:21):** Quarta rodada. Decisao do arquiteto, 26/11/2026. Voce parou pelo motivo certo, e o furo era da minha nota: ela mandava "preservar o comportamento de antes" sem eu ter medido de qual banco eu estava falando. Fui medir a producao, so leitura, pelo SSH. Segue o que o banco de verdade diz, com numero, para esta rodada nao precisar de mais nenhuma pergunta.

MEDIDO EM PRODUCAO, 26/11/2026, 1.725 linhas:
- `idx_editais_pci` EXISTE. Sua hipotese estava certa, e a minha instrucao, implementada ao pe da letra, teria MUDADO a linha escolhida em producao. Foi bom voce ter parado.
- Empates de nome (`area` + `nome` sem caixa): **zero grupos**. E garantido pelo proprio `UNIQUE(area, nome)` do v6, que nao deixa dois nomes iguais na mesma area. O cenario `IFSP`/`ifsp`/`IFSP - SP` que o revisor montou **nao existe em producao**: e forma sintetica de banco legado.
- Empates de link: **2 grupos**, de 2 e 5 linhas, e os dois sao a pagina-indice do Gran (`blog.grancursosonline.com.br/concursos-ti/` e `/concursos-educacao/`). O `_link_e_especifico` recusa exatamente esses quando o `url_indice` e passado, entao eles nao chegam a empatar na busca por link.
- `pci_id` vazio: 0. So espaco: 0. Nao numerico: 0. 158 sao NULL, que e o esperado (Gran e portas de HTML). Ou seja: o conserto do critario de nulidade que voce acabou de fazer esta certo e continua, mas a urgencia dele em producao e zero. Isso e bom saber, nao motivo para desfazer.
- `pci_id` repetido: 429 grupos, 926 linhas. **Todos os 429 cruzam area, e dentro de uma area mesma nao ha nenhum.** E o esperado: um concurso que abre vaga de TI e de educacao aparece nas duas areas, uma linha em cada. Como toda busca filtra `WHERE area = ?`, isso nao produz empate nenhum. O achado que voce levantou de brinde e verdadeiro e inofensivo hoje, e e por isso que ele vale um desempate de barato, nao um conserto de urgencia.

CONCLUSAO QUE ISSO FORCA: hoje, em producao, **nenhuma busca sem chave tem empate**. Logo a regra de desempate nao muda nenhuma linha existente. Ela e garantia para o futuro, nao compatibilidade de migracao. Isso derruba a minha propria objecao da nota anterior.

DECISAO, e ela REVOGA o que a nota 3 dizia sobre o `ORDER BY id`:
1. Ponha o desempate EXPLICITO no SQL de todas as buscas sem chave, e tambem na busca pelo `pci_id`. O criterio e `ORDER BY id` ASC: a linha mais antiga ganha. Razao a escrever no codigo: linha mais antiga e a de historia mais longa, e portanto a que provavelmente carrega a estrela do Lucas; e um resultado explicito nunca depende de qual indice o planejador escolheu, que foi a causa raiz da regressao do revisor.
2. Eu proibi `ORDER BY id` na nota anterior porque, no banco sintetico do revisor, ele mudava a resposta. Com empate zero em producao, essa objecao caiu. Nao e volta atras por conveniencia: e a medida substituindo a suposicao.
3. O teste que a nota 3 pedia muda de expectativa: ele passa a afirmar a regra explicita, e nao a ordem antiga do indice. Deixe no proprio teste um comentario dizendo que a forma do banco de producao nao tem empate e que a regra e deterministica por escolha, senao a proxima pessoa le o teste como se ele descrevesse producao.
4. Inclua a busca pelo `pci_id` no mesmo desempate. Isso entra no escopo de proposito: e a mesma familia de consulta, no mesmo arquivo, e fecha a lacuna que voce apontou com uma clausula.

Nao e preciso mais nada do notebook. Nao me pergunte de novo sobre a forma do banco: o que esta acima e a medida, nao a estimativa.

O gate de integracao (a linha «OK do Lucas:») segue em aberto.

**Decisão do arquiteto (2026-11-26 13:41):** Quinta rodada. Decisao do arquiteto sobre a SEGUNDA reprovacao, 26/11/2026. Pelas regras eu podia quebrar o ticket ou subir o nivel. Fiz nenhum dos dois, e explico por que, porque isso tambem e informacao para quem ler o historico depois.

O revisor trouxe dois achados. Eles parecem o mesmo tipo de coisa e NAO SAO. Separei por medida.

ACHADO 1, a janela entre a decisao e a escrita: REAL em laboratorio, INALCANCAVEL aqui. Ele reproduziu com duas conexoes e sincronizacao determinista, o que exige dois escritores. Fui medir: nao ha thread, async nem multiprocessing em `src/` nem no `main.py`; o `flock -n` do `run_daily.sh` impede duas varreduras ao mesmo tempo; o notebook nao tem servico residente (nenhum `systemd`, nenhum processo do monitor entre varreduras); e os callbacks do Telegram, que tambem escrevem, rodam DENTRO da varredura, chamados pelo `_processar_callbacks_telegram`. Um escritor so, por construcao. **Saiu deste ticket e virou o T-027**, com o requisito R-98 na SPEC-003 e a medida registrada com data. Nao e requisito abandonado: e requisito de garantia, com as tres mudancas que o tornam vivo nomeadas no ticket.

ACHADO 2, a colisao no estado intermediario da fusao: REAL, ALCANCAVEL COM UM ESCRITOR SO, e **e defeito que este ticket cria**. Repare na frase do proprio parecer: «sem outro escritor». Com `(1, "IFSP - SP", NULL)`, `(2, "IFSP - SP", "296538")` e `(3, "IFSP", "296538")`, a linha 1 herda a chave da 3 enquanto ainda se chama "IFSP - SP", e nesse instante a chave dela fica igual a da linha 2. Colide, da rollback, devolve 0 e a atualizacao valida e perdida.
Medi tambem por que isso nao acontece hoje: producao tem **zero empates de nome**, porque o `UNIQUE(area, nome)` do v6 nao deixa. Mas a sua propria mudanca abre essa forma de proposito, e e disso que se trata: trocar a unicidade cria estados novos alcancaveis, e um deles e este. O defeito nasce com o ticket, entao morre com o ticket.
Conserto pedido: a fusao e a gravacao do nome e da chave finais na mesma transacao, numa ordem que nunca passe por um estado intermediario conflitante. Nao aplique a chave nova com o nome antigo. O teste e o cenario das tres linhas pelo link especifico, afirmando retorno 1, status novo, a chave final, o `estado_usuario` «seguindo» herdado da linha 3, e a linha 2 intacta.

ESCOPO DESTA RODADA: so o ACHADO 2. Nao toque em concorrencia, nao ligue WAL, nao mexa na ordem de identidade nem no desempate, que estao provados.

POR QUE NAO SUBI O NIVEL NEM QUEBREI: as quatro rodadas nao foram o implementador errando o alvo. Cada rodada consertou o que foi pedido, e o revisor achou uma camada mais funda. A superficie encolheu a cada volta: migracao provada, ordem de identidade provada, desempate provado, e agora sobra UMA ordenacao dentro da fusao. Isso e convergencia, nao patinacao. Subir para G+ por uma ordem de operacoes seria exagero, e quebrar criaria dois tickets com revisao dobrada para um conserto de uma funcao.
O que eu reconheco como meu erro, e vai para a retro da fase: a spec nao enumerou os estados NOVOS que abrir a unicidade passa a permitir. Se tivesse, o ACHADO 2 estaria no plano de testes da primeira rodada. Mudanca de unicidade cria estados alcancaveis novos, e o ticket tem de listar quais.

O gate de integracao (a linha «OK do Lucas:») segue em aberto.

**Decisão do arquiteto (2026-11-26 14:07):** TERCEIRA REPROVACAO. Analise do arquiteto, 26/11/2026. Nao e para a proxima rodada: e o diagnostico do ticket, e a decisao de escopo esta com o dono.

OS QUATRO DEFEITOS, EM ORDEM, E O QUE ELES TEM EM COMUM:
1. (rodada 1) Fundia um conflito quando havia varios; o que sobrava ocupava o nome e a gravacao era perdida.
2. (rodadas 2 a 4) A linha escolhida nas buscas sem chave dependia de qual indice o planejador usava, e a migracao trocou o indice.
3. (rodada 5) A linha herdava a chave com o nome antigo e colidia num estado intermediario.
4. (agora) Um `continue` na discordancia de chave acontece ANTES da checagem de mesmo orgao. Quando o unico conflito e de outro orgao com outra chave, a funcao aceita o nome disputado: o IFSP passa a se chamar TJPR, e a busca sem chave por TJPR devolve a linha do IFSP.

Os quatro vivem na MESMA familia: `_resolver_nome_sem_colisao`, `_fundir` e as buscas de fallback. A funcao decide tres coisas ao mesmo tempo (qual nome fica, se funde, se herda a chave) por uma SEQUENCIA DE GUARDAS, e a ordem dessas guardas esteve errada de um jeito diferente em cada rodada. O conserto obvio deste quarto defeito e mover a checagem de orgao para antes do `continue`: uma linha. Seria a QUINTA emenda na mesma sequencia, e e por isso que eu nao vou pedi-la.

JUSTICA COM AS DECISOES ANTERIORES, porque isso importa para quem ler depois: a tabela do proprio parecer mostra que a regressao do nome entrou em `47291be`, na primeira rodada, e atravessou as rodadas 2 a 5 sem ser vista. O desempate pelo menor id, que EU aprovei em 26/11, nao causou o defeito: ele tornou o efeito deterministico e portanto visivel. Sem ele, este defeito continuaria no banco mudando de comportamento com o humor do planejador.

O DIAGNOSTICO: o problema nao e nenhuma das quatro guardas. E que a regra nunca foi escrita como regra. Nao existe, nem na spec nem na ADR, a enumeracao dos estados que a troca de unicidade passa a permitir, com o que acontece em cada um. Sem essa tabela, cada rodada conserta o caso que o revisor trouxe e o proximo caso nao conservado continua la. Isso e o mesmo erro meu que eu ja havia anotado para a retro na nota da quinta rodada, e agora ele cobrou juros.

PROPOSTA AO DONO, recomendada:
(a) O T-020 fica com o que sobreviveu a TODAS as revisoes: a migracao (R-84, R-85, idempotencia, `id` e `sqlite_sequence` preservados, arquivo igual na segunda abertura), a ordem de identidade, o desempate explicito e o critario unico de nulidade. Nenhuma revisao contestou nada disso em cinco rodadas.
(b) O `_resolver_nome_sem_colisao` e o `_fundir` VOLTAM ao comportamento da `main`, que e conservador: mantem o nome atual na duvida e nao escreve nome de outro orgao em linha nenhuma.
(c) A logica de nome e fusao vira ticket proprio, G-, cuja PRIMEIRA entrega e a tabela de decisao enumerada na ADR (para cada combinacao de: o candidato tem chave, as chaves concordam, e o mesmo orgao, o item e sem chave), e so depois o codigo, com um teste por linha da tabela.

POR QUE (b) E SEGURO, e isto e o ponto tecnico que sustenta a proposta: o motivo pelo qual o revisor exigiu "funda todos os conflitos" na rodada 2 era que a duplicata deixada para tras ocupava o nome e fazia o `UPDATE` colidir sob o `UNIQUE(area, nome)`. Com o indice novo por expressao, duas linhas de mesmo nome e chaves diferentes COEXISTEM legalmente. Ou seja: a razao da exigencia deixou de existir junto com a unicidade antiga. Voltar ao conservador nao perde nada que funcione hoje, e o que ele deixa de fazer (fundir duplicata legada) e justamente o trabalho do T-023, que existe para isso e pede julgamento humano.

O ALTERNATIVO, que eu nao recomendo: uma sexta rodada movendo a guarda. Barato numa linha, e aposta de que o quinto caso nao existe, depois de quatro apostas perdidas.

Decisao pendente com o Lucas. Nao lance nada neste ticket ate ela entrar aqui.

**Decisão do arquiteto (2026-11-26 14:57):** DECISAO DO DONO, 26/11/2026: reduzir o ticket ao que esta provado. O dono respondeu «pode fazer o que recomendou» no chat. Registro na SPEC-003 secao 4 item 6. ESTA E A RODADA 6, e ela e de ESCOPO NOVO, nao a sexta tentativa do mesmo alvo.

O QUE FICA, e nenhuma das cinco revisoes contestou: a migracao (R-84, R-85, idempotencia, id e sqlite_sequence preservados), a ordem de identidade (R-80, R-81, R-82), o desempate explicito pelo menor id nas quatro buscas, o criterio unico de nulidade do pci_id e o log nomeado da colisao (R-86).

O QUE SAI: a regra de nome e de fusao. O _resolver_nome_sem_colisao passa a cumprir o R-99, conservador: o nome novo so vence quando NENHUMA outra linha da area o ocupa (COLLATE NOCASE); havendo qualquer conflito, mantem o nome atual e loga. O _fundir sai do arquivo e nenhum caminho funde nem apaga linha. A regra vira o T-028, cuja primeira entrega e a tabela de decisao do R-100, e nao codigo.

POR QUE O CONSERVADOR E SEGURO, e isto foi medido hoje no log de producao, nao suposto: o caminho conservador (manter o nome atual) disparou 109 vezes na historia do bot, a ultima em 18/11/2026. A fusao disparou 7 vezes em toda a historia, a ultima em 15/09/2026, e nenhuma depois. O que o R-99 deixa de fazer e limpeza de duplicata legada que nao acontece ha dois meses e meio. E o motivo pelo qual o revisor exigiu «funda todos os conflitos» na rodada 2 morreu junto com a unicidade antiga: era o UPDATE colidir sob o UNIQUE(area, nome), e com o indice novo por expressao duas linhas de mesmo nome e chaves diferentes coexistem legalmente.

E MAIS: a medida de hoje mostra que o estrago vivo em producao NAO vem da regra de nome. Vem do casamento, que e o que fica no ticket. A linha id=1284 (area TI, link igual a pagina-indice do Gran, pci_id nulo) passou por TRES nomes de municipios diferentes: Francisco Macedo (PI), Serra Grande (PB) e Luiz Alves (SC). Quatro linhas do banco carregam a pagina-indice como link (1038, 1265, 1284, 1404), e a busca por link usa fetchone sem ordem. Quem conserta isso e o R-80 mais o desempate, os dois deste ticket. A parte que estou cortando nunca causou o dano de producao: ela foi escrita em agosto para um problema que a unicidade nova resolve de outro jeito.

O QUE FAZER NESTA RODADA, concretamente: reduzir a branch que ja existe (18 commits), nao comecar de novo. Apagar o _fundir e a logica de decisao de nome, deixar o _resolver_nome_sem_colisao com um caminho de mudanca de nome e um de preservacao, e apagar os testes que afirmam fusao, LISTANDO CADA UM PELO NOME no relatorio. Antes de apagar o _fundir, mover para a ADR-0005 a regra do estado_usuario que ele carregava (seguindo > ignorado > ativo, de qualquer das duas linhas), como o que o T-028 tem de preservar: essa regra protege a estrela que o Lucas marca a mao, e nao pode viver so no historico do git.

E OBRIGATORIO entregar o teste test_nome_nao_vira_de_outro_orgao_o_caso_do_parecer_5, com o cenario exato do parecer 5 (id=1 IFSP - SP chave 296538 link /a; id=2 TJPR chave 296044 link /b; atualizar com nome TJPR, link /a e sem pci_id), afirmando que id=1 continua IFSP - SP e que buscar_registro de TJPR devolve id=2. Ele e a prova de que o corte fecha o quarto defeito, e nao so o esconde.

O gate de integracao (a linha «OK do Lucas:») segue em aberto, de proposito: migracao de schema sobre 1.758 linhas de producao e porta de mao unica.

## Histórico
- 2026-11-25 16:48 backlog → pronto · liberado: Lucas liberou no chat em 25/11/2026
- 2026-11-25 16:49 pronto → fazendo · implementador · opus G- high
- 2026-11-25 17:05 fazendo → entregue · implementador: ENTREGUE · relatório T-020-implementador-1.md · 17 min
- 2026-11-25 17:05 entregue → revisando · revisor · codex G- high
- 2026-11-25 17:15 revisando → bloqueado · revisor: BLOQUEADO · relatório T-020-revisor-1.md · 11 min
- 2026-11-25 18:31 bloqueado → pronto · manual: arquiteto julgou o BLOQUEADO: tres achados confirmados viram 2a rodada; o alerta do R-86 saiu para o T-026 por decisao do dono
- 2026-11-26 12:47 pronto → fazendo · implementador · opus G- high
- 2026-11-26 12:59 fazendo → entregue · implementador: ENTREGUE · relatório T-020-implementador-2.md · 13 min
- 2026-11-26 13:00 entregue → revisando · revisor · codex G- high
- 2026-11-26 13:09 revisando → pronto · revisor: REPROVADO · relatório T-020-revisor-2.md · 9 min
- 2026-11-26 13:11 pronto → fazendo · implementador · opus G- high
- 2026-11-26 13:20 fazendo → bloqueado · implementador: BLOQUEADO · relatório T-020-implementador-3.md · 10 min
- 2026-11-26 13:21 bloqueado → pronto · manual: arquiteto mediu a producao e decidiu o desempate; a duvida que bloqueou foi respondida com numero
- 2026-11-26 13:21 pronto → fazendo · implementador · opus G- high
- 2026-11-26 13:29 fazendo → entregue · implementador: ENTREGUE · relatório T-020-implementador-4.md · 8 min
- 2026-11-26 13:29 entregue → revisando · revisor · codex G- high
- 2026-11-26 13:40 revisando → bloqueado · revisor: REPROVADO · relatório T-020-revisor-3.md · 11 min
- 2026-11-26 13:41 bloqueado → pronto · manual: arquiteto separou os dois achados por medida: o de concorrencia virou T-027; sobra a ordem da fusao, que este ticket cria
- 2026-11-26 13:41 pronto → fazendo · implementador · opus G- high
- 2026-11-26 13:53 fazendo → entregue · implementador: ENTREGUE · relatório T-020-implementador-5.md · 13 min
- 2026-11-26 13:56 entregue → revisando · revisor · codex G- high
- 2026-11-26 14:06 revisando → bloqueado · revisor: REPROVADO · relatório T-020-revisor-4.md · 11 min
- 2026-11-26 14:57 bloqueado → pronto · manual: escopo reduzido por decisao do dono em 26/11/2026: a regra de nome e fusao saiu para o T-028 (R-100) e o R-99 conservador entra no lugar
