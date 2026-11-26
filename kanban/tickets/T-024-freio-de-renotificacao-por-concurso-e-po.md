---
id: T-024
titulo: Freio de renotificacao por concurso e por dia
tipo: codigo
nivel: M-
status: backlog
repo: principal
spec: [SPEC-003, R-95, R-96]
depende_de: [T-021, T-026]
toca: [src/core/bot.py, tests/test_concurso_bot.py]
recursos: []
afinidade:
retornos: 0
---
# T-024 · Freio de renotificacao por concurso e por dia

## Contexto

Em 25/11/2026 um mesmo concurso recebeu 24 cards em um dia, e isso passou treze horas sem ninguem perceber.
Os alertas de varredura ja tem limite de um por dia (`_alerta_uma_vez_por_dia`); o **card de concurso** nao
tem nenhum, porque com identidade correta ele nunca precisou de um.

Este ticket e rede de seguranca para a classe inteira de defeito, nao para a causa de 25/11, que os tickets
da identidade e da cota resolvem. Ele existe para que a proxima causa nova de laco de notificacao seja
percebida no mesmo dia, em vez de depois de treze horas.

## Critério de aceite
- [ ] Um mesmo `id` que notificaria mais de `N` vezes no mesmo dia para de notificar (R-95)
- [ ] Quando o freio trava, sai **um** alerta dizendo qual concurso travou e quantas vezes
- [ ] O freio e por `id` e por dia, **nao** por area (R-96)
- [ ] `N` vem da config, com padrao conservador; valor invalido cai no padrao (fail-open)
- [ ] Concurso que notifica dentro do limite nao muda em nada o comportamento de hoje
- [ ] A contagem do freio vira o dia junto com os outros marcadores de «uma vez por dia»
- [ ] Suite verde; nenhum teste existente afrouxado

## Plano de testes
Costura: `ConcursoBot.executar()`, com notificador e banco dublados, como os testes de `TestResumoSemanal` ja
fazem. Pega: a contagem por `id`, o corte e o alerta. Nao pega: **por que** o concurso notificou tantas
vezes, que e assunto dos outros tickets.
Oráculo: literais escritos a mao; relogio dublado para atravessar a virada do dia.

Testes que nascem vermelhos:

- `test_concurso_para_de_notificar_depois_do_limite_do_dia`
- `test_freio_dispara_um_alerta_so_com_o_nome_e_a_contagem`
- `test_freio_conta_por_id_e_nao_por_area`
- `test_concurso_dentro_do_limite_notifica_como_hoje`
- `test_contagem_do_freio_vira_o_dia`
- `test_limite_invalido_na_config_cai_no_padrao`

## Fora do escopo
- Consertar a **causa** das repeticoes. Sao os tickets da identidade e da cota.
- Mexer na matriz de decisao ou na elegibilidade.

## Notas do arquiteto

**Por que M−:** regra simples, um modulo, mas toca o caminho de notificacao, que e o caminho que o Lucas ve.

**A dependencia e por conflito de arquivo, nao por logica:** este ticket e o da cota escrevem os mesmos dois
arquivos (`src/core/bot.py` e `tests/test_concurso_bot.py`). Nao espere comportamento do outro ticket, e nao
construa nada em cima do que ele fez.

**Este e o ticket a cortar se a fase ficar grande.** Sem ele, a fase ainda resolve o PED-07. Sugestao de `N`:
`3` por dia, que da folga para avanco de fase e mudanca de prazo no mesmo dia.

**Nao implemente o freio apagando notificacao: ele suspende e avisa.** Freio silencioso trocaria um defeito
ruidoso por um silencioso, que e pior pela regra de fail-open do projeto.
