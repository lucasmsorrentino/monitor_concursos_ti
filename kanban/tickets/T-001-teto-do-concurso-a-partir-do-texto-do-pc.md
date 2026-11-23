---
id: T-001
titulo: Teto do concurso a partir do texto do PCI
tipo: codigo
nivel: P+
status: backlog
repo: principal
spec: [SPEC-001, R-01]
depende_de: []
toca: [src/utils/salario.py, tests/test_salario.py]
recursos: []
afinidade:
retornos: 0
---
# T-001 · Teto do concurso a partir do texto do PCI

## Contexto

O PCI Concursos publica o **teto do concurso** (`GLOSSARIO.md`) como texto livre, no campo `vagas_salario`
da resposta do servidor MCP: "454 vagas ate R$ 8.628,87", "Vagas ate R$ 21.825,31", "Cadastro de reserva ate
R$ 14.189,97". A decisao de elegibilidade precisa desse valor como numero.

Este ticket entrega so o parser, numa funcao pura. Quem o usa vem depois. O contrato esta na SPEC-001,
secao 3.2.

## Critério de aceite

- [ ] `src/utils/salario.py` expoe `teto_de(texto: str | None) -> float | None`, que devolve o **maior** valor
      em reais citado no texto, ou `None` quando nao ha valor aproveitavel.
- [ ] Le o formato brasileiro com separador de milhar e virgula decimal: `"R$ 8.628,87"` vira `8628.87`;
      `"R$ 950,00"` vira `950.0`; `"R$ 21.825,31"` vira `21825.31`.
- [ ] Le os tres enunciados reais do campo `vagas_salario`: com o numero de vagas na frente, sem ele, e com
      "Cadastro de reserva" (que aparece com `r` minusculo e maiusculo).
- [ ] Faixa devolve o **topo**: `"Os vencimentos mensais vao de R$ 1.840,36 a R$ 18.540,71"` vira `18540.71`.
- [ ] Le "mil" por extenso: `"salarios de ate R$ 6,6 mil"` vira `6600.0`; `"R$ 12 mil"` vira `12000.0`.
- [ ] **Banda de sanidade:** valor abaixo de `R$ 500,00` ou acima de `R$ 80.000,00` e ignorado. Existe para
      nao confundir taxa de inscricao (`"A taxa e de R$ 65,00"`) nem valor por hora
      (`"Dentista recebe R$ 32,64 por hora"`) com salario mensal. Texto em que **so** ha valores fora da banda
      devolve `None`, nunca o valor fora da banda.
- [ ] `None`, string vazia, `"Vagas"` e `"a combinar"` devolvem `None` sem levantar excecao.
- [ ] Modulo sem dependencia externa: so `re` da stdlib, como `src/utils/text.py` ja faz.

## Plano de testes

Costura: `salario.teto_de`, a propria funcao publica. Pega todo formato que o campo `vagas_salario` e o texto
da noticia do PCI usam. Nao pega de onde o texto veio nem o que se decide com o numero.

Oráculo: literais escritos a mao neste ticket, retirados de respostas reais do servidor (as fixtures em
`tests/fixtures/pci_mcp/`) e de uma noticia do PCI lida em 20/11/2026. Nenhum esperado se calcula do jeito que
o codigo calcula.

Testes que nascem vermelhos em `tests/test_salario.py`:

- `test_teto_de_le_formato_brasileiro_com_milhar` — `"454 vagas ate R$ 8.628,87"` devolve `8628.87`.
- `test_teto_de_le_valor_sem_separador_de_milhar` — `"Vagas ate R$ 950,00"` devolve `950.0`.
- `test_teto_de_le_cadastro_de_reserva_nas_duas_grafias` — `"Cadastro de reserva ate R$ 14.189,97"` e
  `"Cadastro de Reserva ate R$ 12.937,29"` devolvem `14189.97` e `12937.29`.
- `test_teto_de_em_faixa_devolve_o_topo` — `"vao de R$ 1.840,36 a R$ 18.540,71"` devolve `18540.71`.
- `test_teto_de_le_mil_por_extenso` — `"ate R$ 6,6 mil"` devolve `6600.0` e `"R$ 12 mil"` devolve `12000.0`.
- `test_teto_de_ignora_taxa_de_inscricao` — `"A taxa e de R$ 65,00 para nivel fundamental"` devolve `None`.
- `test_teto_de_ignora_valor_por_hora` — `"Dentista recebe R$ 32,64 por hora"` devolve `None`.
- `test_teto_de_ignora_valor_absurdo` — `"R$ 980.000,00"` devolve `None`.
- `test_teto_de_mistura_taxa_e_salario_devolve_o_salario` — `"salarios de ate R$ 8.628,87. A taxa e de
  R$ 80,00"` devolve `8628.87`.
- `test_teto_de_sem_valor_devolve_none` — `None`, `""`, `"Vagas"` e `"a combinar"` devolvem `None`.

## Fora do escopo

- Somar beneficio (vale, auxilio) ao teto. A SPEC-001 compara teto cru com o corte.
- Descobrir o salario do **cargo** da area. O PCI nao publica isso; ver ADR-0002.
- Chamar o servidor MCP ou abrir pagina. Este modulo so recebe texto.
- Normalizar jornada (20 h, 40 h).

## Notas do arquiteto

- **P+ e nao P−:** o padrao de parse por regex ja existe no repo (`src/scrapers/pci_comum.py` faz isso com
  datas, inclusive a logica de "a ultima data da frase vence"), entao o caminho e claro. O sinal `+` e pela
  banda de sanidade e pelo "mil", que sao o detalhe onde se erra.
- Espelhe o estilo de `src/scrapers/pci_comum.py`: regex compilado no topo do modulo, com um comentario
  dizendo que frase real cada um pega.
- Cuidado com a ordem do parse de "mil": `"R$ 6,6 mil"` tem virgula decimal **e** multiplicador. Trate "mil"
  antes de aplicar a regra de milhar, senao `6,6` vira `6.6` e some na banda de sanidade.
- A banda de sanidade e refinamento desta funcao sobre a SPEC-001 secao 3.2, que diz apenas "valor legivel".
  Ela esta no aceite, e nao e opcional.
