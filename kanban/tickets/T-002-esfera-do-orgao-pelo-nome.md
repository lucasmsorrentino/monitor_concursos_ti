---
id: T-002
titulo: Esfera do orgao pelo nome
tipo: codigo
nivel: M+
status: entregue
repo: principal
spec: [SPEC-001, R-05]
depende_de: []
toca: [src/utils/esfera.py, tests/test_esfera.py]
recursos: []
afinidade:
retornos: 0
atualizado: 2026-11-23T11:26-03:00
branch: t/T-002-esfera-do-orgao-pelo-nome
executor: glm
executor_impl: glm
corpo_lancado: 001ef14f1685
fora_do_toca: []
ponta: 420f3160da3c26f99d5c9ac6dccc8b7bcea35337
---
# T-002 · Esfera do orgao pelo nome

## Contexto

A elegibilidade isenta do corte salarial os concursos de **esfera** `federal` (ADR-0002): instituto federal e
universidade federal pagam a tabela federal, que nao alcanca o corte de TI, e sao justamente a mobilidade que
interessa a um servidor federal. Para isso o bot precisa classificar a esfera a partir do **nome do orgao**,
que e tudo o que a fonte da.

O nome vem no estilo do PCI, com a UF no sufixo: `"UFMS - Fundacao Universidade Federal de Mato Grosso do Sul
- MS"`, `"Camara de Cuiaba - MT"`, `"CRP/05 - Conselho Regional de Psicologia da 5a Regiao - RJ"`.

Este ticket entrega so o classificador, numa funcao pura. O contrato esta na SPEC-001, secao 3.3.

## Critério de aceite

- [ ] `src/utils/esfera.py` expoe `esfera_de(nome: str | None) -> str | None`, que devolve uma de
      `"federal"`, `"estadual"`, `"distrital"`, `"municipal"`, `"conselho_profissional"`, ou `None` quando o
      nome nao decide.
- [ ] **`municipal`**: "Prefeitura", "Camara" (de municipio), "Consorcio Intermunicipal", "Municipio de",
      "Secretaria Municipal", "Instituto de Previdencia do Municipio", "Fundo Municipal".
- [ ] **`federal`**: "Universidade Federal", "Instituto Federal", "Fundacao Universidade Federal",
      "Universidade Tecnologica Federal", "Ministerio", "Tribunal Regional Federal", "Tribunal Regional do
      Trabalho", "Tribunal Regional Eleitoral", "Policia Federal", "Policia Rodoviaria Federal",
      "Justica Federal", mais estatal federal pelo nome ("Correios", "Dataprev", "Transpetro", "Petrobras",
      "Caixa Economica Federal", "Banco do Brasil", "Serpro", "Embrapa", "Infraero", "Conab").
- [ ] **`estadual`**: "Universidade do Estado", "Universidade Estadual", "Secretaria de Estado",
      "Tribunal de Contas do Estado", "Tribunal de Justica", "Policia Civil", "Policia Militar",
      "Defensoria Publica do Estado", "Ministerio Publico do Estado", "Companhia/Banco do Estado",
      "Assembleia Legislativa", "Instituto do Meio Ambiente do Estado".
- [ ] **`distrital`**: orgao do Distrito Federal que nao e federal — "do Distrito Federal", "Distrital",
      e a UF `DF` no sufixo quando nada mais decide. `"DPDF - Defensoria Publica do Distrito Federal - DF"`
      e `distrital`, nao federal.
- [ ] **`conselho_profissional`**: "Conselho Regional", "Conselho Federal", "CRM", "CRO", "CREA", "CRC",
      "CRP", "CRA", "COREN", "OAB". **Conselho Federal de X e `conselho_profissional`, nao `federal`** —
      ADR-0002 diz isso de forma explicita.
- [ ] **Precedencia quando dois padroes casam**, declarada e testada, nesta ordem:
      `conselho_profissional` > `municipal` > `federal` > `distrital` > `estadual`.
      Ela resolve os pares reais: "Conselho Regional ... da 5a Regiao" nao e estadual;
      "Instituto de Previdencia do Municipio de Jundiai" nao e estadual por causa de "Instituto";
      "Universidade do Estado de Minas Gerais" nao e federal por causa de "Universidade".
- [ ] Nome que nao casa nada devolve `None`, e `None`/`""` tambem.
- [ ] Comparacao insensivel a acento e a caixa, reusando `normalizar_nome` de `src/utils/text.py`.
- [ ] Modulo sem dependencia externa.

## Plano de testes

Costura: `esfera.esfera_de`, a propria funcao publica. Pega a classificacao de um nome de orgao. Nao pega de
onde o nome veio nem o que a esfera libera na elegibilidade.

Oráculo: tabela de casos escrita a mao, com os nomes copiados das fixtures em `tests/fixtures/pci_mcp/`
(resposta real do servidor, 23/11/2026) e dos exemplos acima. O esperado de cada linha e julgamento humano,
nao saida do codigo.

Testes que nascem vermelhos em `tests/test_esfera.py`:

- `test_esfera_de_municipal` — parametrizado com "Prefeitura de Ijui - RS", "Camara de Cuiaba - MT",
  "Prefeitura e Camara de Coronel Freitas - SC", "Consorcio Intermunicipal ... - MG": todos `municipal`.
- `test_esfera_de_federal_universidade_e_instituto` — "UFMS - Fundacao Universidade Federal de Mato Grosso do
  Sul - MS", "IFSP - Instituto Federal de Educacao, Ciencia e Tecnologia de Sao Paulo - SP",
  "UTFPR - Universidade Tecnologica Federal do Parana - PR": todos `federal`.
- `test_esfera_de_federal_tribunal_e_ministerio` — "TRF3 - Tribunal Regional Federal da 3a Regiao",
  "TRT 4 - Tribunal Regional do Trabalho da 4a Regiao - RS", "Ministerio da Saude": todos `federal`.
- `test_esfera_de_estadual` — "UEMG - Universidade do Estado de Minas Gerais - MG", "TCEES - Tribunal de
  Contas do Estado do Espirito Santo - ES", "PCAC - Policia Civil do Estado do Acre - AC",
  "SECITECI - Secretaria de Estado de Ciencia ... - MT", "Banestes - Banco do Estado do Espirito Santo - ES":
  todos `estadual`.
- `test_esfera_de_distrital` — "DPDF - Defensoria Publica do Distrito Federal - DF" devolve `distrital`.
- `test_esfera_de_conselho_profissional` — "CRP/05 - Conselho Regional de Psicologia da 5a Regiao - RJ" e
  "Conselho Federal de Enfermagem" devolvem `conselho_profissional`.
- `test_esfera_de_precedencia_conselho_vence_estadual` — nome com "Conselho Regional" e "do Estado" junto
  devolve `conselho_profissional`.
- `test_esfera_de_precedencia_municipal_vence_estadual` — "IPREJUN - Instituto de Previdencia do Municipio de
  Jundiai - SP" devolve `municipal`.
- `test_esfera_de_ignora_acento_e_caixa` — "prefeitura de ijuí - rs" devolve `municipal`.
- `test_esfera_de_desconhecido` — "APS - Associacao das Pioneiras Sociais", `None` e `""` devolvem `None`.

## Fora do escopo

- Decidir o que a esfera libera. Isso e da elegibilidade, noutro ticket.
- Buscar a esfera em fonte externa (CNPJ, API de orgaos). Classificacao e por nome, deterministica.
- Esfera de lotacao multipla (concurso nacional com vagas em varias UFs). O campo `regiao` da fonte ja
  cobre isso na elegibilidade.
- Mexer em `src/utils/text.py`. Importe `normalizar_nome` de la; nao edite o arquivo.

## Notas do arquiteto

- **M+ e nao P:** nao e uma lista de palavras, e uma classificacao com casos que se cruzam. Os tres pares da
  precedencia sao reais e vieram da resposta do servidor: "Associacao das Pioneiras Sociais" (servico social
  autonomo, que fica `None` de proposito) e o quarto caso que mostra o limite. Sinal `+` pelos cruzamentos.
- **`APS` fica `None` de proposito.** Pelo fail-open do `kanban/REGRAS.md`, esfera desconhecida nao isenta do
  corte, mas tambem nao condena: a elegibilidade decide pelo teto, que no caso da APS e R$ 14.972,56 e passa.
  Nao invente uma esfera para ela.
- O "DF no sufixo decide distrital" vale **so quando nada mais decide**. "TRF1 - Tribunal Regional Federal da
  1a Regiao - DF" e `federal`, porque o padrao de tribunal federal vem antes na precedencia.
- As fixtures em `tests/fixtures/pci_mcp/` sao resposta crua do servidor MCP. O caminho ate o nome de um orgao
  dentro delas e `result.content[0].text` (JSON em string), depois `data[].titulo` mais `data[].uf`.

## Histórico
- 2026-11-23 11:16 backlog → pronto · liberado: OK do Lucas em 23/11/2026
- 2026-11-23 11:16 pronto → fazendo · implementador · glm M+ high
- 2026-11-23 11:26 fazendo → entregue · implementador: ENTREGUE · relatório T-002-implementador-1.md · 11 min
