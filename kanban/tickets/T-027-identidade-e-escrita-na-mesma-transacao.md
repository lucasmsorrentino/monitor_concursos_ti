---
id: T-027
titulo: Identidade e escrita na mesma transacao protegida
tipo: codigo
nivel: M+
status: backlog
repo: principal
spec: [SPEC-003, R-98]
depende_de: [T-020, T-026, T-028]
toca: [src/database/manager.py, tests/test_database_manager.py]
recursos: []
afinidade:
retornos: 0
---
# T-027 · Identidade e escrita na mesma transacao protegida

## Contexto

O revisor do T-020 (Codex, G-, 26/11/2026) reproduziu, em banco SQLite em arquivo com duas conexoes e
sincronizacao determinista, uma janela entre a decisao de identidade e a escrita dela. A busca le uma linha
sem chave canonica; antes do `UPDATE`, outra conexao atribui um `pci_id` a essa linha; o `UPDATE` grava pelo
id ja escolhido e **sobrescreve a chave sem revalidar**. No cenario dele, as duas chamadas devolveram `1`, o
edital `296044` desapareceu da busca e o `296538` ficou no id `1` com o prazo do segundo. Ou seja: a chave
canonica de um edital foi sobrescrita pela de outro, em silencio.

**Isto NAO e defeito vivo hoje, e e por isso que esta num ticket separado.** Medido em producao em
26/11/2026: nao ha thread, async nem multiprocessing em `src/` nem no `main.py`; o `flock -n` do
`scripts/run_daily.sh` impede duas varreduras simultaneas; o notebook nao tem servico residente (nenhum
`systemd`, nenhum processo do monitor entre varreduras); e os callbacks do Telegram, que tambem escrevem no
banco, rodam DENTRO da varredura, chamados por `ConcursoBot._processar_callbacks_telegram`. Um escritor so,
por construcao.

O requisito R-98 existe porque **tres mudancas plausiveis** quebram essa garantia, e nenhuma delas pareceria
perigosa na hora: por um servico residente de Telegram (para o botao responder na hora, em vez de na proxima
varredura), por paralelizar as tres areas da varredura, ou por qualquer segundo processo escrevendo no mesmo
arquivo. Quem fizer uma dessas tres precisa achar este ticket.

## Critério de aceite

- [ ] A decisao de identidade e a escrita que decorre dela ficam na mesma transacao protegida contra outro
      escritor, ou a linha e revalidada no momento da escrita e a resolucao refeita se ela mudou.
- [ ] Com duas conexoes e sincronizacao determinista no cenario do revisor, os dois editais continuam em ids
      distintos, cada um com o seu prazo, e o id legado continua com o edital que o ocupava.
- [ ] Nenhuma chave canonica e sobrescrita por outra sem que a resolucao de identidade seja refeita.
- [ ] O caminho de um escritor so nao fica mais lento de forma observavel na suite, e nao muda de resultado.
- [ ] Falha de bloqueio no banco nao vira silencio: entra no log com nome proprio, pela regra de fail-open.

## Plano de testes

Costura: `DatabaseManager.atualizar_concurso` e `buscar_registro`, as mesmas interfaces publicas do T-020.
Pega: que duas escritas intercaladas nao se sobrescrevem e que o caminho sequencial nao muda.
Nao pega: concorrencia real com o relogio solto. A sincronizacao e determinista de proposito, porque teste de
corrida com `sleep` e teste intermitente, que e pior que teste ausente.
Oráculo: os ids, prazos e chaves escritos a mao no fixture.

- `test_duas_escritas_intercaladas_nao_trocam_a_chave`: o cenario exato do revisor, com os dois ids
  preservados e cada prazo no seu edital.
- `test_rechave_revalida_a_linha_antes_de_gravar`: a linha ganha `pci_id` entre a busca e a escrita; a
  segunda escrita refaz a resolucao em vez de sobrescrever.
- `test_caminho_de_um_escritor_nao_muda`: os casos de identidade do T-020 seguem com o mesmo resultado.
- `test_falha_de_bloqueio_entra_no_log`: bloqueio simulado produz erro nomeado, nao silencio.

## Fora do escopo

- **Mexer na ordem de identidade ou no desempate.** E do T-020, ja decidido e provado.
- **Trocar o SQLite por outro banco, ou ligar WAL globalmente.** Se o conserto pedir WAL, proponha no
  relatorio com medida, e nao o ligue de passagem: muda o comportamento de todo o resto.
- **Criar o servico residente de Telegram.** Este ticket so deixa o banco pronto para quando ele existir.

## Notas do arquiteto

Por que M+: a regra e conhecida, mas sao varios caminhos de escrita no mesmo arquivo e o teste exige
sincronizacao determinista entre duas conexoes, que e a parte que erra facil.

Por que separado do T-020, e nao uma quinta rodada dele: o T-020 ja levou quatro rodadas, e o defeito dele
que sobra (o estado intermediario da fusao) e alcancavel com um escritor so. Este, nao. Misturar os dois
atrasaria um conserto que o Lucas precisa em producao agora por causa de um que nenhum caminho de hoje
alcanca. A medida que sustenta isso esta no Contexto e na SPEC-003 R-98, com data.

Depende do T-020 integrado, porque mexe nas mesmas funcoes e o T-020 e o dono delas.
