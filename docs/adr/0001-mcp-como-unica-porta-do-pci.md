# O servidor MCP e a unica porta do PCI Concursos

O PCI publicou em 03/2026 um servidor MCP oficial (`https://mcp.pciconcursos.com.br/mcp`, sem autenticacao,
somente leitura) que devolve, ja estruturado, o que as duas portas de HTML liam raspando pagina: nome do orgao,
`uf`, `regiao` (inclusive `NACIONAL`), teto do concurso, total de cargos, link da noticia, e as datas de
inscricao ja calculadas pelo servidor (`aberto`, `em_breve`, `dias_ate_fim`). O `id` dele e o mesmo numero da
noticia que a pagina de cargo trazia na classe CSS, entao continua servindo de chave de dedup (`pci_id`).

Por isso o `PciScraper` (pagina de cargo) e o `PciNacionalScraper` (lista nacional) saem do caminho padrao. Eles
ficam no repo, desligaveis e religaveis por variavel de ambiente, como reserva se o MCP sair do ar ou mudar o
contrato.

## Alternativas consideradas

- **Tres portas ao mesmo tempo.** Cobertura marginalmente maior e o parse de HTML continuaria quebrando a cada
  mudanca de layout, com tres listas para deduplicar na mesma rodada.
- **Apagar os dois scrapers.** Repo mais limpo, sem reserva nenhuma. Uma fonte de terceiro com tres meses de
  vida nao merece ser ponto unico de falha.

## Consequencias

- A lista nacional deixa de precisar de LLM: a porta nacional antiga mandava cada item novo para o modelo, e o
  MCP ja devolve o campo. O custo por rodada cai.
- O MCP so lista concurso com inscricao **aberta ou prestes a abrir**. Edital encerrado nao aparece mais, entao
  a deteccao de "inativo" passa a vir do desaparecimento do item, nao de uma data no passado.
- `buscar_por_cargo` corta em 200 resultados (medido em 22/11/2026: `professor` devolve exatamente 200,
  `tecnico` 183). Nenhum termo de TI passa de 69 hoje, mas area com termo generico precisa fatiar a busca.
