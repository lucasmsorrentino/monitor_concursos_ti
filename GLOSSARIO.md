# Monitor de concursos

O bot varre fontes de concurso publico, decide o que o Lucas ainda nao viu e manda para o Telegram, uma area
por chat. Os termos abaixo valem na spec, no ticket, no teste e no codigo.

## Linguagem

**Area**:
Uma vertical monitorada (TI, EDUCACAO), com o seu chat, as suas palavras-chave e as suas linhas no banco.
_Evite_: vertical, assunto, tema

**Porta**:
Um ponto de entrada numa fonte. O PCI Concursos tem mais de uma porta possivel (pagina de cargo, lista
nacional, servidor MCP); o blog do Gran tem uma.
_Evite_: fonte (fonte e o site; porta e o caminho ate ele), endpoint, scraper

**Rodada**:
Uma execucao completa do `main.py`, com todas as areas e todas as portas.
_Evite_: varredura, ciclo, execucao

**Fase**:
O estagio do edital, em vocabulario controlado (`previsto`, `banca_definida`, `edital_publicado`,
`inscricoes_abertas`, `inscricoes_encerradas`). Vive em `src/utils/fases.py`.
_Evite_: status (status e o texto livre da fonte), etapa, estagio

**Teto do concurso**:
O maior salario publicado para o edital inteiro, somando todos os cargos ("Vagas ate R$ 18.540,71"). **Nao e**
o salario do cargo da area: num edital com 86 cargos o teto costuma ser de procurador ou medico. E a unica
evidencia salarial que o PCI publica.
_Evite_: salario, remuneracao, piso, teto salarial

**Esfera**:
O nivel administrativo do orgao: `federal` (inclui estatal federal, instituto federal e universidade
federal), `estadual`, `distrital`, `municipal`, `conselho_profissional`. Conselho profissional nao e federal.
_Evite_: nivel, ambito, jurisdicao

**Elegibilidade**:
A decisao do bot sobre notificar ou nao um concurso, com o motivo. E coluna separada de `estado_usuario`:
elegibilidade e do bot, `estado_usuario` e do Lucas (a estrela e o x dos botoes do Telegram).
_Evite_: filtro, relevancia, score

**Corte fora do Sul**:
O piso de teto do concurso exigido para notificar um concurso que nao e do Sul (PR, SC, RS). Por area.
Concurso do Sul nao passa pelo corte.
_Evite_: corte salarial, threshold, limite

**Municipal inflado**:
Concurso municipal (prefeitura, camara, consorcio) fora do Sul cujo teto vem de outro cargo, nao do cargo da
area. Reconhecido pela quantidade de cargos do edital.
_Evite_: teto falso, ruido municipal

**Fail-open**:
A regra de que falha tecnica faz o concurso entrar, marcado, em vez de sumir. Erro nunca vira silencio.
_Evite_: fail-safe, modo permissivo

**Sonda**:
A verificacao barata de madrugada, sem LLM e por amostra. Duas: a de **ambiente** (no notebook de producao:
venv, cron, marcador, banco, credencial, rede, disco, relogio) e a de **contrato** (nas fontes: campo por
campo contra piso declarado). Nao e rodada: a sonda nunca grava concurso nem manda card.
_Evite_: healer, monitor, health check, watchdog

**Sintoma**:
Uma observacao da sonda que nao bate com o esperado, com o numero cru que a sustenta. Sintoma nao diz o que
fazer; quem diz e a classe.
_Evite_: erro, falha, alerta

**Classe de sintoma**:
A causa nomeada, de uma lista fechada de nove: `credencial`, `rede`, `agendamento`, `ambiente`, `fonte_morta`,
`fonte_vazia`, `fonte_parada`, `contrato`, `regressao` (mais `contrato_novo`, que e so nota). Duas delas
acionam conserto; as outras viram alerta. A triagem escolhe uma, pela primeira regra que casa.
_Evite_: tipo de erro, categoria, severidade

**Linha de base**:
A media movel das ultimas sete noites **saudaveis** de preenchimento de cada campo, por porta. Noite de rede
ou credencial caida nao entra, para nao rebaixar o piso e mascarar a queda seguinte.
_Evite_: baseline, historico, media

**Dossie**:
A pasta que a sonda grava quando ha sintoma consertavel: a resposta crua, a fixture, o **teste vermelho
escrito pela sonda** e o relatorio. E o que o agente de conserto recebe, e a evidencia que fica mesmo quando
nenhum conserto roda.
_Evite_: bundle, pacote, snapshot

**Conserto**:
O agente confinado que faz o teste do dossie passar, num worktree, sem tocar em `tests/`. Entrega branch, nao
deploy.
_Evite_: fix, cura, patch automatico

**Gate**:
As nove condicoes automaticas que o diff do conserto precisa cumprir para ser aceito. Nenhuma e avaliada pelo
agente que escreveu o diff.
_Evite_: validacao, revisao, aprovacao
