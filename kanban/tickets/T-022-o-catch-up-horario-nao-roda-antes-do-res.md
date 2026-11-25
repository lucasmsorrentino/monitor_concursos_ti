---
id: T-022
titulo: O catch-up horario nao roda antes do reset conhecido
tipo: codigo
nivel: P+
status: backlog
repo: principal
spec: [SPEC-003, R-89, R-90]
depende_de: [T-021]
toca: [scripts/run_daily.sh, tests/test_run_daily.py]
recursos: []
afinidade:
retornos: 0
---
# T-022 · O catch-up horario nao roda antes do reset conhecido

## Contexto

O `scripts/run_daily.sh` roda de hora em hora e sai em tres linhas quando `logs/.last_success_date` tem a
data de hoje. Quando a varredura falha, o marcador nao e gravado e **todo** tick roda a varredura inteira:
em 25/11/2026 foram 13. O catch-up horario e requisito, e existe por um motivo medido: entre 01/07 e
08/08/2026, nove dias nao tiveram varredura nenhuma porque o notebook estava desligado na hora marcada.

O que ele nao previu foi causa com hora de volta conhecida. Quando a cota da LLM diz a que horas reseta,
repetir antes daquela hora e certeza de falhar igual, e cada repeticao repassa a matriz de decisao em todas
as linhas do banco.

## Critério de aceite
- [ ] O script sai sem rodar quando existe marcador de «nao antes de» com instante ainda no futuro (R-89)
- [ ] Marcador ausente, vazio, ilegivel ou com data invalida **nao** impede a varredura (R-90, fail-open)
- [ ] Marcador com instante no passado nao impede a varredura
- [ ] A checagem acontece **antes** do `flock`, junto da checagem do marcador do dia
- [ ] O dead-man switch continua funcionando: marcador de espera nao conta como varredura bem-sucedida e nao
      zera a conta de dias sem sucesso
- [ ] A saida quieta nao enche o log: no maximo uma linha por tick, como o caminho do marcador do dia

## Plano de testes
Costura: o proprio `scripts/run_daily.sh`, invocado com `REPO_DIR` apontando para arvore temporaria, no molde
de `tests/test_diagnostico_producao.py`, que ja testa script de shell neste repo. Pega: a decisao de rodar ou
nao e o codigo de saida. Nao pega: o `main.py`, que e dublado por um executavel falso dentro da arvore
temporaria.
Oráculo: instantes literais escritos a mao, relativos a um «agora» fixado pelo teste.

Testes que nascem vermelhos:

- `test_marcador_de_espera_no_futuro_sai_sem_rodar`
- `test_marcador_de_espera_no_passado_roda`
- `test_marcador_de_espera_ilegivel_roda`
- `test_marcador_de_espera_ausente_roda`
- `test_marcador_de_espera_nao_marca_sucesso_do_dia`

## Fora do escopo
- **Escrever** o marcador. Quem escreve e o ticket da cota; este so o honra.
- Mexer no dead-man, no `flock` ou na frequencia do cron.
- `scripts/install_schedule.*`, que o `kanban/REGRAS.md` proibe tocar.

## Notas do arquiteto

**Por que P+:** mecanico, e o padrao do marcador ja existe duas vezes no mesmo script
(`.last_success_date` e `.last_dead_man_alert`). O sinal e `+` por duas bordas: comparacao de instante em
`bash`, e a regra de fail-open. Use `date -d`, como o dead-man ja usa.

Nome sugerido para o marcador: `logs/.retry_nao_antes`, no mesmo diretorio e no mesmo estilo dos outros dois.
Conteudo: um instante ISO numa linha.

**O fuso e o ponto delicado, e a assimetria importa.** O provedor nao declara fuso. Errar para o lado de
rodar cedo custa **uma** varredura; errar para o lado de ficar parado custa um dia de monitoramento. Entao,
na duvida, rodar. Se o instante nao tiver fuso explicito, assuma o fuso local da maquina, que e o que o log
usa (ADR-0004), e siga.
