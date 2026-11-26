# SPEC-003 — Identidade do concurso, e cota da LLM que retry nao conserta

> **Estado:** proposta ao dono — 25/11/2026
> **Decisao que a sustenta:** `docs/adr/0005-identidade-do-concurso.md`, que nasce nesta fase.
> **Itens do pedido que atende:** PED-07
> **Depende da SPEC-001:** o `pci_id` e a porta do MCP nascem la. Esta spec decide o que fazer quando
> **dois editais distintos do mesmo orgao** chegam pela mesma porta, caso que a SPEC-001 nao previu.
> Os termos sao os do `GLOSSARIO.md`.

## Pedido original

Pedido do Lucas no chat, em 25/11/2026:

- **PED-07** — "os requisitos, originalmente, diziam para enviar so os concursos novos ou novidades, eu
  estou recebendo um monte repetidos nesses ultimos dias": o bot volta a notificar so o que e novo ou
  novidade de verdade.

No mesmo pedido ele mandou conferir todos os requisitos desde o comeco do projeto. A conferencia foi feita
antes desta spec, e o resultado dela esta na secao 1.1: **nenhum requisito de notificacao foi violado.** E
por isso que esta spec trata de identidade e de cota, e nao da matriz de decisao, que esta correta.

## 1. O problema, medido em producao

Em 25/11/2026 o bot rodou **13 varreduras completas** e enviou **113 notificacoes**, contra uma varredura e
um punhado de cards num dia normal. O log do dia foi de 50 KB para 2,9 MB.

As repeticoes se concentram em quatro concursos:

| Concurso | Cards no dia | Evento |
| :-- | :-: | :-- |
| IFSP | 24 | `[TRANSICAO]`, duas por varredura |
| IFMS | 24 | `[TRANSICAO]`, duas por varredura |
| IFPB | 20 | `[TRANSICAO]`, duas por varredura |
| UNESP | 12 | `[NOVO]`, uma por varredura, sempre "detectado pela primeira vez" |

Foram **68 transicoes no dia, e 24 + 24 + 20 = 68**: nenhum outro concurso transicionou nas 13 varreduras, e
os 692 itens filtrados passaram calados. **Quem tem identidade correta ficou em silencio perfeito**, nas treze
voltas. Essa e a medida que separa o defeito do requisito.

A linha do log nomeia o mecanismo:

```text
🔔 [TRANSICAO] IFSP - Instituto Federal ... - SP: Inscrições abertas → Inscrições abertas (data_mudou=True).
```

A fase nao mudou. O que muda e o **prazo**, porque dois editais distintos do mesmo orgao ocupam uma linha so e
cada varredura sobrescreve o prazo do outro. Ida e volta, duas vezes por varredura, para sempre.

### 1.1. A conferencia dos requisitos, desde o comeco

Quatro camadas falam sobre quando notificar, e elas concordam entre si:

- a **matriz de decisao do README** (`_decidir_e_notificar`), o documento original: inedito manda card novo,
  fase que avancou manda atualizacao, prazo de inscricao que mudou manda atualizacao, LLM que so reescreveu
  ou regrediu a fase atualiza em silencio;
- o **`CLAUDE.md`**: so avanco de fase ou mudanca de `data_fim_inscricao` notifica;
- a **SPEC-001**, R-11 a R-13: item filtrado salva calado, filtrado que passa a entrar sai como novo porque o
  Lucas nunca o viu, e quem entrava e passa a filtrado nao renotifica;
- a **ADR-0002**: o silencio por teto, na area TI.

O codigo cumpre isso. `src/core/bot.py` nega a notificacao quando nao houve avanco de fase nem mudanca de
data, e manda o card quando houve. **A regra "prazo mudou, avisa" e requisito escrito, e e ela que esta
disparando.** O que esta errado nao e a regra: e a premissa de que aquela linha representa um concurso so.

### 1.2. A cadeia de causa das 13 varreduras

Cada elo foi conferido na fonte primaria:

1. a cota semanal da LLM esgotou as 00:20:11 de 25/11 (`Weekly/Monthly Limit Exhausted`, 4.643 vezes no log do
   dia, zero em qualquer dia anterior);
2. sem LLM, a extracao perde 75 de 187 blocos (40%), acima do `LIMITE_ERRO_EXTRACAO` de 20%;
3. a area entra em `falhou`, e o `main.py` sai com 1;
4. o `scripts/run_daily.sh` so grava `logs/.last_success_date` quando o exit e 0;
5. sem o marcador do dia, o tick horario do cron roda a **varredura inteira** a cada hora, que e o catch-up
   previsto em projeto, escrito para recuperar os nove dias sem varredura de 01/07 a 08/08/2026;
6. cada varredura repassa a matriz de decisao em todas as linhas, e as linhas de identidade colidida oscilam.

O catch-up horario nao e defeito, e requisito: *"perda de >= 20% dos blocos dispara alerta e retorna exit code
1, para retry horario"*. O que ninguem previu foi **retry que renotifica**. Ele foi escrito para falha
passageira, nao para parede de cota com hora de reset conhecida, que nao muda de resposta antes daquela hora.

### 1.3. O que o codigo ja faz certo, e que esta spec aproveita

Nao ha nada a inventar aqui: os dois padroes necessarios ja existem no repo, so nao alcancam estes casos.

- **`buscar_registro` ja tem ordem de identidade** com o `pci_id` na frente, e o `pci_id` ja e descrito como
  "chave canonica" desde a v5. O furo e a cadeia de fallback **nao parar** quando a chave canonica discorda:
  item com `pci_id` que nao casa cai no fallback por link, por `(area, nome)` e por entidade, e acaba casando
  com a linha de outro edital do mesmo orgao.
- **`_resolver_nome_sem_colisao` ja trata colisao de nome** e funde duplicatas do mesmo orgao. Foi escrita
  depois da varredura de 08/08/2026, que logou quatro casos (SEFIN RO, Seduc AL, IFFar, UEAP). Ela modela dois
  casos: mesmo orgao, e orgaos distintos que por acaso disputam o nome. **Falta o terceiro: mesmo orgao, dois
  concursos.**
- **`_e_falha_de_credencial` ja trata causa que retry nao conserta.** Login vencido, chave invalida e saldo
  zerado do z.ai (codigo `1113`) curto-circuitam as chamadas seguintes da rodada, com alerta que nomeia a
  causa. Foi escrita depois de 14/10 a 22/10/2026, quando o Lucas recebeu 24 avisos genericos por dia sem
  pista de que o problema era OAuth expirado. **`RateLimitError` nao esta nessa lista**, e por isso a cota
  esgotada gastou tres tentativas por item, em cada uma das 13 varreduras.
- **`_alerta_uma_vez_por_dia` funcionou.** O Lucas recebeu **um** alerta de extracao degradada, nao treze. O
  que nao tem limite por dia e o card de concurso, porque com identidade correta ele nunca precisou de um.

## 2. Decisao

### 2.1. Identidade: a chave canonica que discorda vence o nome

Quando o item carrega `pci_id` e a linha candidata tem `pci_id` nao nulo e **diferente**, nao e a mesma linha,
e nenhum fallback mais fraco pode dizer que e. Quando a linha candidata tem `pci_id` **nulo**, o casamento por
nome continua valendo e a linha e rechaveada, que e o que a ADR-0001 ja manda: e o caso legado das portas de
HTML e do Gran, e foi o que rechaveou 59 linhas em 24/11 sem perder nenhuma.

### 2.2. A unicidade no banco: decisao do dono

Corrigir so o casamento para a linha nova e necessario, e nao e suficiente. Com o casamento corrigido, o
segundo edital vira um `INSERT` que bate no `UNIQUE(area, nome)` da tabela, cai no `except sqlite3.Error` do
`atualizar_concurso` e devolve `0`: o concurso deixa de ser renotificado, mas continua sem entrar. Trocaria
spam por silencio, e silencio e o sintoma pior.

Em SQLite nao se remove um `UNIQUE` de nivel de tabela sem recriar a tabela, e o `kanban/REGRAS.md` diz
**"migracao de schema e aditiva e idempotente; nunca `DROP`, nunca recriar tabela com dado dentro"**. Essa
regra e do dono, entao a escolha e dele. As duas opcoes reais estao na secao 4.

### 2.3. Cota com hora de reset e causa que retry nao conserta

Um erro de cota que traz o instante de volta pertence a mesma familia da credencial recusada: a resposta nao
muda antes daquela hora. Ele curto-circuita o resto da rodada, nomeia a causa no alerta, e **suspende o
catch-up horario ate o instante de reset**, por marcador em arquivo, do mesmo jeito que o
`.last_success_date` ja faz. O marcador e reescrito a cada nova ocorrencia, entao errar o fuso do provedor
custa exatamente uma varredura, nao um dia.

## 3. Requisitos

### 3.1. Identidade

- **R-80** Item com `pci_id` nunca casa com linha cujo `pci_id` seja nao nulo e diferente. Vale para os tres
  fallbacks: link especifico, `(area, nome)` e casamento de entidade.
- **R-81** Item com `pci_id` casa com linha de `pci_id` **nulo** pelas regras de hoje, e grava o `pci_id` na
  linha (rechave). Comportamento preservado da ADR-0001.
- **R-82** Item **sem** `pci_id` (Gran, portas de HTML de reserva) mantem a ordem de identidade de hoje, sem
  mudanca de comportamento.
- **R-83** Dois editais distintos do mesmo orgao, na mesma area, podem coexistir como duas linhas. A
  unicidade do banco deixa de impedir isso, pelo caminho que o dono escolher na secao 4.
- **R-84** A migracao preserva `id`, `estado_usuario` e todos os campos de todas as linhas. Nenhuma linha e
  apagada e nenhuma e fundida. O `id` importa porque e o `callback_data` dos botoes do Telegram: perder o
  `id` quebra o historico de estrelas do Lucas.
- **R-85** A migracao **nao divide** linha que ja colidiu. O reparo das linhas colididas e separado (3.3),
  porque exige julgamento sobre qual dado pertence a qual edital.
- **R-86** Colisao de identidade que o codigo nao consiga resolver nunca vira silencio: entra no log como erro
  nomeado, pela regra de fail-open do projeto.
- **R-98** A decisao de identidade e a escrita dela acontecem na mesma transacao protegida contra outro
  escritor, ou a linha e revalidada na escrita e a resolucao refeita se ela mudou. **Requisito de garantia,
  nao de defeito vivo:** medido em 26/11/2026, este sistema tem um escritor so, por construcao. O codigo nao
  tem thread, async nem multiprocessing; o `flock -n` do `run_daily.sh` impede duas varreduras ao mesmo
  tempo; nao ha servico residente no notebook (nenhum `systemd` e nenhum processo entre varreduras); e os
  callbacks do Telegram sao processados DENTRO da varredura, em `ConcursoBot._processar_callbacks_telegram`.
  O requisito existe porque qualquer uma dessas tres coisas basta para ele virar defeito vivo: um servico
  residente de Telegram, uma varredura com thread, ou um segundo processo escrevendo no mesmo arquivo.

- **R-97** A mesma colisao chega ao **alerta do dia**, uma vez por dia como os outros alertas. Requisito
  separado do R-86 por decisao do dono em 25/11/2026 (secao 4, item 5): o log e o banco, o alerta e o bot, e o
  ticket da migracao nao carrega o `src/core/bot.py`. Enquanto o R-97 nao integrar, a colisao fica registrada
  no log e nao chega ao Telegram: isso e divida declarada, com prazo de uma onda, nao requisito abandonado.

- **R-99** Enquanto a regra de nome nao estiver escrita como tabela (R-100), o `_resolver_nome_sem_colisao` e
  **conservador e nao funde**: o nome novo so vence quando nenhuma outra linha da area o ocupa (COLLATE
  NOCASE); havendo qualquer conflito, a linha mantem o nome atual e a colisao entra no log (R-86). A funcao
  nao funde linha e nao apaga linha, em nenhum caminho. **Divida declarada, nao requisito abandonado:** quem
  a escreve como regra e o R-100. O custo desta escolha foi medido no log de producao em 26/11/2026, e nao e
  suposicao: o caminho conservador disparou **109 vezes**, a fusao disparou **7 vezes em toda a historia do
  bot** e a ultima foi em **15/09/2026**. Ate o R-100 integrar, duplicata do mesmo orgao continua no banco,
  que e exatamente o estado de hoje em producao.
- **R-100** A regra de nome e de fusao e escrita como **tabela de decisao enumerada** na ADR-0005, **antes**
  do codigo. As linhas da tabela sao os estados que a unicidade nova passa a permitir, pelo produto de tres
  eixos: existe conflito pelo nome ou nao; a chave da linha em conflito e nula, igual a do item ou diferente;
  e o nome em conflito e do mesmo orgao ou nao. Cada linha diz tres coisas: o nome final, se funde e o que
  vai para o log. Nenhum estado fica sem linha, e cada linha tem um teste. A tabela tem de satisfazer um
  invariante, e ele e o criterio de aceite mais importante: **a funcao nunca devolve o nome novo deixando
  atras de si um conflito que ela nao fundiu.** Os quatro defeitos achados nas cinco revisoes do ticket da migracao sao,
  dois deles, violacoes deste invariante; os outros dois sao o empate sem ordem e a escrita do nome separada
  da escrita da chave, ambos ja resolvidos com a migracao.

### 3.2. Cota da LLM

- **R-87** Erro de cota com instante de reset e causa que retry nao conserta na rodada: a primeira ocorrencia
  curto-circuita as chamadas seguintes, como a falha de credencial ja faz.
- **R-88** O alerta nomeia a causa e a hora de volta, em vez do generico "varredura incompleta". Uma vez por
  dia, como os outros.
- **R-89** O catch-up horario nao roda antes do instante de reset. O marcador e arquivo em `logs/`, lido pelo
  `scripts/run_daily.sh` antes do lock, e reescrito a cada nova ocorrencia.
- **R-90** Marcador ausente, ilegivel ou com data invalida **nao** impede a varredura: fail-open.

### 3.3. Reparo das linhas que ja colidiram

- **R-91** O reparo e script com `--dry-run`, e o `--dry-run` e o padrao: sem ele o script nao escreve.
- **R-92** O reparo preserva o `estado_usuario` da linha original e **nao notifica**: o edital separado em
  linha nova entra como ja notificado. Senao o reparo vira um flood de cards antigos.
- **R-93** Os cinco casos confirmados pelo spike de 24/11 (`563`, `1131`, `1445`, `1587`, `1681`) entram no
  reparo. Os dois duvidosos (`930` UNIFEI, `1113` UERJ) **nao**: decisao do dono, caso a caso.
- **R-94** O reparo roda em producao com backup do banco antes, e com a contagem de linhas conferida antes e
  depois.

### 3.4. Freio de renotificacao (rede de seguranca)

- **R-95** Um mesmo `id` que notificaria mais de N vezes no mesmo dia para de notificar, e sai um alerta
  unico dizendo qual concurso travou o freio. `N` e configuravel, com padrao conservador.
- **R-96** O freio e por dia e por `id`, nao por area: ele existe para a classe inteira de defeito, nao so
  para a causa de 25/11.

## 4. Decisoes do dono

> A primeira e a quinta foram decididas em 25/11/2026, e a sexta em 26/11/2026; as outras tres seguem
> em aberto.

1. **Como abrir a unicidade (R-83) — DECIDIDA em 25/11/2026: recriar a tabela.** O dono respondeu
   «Recria a tabela» no chat, e a excecao a regra de migracao aditiva foi aberta por escrito no
   `kanban/REGRAS.md`, com escopo de um caso. O raciocinio que sustentou a recomendacao fica como
   registro. Recomendacao, agora confirmada: **indice unico por expressao**,
   `(area, nome, COALESCE(pci_id, ''))`, substituindo o `UNIQUE(area, nome)` de tabela. O `COALESCE` existe
   para nao perder a dedupe das linhas sem `pci_id`: em SQLite, `NULL` nao colide com `NULL` numa chave
   unica, e sem ele duas linhas do Gran com o mesmo nome passariam a ser aceitas. O SQLite de producao e
   3.45.1, e indice por expressao existe desde a 3.9. Isso exige **recriar a tabela uma vez**, pelo
   procedimento documentado do SQLite, dentro de transacao e com backup antes, o que colide com a regra
   "nunca recriar tabela com dado dentro" do `kanban/REGRAS.md`. O projeto ja fez isso uma vez, no
   `_migrate_to_v3`. A alternativa e **desambiguar o `nome`** na escrita, acrescentando algo do proprio
   edital ao nome da segunda linha: nao mexe no schema, mas polui o campo que o Lucas le no card, e e o
   campo pelo qual o Gran e as portas de HTML casam. Recomendo a primeira, com a regra relaxada uma vez e por
   escrito, em vez de piorar o dado que o humano le.
2. **Os dois duvidosos (R-93).** `930` (UNIFEI) e `1113` (UERJ) tem nome de criacao diferente do nome de hoje,
   e a maquina nao sabe dizer se e o mesmo concurso. Ficam fora do reparo automatico ate ele decidir.
3. **O `N` do freio (R-95).** Sugestao: `3` por dia. Com identidade correta, um concurso legitimo quase nunca
   passa de uma notificacao por dia; tres da folga para avanco de fase e mudanca de prazo no mesmo dia.
4. **Se o freio entra nesta fase.** Ele e rede de seguranca, nao conserto: sem ele, a fase ainda resolve o
   PED-07. E o primeiro candidato a corte se o dono quiser a fase menor.
5. **Onde entra o alerta do dia da colisao (R-86/R-97) — DECIDIDA em 25/11/2026: ticket separado.** O
   revisor do ticket da migracao apontou, com razao, que a spec pedia log **e** alerta e o ticket entregava so o log, e
   devolveu a decisao de escopo. O dono respondeu «Ticket separado» no chat. O requisito foi partido em R-86
   (log, no banco, junto da migracao) e R-97 (alerta do dia, no bot, em ticket proprio). Razao registrada: o diff da migracao e o
   que o dono le pessoalmente antes de uma migracao irreversivel sobre ~1.700 linhas, e inflar esse diff com
   o `src/core/bot.py` — o arquivo mais disputado da fase, que os tickets do freio de renotificacao e do concurso filtrado tambem querem — encareceria
   a unica revisao humana que a fase tem. A alternativa era ampliar o ticket da migracao, que o revisor recomendava.

6. **O escopo da migracao depois da terceira reprovacao - DECIDIDA em 26/11/2026: reduzir ao que esta
   provado.** A quinta revisao achou o **quarto** defeito distinto na mesma funcao, e todos os quatro moram
   em `_resolver_nome_sem_colisao`, `_fundir` e nas buscas de fallback. O arquiteto recusou o conserto de uma
   linha que estava disponivel, porque seria a quinta emenda na mesma sequencia de guardas, e levou ao dono
   duas opcoes: reduzir o ticket ou tentar uma sexta rodada. O dono respondeu «pode fazer o que recomendou»
   no chat. Decisao: o ticket fica com a migracao, a ordem de identidade, o desempate explicito e o criterio
   unico de nulidade, nenhum deles contestado em cinco revisoes, e passa a cumprir o R-99 no lugar da logica
   de nome e fusao; a regra de nome vira ticket proprio, cuja primeira entrega e a tabela do R-100, nao codigo.
   Causa raiz registrada: **a regra nunca foi escrita como regra.** Nao ha, em nenhuma versao desta spec,
   requisito que diga o que a funcao deve fazer em cada estado; R-80 a R-86 falam de casamento, de migracao e
   de log, e nunca do nome. Quatro rodadas de implementacao foram gastas em comportamento que requisito
   nenhum pediu. A alternativa, a sexta rodada, era apostar que o quinto caso nao existe depois de quatro
   apostas perdidas.

## 5. Fora de escopo

- **A matriz de decisao e a elegibilidade.** Conferidas, corretas, nao se mexe.
- **A cota compartilhada.** A mesma assinatura alimenta a LLM deste bot, o cerebro do agente de casa e os
  executores da esteira, e nenhum dos tres sabe dos outros. E um problema de orquestracao, de outra fase.
- **Trocar o backend de LLM.** Decisao de operacao, nao de codigo.
- **A SPEC-002** (sonda e conserto automatico) segue sem ticket, e esta spec nao a cobre.
