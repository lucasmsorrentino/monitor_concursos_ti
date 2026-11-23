---
id: T-003
titulo: Elegibilidade: a decisao de silencio, pura
tipo: codigo
nivel: G-
status: backlog
repo: principal
spec: [SPEC-001, R-02]
depende_de: []
toca: [src/core/elegibilidade.py, tests/test_elegibilidade.py]
recursos: []
afinidade:
retornos: 0
---
# T-003 · Elegibilidade: a decisao de silencio, pura

## Contexto

Hoje o bot notifica todo concurso que ele considera ativo. Em 22/11/2026 isso eram 108 concursos de TI no PCI,
**79 fora do Sul**, 44 deles com teto abaixo de R$ 10.000: metade do que chega no Telegram e vaga que o Lucas
nao faria.

Este ticket entrega a **elegibilidade** (`GLOSSARIO.md`): a decisao do bot sobre notificar ou nao, com o
motivo. E uma funcao pura sobre valores primitivos, fora do bot, e e o **contrato** que a fiacao e os testes
dos outros tickets consomem. Quem a chama monta a entrada; ela so decide.

O contrato esta na SPEC-001 secao 3.4 e as nove regras na secao 4.2. A decisao de desenho e o porque de cada
isencao estao em `docs/adr/0002-elegibilidade-pelo-teto-do-concurso.md`.

## Critério de aceite

- [ ] `src/core/elegibilidade.py` expoe, exatamente como a SPEC-001 secao 3.4 declara, os dataclasses
      congelados `Candidato`, `Politica` e `Decisao`, e a funcao `decidir(c: Candidato, p: Politica) ->
      Decisao`. Os nomes dos campos e os padroes de `Politica` sao os da spec, sem renomear.
- [ ] As nove regras da SPEC-001 secao 4.2 valem, **a primeira que casa vence**, e cada uma devolve o `motivo`
      que a tabela manda. O conjunto de motivos e fechado: `seguindo`, `filtro_desligado`, `nao_verificado`,
      `sul`, `federal`, `abaixo_do_corte`, `municipal_inflado`, `sem_evidencia`, `acima_do_corte`.
- [ ] So duas regras devolvem `entra=False`: `abaixo_do_corte` (regra 5) e `municipal_inflado` (regra 6).
      Todas as outras devolvem `entra=True`.
- [ ] `selo` e `"⚠️ salario nao verificado"` nas regras 2 (`nao_verificado`) e 7 (`sem_evidencia`), e `None`
      em todas as outras.
- [ ] `Politica.modo` aceita `"desligado"` e `"ativo"`. **Qualquer outro valor se comporta como
      `"desligado"`** (fail-open do `kanban/REGRAS.md`: config invalida cai no modo conservador, nunca no
      agressivo) e a regra 1 dispara.
- [ ] Um modulo expoe tambem a constante do selo, para a fiacao e os testes nao repetirem o literal.
- [ ] Comparacao de UF e de esfera insensivel a caixa: `uf="pr"` casa `ufs_sem_corte=("PR",...)`.
- [ ] `regiao` casa `"SUL"` sem depender de caixa nem de acento. `regiao="NACIONAL"` **nao** e Sul.
- [ ] Modulo sem dependencia externa e sem importar nada de `src/core/bot.py`, `src/database/` nem
      `src/scrapers/`: ele nao conhece quem o usa.

## Plano de testes

Costura: `elegibilidade.decidir`, a propria funcao publica. Pega as nove regras, a precedencia entre elas e o
selo. Nao pega de onde vieram `teto`, `esfera` e `regiao` (isso e dos outros tickets), nem o que o bot faz com
a `Decisao`.

Oráculo: a tabela da SPEC-001 secao 4.2, transcrita a mao como tabela de casos no teste. Cada caso diz qual
regra deve disparar e por que. O esperado nao sai de chamada ao codigo.

Testes que nascem vermelhos em `tests/test_elegibilidade.py`:

- `test_seguindo_entra_mesmo_abaixo_do_corte` — `seguindo=True` com teto R$ 3.000 fora do Sul devolve
  `entra=True, motivo="seguindo"`. A estrela do Lucas nunca se contorna.
- `test_modo_desligado_deixa_tudo_entrar` — `modo="desligado"` com o candidato mais filtravel possivel devolve
  `motivo="filtro_desligado"`.
- `test_modo_invalido_se_comporta_como_desligado` — `modo="ativo "`, `modo="sombra"` e `modo=""` devolvem
  `motivo="filtro_desligado"`.
- `test_uf_e_regiao_desconhecidas_entram_com_selo` — `uf=None, regiao=None` devolve
  `entra=True, motivo="nao_verificado"` e o selo preenchido, mesmo com teto R$ 2.000.
- `test_uf_do_sul_entra_sem_olhar_teto` — `uf="PR"`, `"SC"` e `"RS"` com teto R$ 2.000 devolvem
  `motivo="sul"`.
- `test_regiao_sul_entra_quando_uf_e_none` — `uf=None, regiao="SUL"` devolve `motivo="sul"`.
- `test_federal_entra_mesmo_abaixo_do_corte` — `uf="MS", esfera="federal", teto=5215.39` devolve
  `entra=True, motivo="federal"`. E a UFMS da fixture.
- `test_nacional_nao_e_sul` — `uf=None, regiao="NACIONAL", esfera="federal"` devolve `motivo="federal"`, nao
  `"sul"`.
- `test_abaixo_do_corte_e_filtrado` — `uf="MG", esfera="municipal", teto=8628.87`, corte 10000, devolve
  `entra=False, motivo="abaixo_do_corte"`.
- `test_teto_exatamente_no_corte_entra` — `teto=10000.0` com corte `10000.0` devolve `entra=True`: a regra 5
  e `teto < corte`, estritamente. Prefeitura de Luislandia (teto R$ 10.000) entra.
- `test_municipal_inflado_e_filtrado` — `uf="SP", esfera="municipal", teto=18540.71, cargos_total=86`,
  limite 10, devolve `entra=False, motivo="municipal_inflado"`. E Guaratingueta da medida de 22/11/2026.
- `test_municipal_com_poucos_cargos_entra` — mesmo caso com `cargos_total=4` devolve
  `entra=True, motivo="acima_do_corte"`.
- `test_cargos_total_no_limite_entra` — `cargos_total=10` com limite 10 devolve `entra=True`: a regra 6 e
  `cargos_total > limite`, estritamente.
- `test_inflado_nao_se_aplica_fora_do_municipal` — `esfera="estadual", cargos_total=80, teto=12937.29`
  (a SECITECI da fixture) devolve `entra=True, motivo="acima_do_corte"`.
- `test_sul_vence_municipal_inflado` — `uf="SC", esfera="municipal", cargos_total=55` devolve `motivo="sul"`.
  E a Prefeitura de Ararangua da fixture: concurso do Sul nunca se filtra.
- `test_federal_vence_abaixo_do_corte` — ordem das regras 4 e 5.
- `test_teto_desconhecido_entra_com_selo` — `teto=None` fora do Sul, esfera `estadual`, devolve
  `entra=True, motivo="sem_evidencia"` e o selo.
- `test_teto_desconhecido_em_municipal_inflado_e_filtrado` — `teto=None, esfera="municipal",
  cargos_total=50`: a regra 6 nao precisa do teto, entao devolve `entra=False,
  motivo="municipal_inflado"`.
- `test_cargos_total_none_nao_infla` — `cargos_total=None` com esfera `municipal` e teto acima do corte
  devolve `entra=True`.
- `test_uf_minuscula_casa_o_sul` — `uf="pr"` devolve `motivo="sul"`.
- `test_motivo_sempre_do_conjunto_fechado` — varre uma matriz de candidatos e afirma que todo `motivo`
  devolvido pertence ao conjunto dos nove.

## Fora do escopo

- Ler o banco, chamar o MCP, montar mensagem de Telegram ou decidir se o concurso e novo. A funcao recebe
  primitivos e devolve uma `Decisao`.
- Parsear o teto (T-001) ou classificar a esfera (T-002). Aqui eles chegam prontos.
- Gravar a decisao. Quem grava e a fiacao, noutro ticket.
- Modo sombra. Decidido fora do escopo em 22/11/2026: `modo` tem dois valores.

## Notas do arquiteto

- **G− porque e o contrato e porque o erro aqui e silencio.** Tres outros tickets consomem estes tipos, e um
  erro de precedencia nao quebra teste nenhum: ele simplesmente deixa de mandar um concurso, e isso so
  aparece semanas depois. As nove regras com precedencia sao regra de dominio densa.
- **As duas regras de recusa e o unico jeito de recusar.** Se durante a implementacao parecer que falta uma
  terceira forma de filtrar, nao a invente: volte com `BLOQUEADO`. A spec e a ADR-0002 foram escritas com os
  numeros medidos, e a lista de recusas e deliberadamente curta.
- Repare que as regras 5, 6 e 7 **nao sao exclusivas em evidencia**: cada uma so dispara se tiver o campo de
  que precisa. Por isso a regra 6 pode disparar com `teto=None`, e e proposital: "municipal inflado" nao fala
  de valor, fala de o teto nao dizer nada sobre o cargo da area.
- O literal do selo tem emoji. O repo ja manda emoji no Telegram (`src/core/bot.py`), entao nao ha problema de
  encoding, mas defina-o como constante no modulo e importe-a nos testes, em vez de repetir a string.
- Use `tuple` nos campos de colecao da `Politica`, como a spec declara: `dataclass(frozen=True)` com `list`
  nao e hashavel e convida a mutacao acidental.
