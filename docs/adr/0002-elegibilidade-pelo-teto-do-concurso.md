# A elegibilidade usa o teto do concurso, e a esfera federal nao passa pelo corte

O Lucas mora em Curitiba, e servidor efetivo na UFPR e tem filha pequena: concurso fora do Sul so interessa
com salto real de salario. O bot passa a nao notificar, **na area TI**, concurso fora do Sul (PR, SC, RS) cujo
salario nao alcance o corte da area.

A dificuldade e que o PCI nunca publica o salario do cargo, so o **teto do concurso**. Conferido em 20/11/2026
numa noticia de edital com 86 cargos: a pagina traz a faixa do edital inteiro ("de R$ 1.840,36 a
R$ 18.540,71") e a lista de cargos sem valor ao lado de cada um. Entao a decisao se apoia em duas evidencias
negativas, as unicas que o dado sustenta:

1. **teto abaixo do corte** prova que o cargo da area tambem esta abaixo, porque o teto e o maximo do edital;
2. **municipal inflado** (prefeitura, camara ou consorcio fora do Sul com muitos cargos) significa que o teto
   e de outro cargo e nao diz nada sobre o da area.

A esfera `federal` fica isenta do corte: instituto federal e universidade federal pagam a tabela federal, que
nao chega ao corte de TI, e sao justamente a mobilidade que interessa a um servidor federal. Conselho
profissional nao conta como federal.

## Alternativas consideradas

- **Cortar federal tambem**, pela leitura literal do pedido. Em 22/11/2026 isso silenciaria IFTM (8.340),
  UEMG, UFMS, IFSP e IFG (5.215 cada). O dono preferiu manter.
- **Deep-dive com LLM** para estimar o salario do cargo na noticia (o plano antigo, `PLANO_EVOLUCAO_AGENTICA.md`
  secao 3.1). Mais preciso e mais caro, e apoiado na peca que ficou um mes fora do ar em 2026 (23/09 a 22/10).
  Fica fora desta fase.
- **Cortar tudo que nao e do Sul.** Mataria TRF3, USP e TCEES, que e o tipo de vaga que justifica a mudanca.

## Consequencias

- Concurso municipal fora do Sul com poucos cargos e teto alto continua entrando, mesmo que o cargo da area
  pague pouco: nao ha evidencia para descartar.
- O silencio e auditavel. A decisao e o motivo ficam no banco, e um resumo semanal lista o que foi filtrado.
- Fail-open: teto ilegivel, chamada que falhou ou `uf` desconhecida fazem o concurso entrar, marcado.
