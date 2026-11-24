ENTREGUE
Esteira: implementador · glm (zai-coding-plan/glm-5.3) · nível M+ · esforço high · 2026-11-23 17:53 → 2026-11-23 18:09 (16 min)
Resumo: Segunda volta. As 6 exigências do parecer eram de cobertura de teste: acrescentei 49 casos a
`tests/test_esfera.py` (precedença de fato, distrital e fallback DF, municipais e exceção da Camara
Legislativa, federais com estatais e exceção do MP, estaduais faltantes, siglas de conselho), na mesma
costura `esfera_de`. Nenhuma linha de `src/utils/esfera.py` mudou. Reproduzi as 7 mutações do parecer:
todas mortas agora.
Arquivos: `tests/test_esfera.py` (dentro do `toca`). Fora do `toca`: nenhum commitado.
Commits: `906faf2` test: precedencia entre esferas, padroes de cada esfera, excecoes e fallback DF na tabela do oraculo
Testes: `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q -rs` → base `420f316` 320 passed / 0 failed (numero do parecer do revisor, medido nesse mesmo commit; nao medi de novo) · ponta `906faf2` 369 passed / 0 failed (0 pulados). Lint: nao configurado no repo.
Testes que nascem verdes: os 49 novos, todos. O parecer reprova a suite por falta de cobertura, nao o codigo (o proprio revisor atestou os padroes e a precedencia corretos em `src/utils/esfera.py`); guardas contra mutacoes nascem verdes por natureza. O valor deles esta provado por mutacao, abaixo.

## Exigencias do parecer, uma a uma

1. **Precedencia real entre esferas** — `tests/test_esfera.py`, `test_esfera_de_precedencia_entre_esferas`
   (parametrizado com 9 pares, ids por degrau): nomes que ativam simultaneamente dois predicados.
   `conselho_vence_municipal`, `conselho_vence_federal`, `conselho_vence_estadual`,
   `municipal_vence_federal`, `municipal_vence_distrital`, `municipal_vence_estadual`,
   `federal_vence_estadual`, `distrital_vence_estadual` (este com
   `"Secretaria de Estado de Saude do Distrito Federal - DF"` → `distrital`, exemplo do parecer) e
   `federal_vence_sufixo_df` (`"TRF1 - Tribunal Regional Federal da 1a Regiao - DF"` → `federal`).
   Os nomes sao construidos para o teste (o orgao real raramente junta dois padroes), declarado na
   docstring do modulo de testes; o esperado vem da ordem declarada no aceite, nao do codigo.
2. **Distrital e fallback de UF DF** — `test_esfera_de_distrital_pelo_padrao_distrital`
   (`"Policia Penal Distrital"`, `"Camara Legislativa Distrital"`, sem "do Distrito Federal" e sem
   sufixo) e `test_esfera_de_distrital_pela_uf_df_quando_nada_decide`
   (`"SLU - Servico de Limpeza Urbana - DF"`, `"CAAC - Companhia de Aguas - DF"`).
3. **Padroes municipais e excecao** — `test_esfera_de_municipal_padroes_do_aceite`:
   `"SEMSA - Secretaria Municipal de Saude de Nova Lima - MG"`, `"Fundo Municipal de Saude de Cascavel - PR"`,
   `"Municipio de Nova Trento - SC"` (sem "Instituto de Previdencia") e
   `"Instituto de Previdencia do Municipio - SP"` (sem a substring "municipio de").
   `test_esfera_de_camara_legislativa_nao_e_municipal`: `"CLDF - Camara Legislativa do Distrito Federal - DF"`
   → `distrital`.
4. **Padroes federais, estatais e excecao de MP** — `test_esfera_de_federal_tribunais_policia_e_justica`
   (TRE-SC, DPF, DPRF, JFSC); `test_esfera_de_federal_estatais` com as 10 do aceite (Correios, Dataprev,
   Transpetro, Petrobras, Caixa Economica Federal, Banco do Brasil, Serpro, Embrapa, Infraero, Conab);
   `test_esfera_de_ministerio_publico_estadual_e_estadual` (`"MPSC - Ministerio Publico do Estado de
   Santa Catarina - SC"` → `estadual`) e `test_esfera_de_ministerio_publico_da_uniao_nao_decide`
   (`"MPU - Ministerio Publico da Uniao"` → `None`).
5. **Padroes estaduais faltantes** — `test_esfera_de_estadual_padroes_do_aceite`: Universidade Estadual
   (UEPG), Tribunal de Justica (TJSC), Policia Militar (PMSC), Defensoria Publica do Estado (DPSC),
   Assembleia Legislativa (ALESC), Instituto do Meio Ambiente do Estado (IMA-SC, exemplo do parecer) e
   Companhia do Estado (`"CODES - Companhia do Estado de Sergipe - SE"`). "Ministerio Publico do Estado"
   coberto no teste da excecao de MP (item 4).
6. **Siglas de conselho profissional** — `test_esfera_de_conselho_pela_sigla`: as 8 decidindo sozinhas,
   sem "Conselho Regional"/"Conselho Federal" no nome (`"CRM - RS"`, `"CRO - SP"`, `"CREA - PR"`,
   `"CRC - MG"`, `"CRP/06 - SP"`, `"CRA - RS"`, `"COREN - RS"`,
   `"OAB - Ordem dos Advogados do Brasil - SP"`).

## Prova por mutacao (as 7 sobreviventes do parecer, reproduzidas sobre `906faf2`)

Comando por mutacao: editar `src/utils/esfera.py`, `"C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest tests/test_esfera.py -q`, restaurar com `git checkout -- src/utils/esfera.py` (worktree limpo ao final, verificado com `git status --short` vazio):

| Mutacao do parecer | Resultado agora |
|---|---|
| 7a precedencia invertida (`estadual > ... > conselho`) | 8 failed, 65 passed — MORTA |
| 5a remover `"distrital"` + fallback `UF == "DF"` virar `if False:` | 4 failed, 69 passed — MORTA |
| 2a remover `municipio de`/`secretaria municipal`/`fundo municipal` + excecao Camara Legislativa | 7 failed, 66 passed — MORTA |
| 2b remover `instituto de previdencia do municipio` mantendo `municipio de` | 1 failed, 72 passed — MORTA |
| 3a remover 5 padroes federais + 10 estatais + excecao `ministerio publico` | 17 failed, 56 passed — MORTA |
| 4a remover 8 padroes estaduais | 8 failed, 65 passed — MORTA |
| 6a remover as 8 siglas de conselho | 8 failed, 65 passed — MORTA |

As mutacoes 8 e 9 (None/`""` e `normalizar_nome`) ja morriam na suite anterior, segundo o parecer, e seguem mortas.

## Mesmo padro no repo inteiro

Busca: `grep "esfera_de|conselho_profissional" --include "*.py"` em todo o repo → 52 ocorrencias, todas em
`tests/test_esfera.py` (44) e `src/utils/esfera.py` (8, o modulo e seus comentarios). Nao ha outra copia da
classificacao nem consumidor sem teste: a lacuna de cobertura existia so em `tests/test_esfera.py`.

## Docs

Nao ha commit `docs:` nesta volta: nenhum comportamento ou contrato mudou (so teste), e a documentacao do
modulo (`420f316`) continua correta. E o caso "se nao ha o que documentar, diga isso no relatorio".

Desvios e riscos: Nenhum codigo de producao mudou (`git diff 420f316..906faf2` toca so `tests/test_esfera.py`, +191).
Os dois testes antigos de precedencia que o revisor apontou como "nao ativam dois predicados"
(`test_esfera_de_precedencia_conselho_vence_estadual` e `test_esfera_de_precedencia_municipal_vence_estadual`)
ficaram: a esteira proibe apagar teste existente e eles nao estao errados, so fracos; os 9 pares novos
cobrem a exigencia de fato. `"CODES - Companhia do Estado de Sergipe - SE"` e nome construido (o orgao pode
nao existir): o oraculo e a regra do aceite ("Companhia/Banco do Estado"), nao a existencia do orgao; se o
revisor preferir nome real, e troca de uma linha. Push nao feito (regra do projeto: trabalho em commit local).
Pendencias: As mesmas do parecer, que sao do arquiteto, nao do implementador: decidir casamento nao contiguo
de "companhia" + "do estado" (CETESB segue `None` — fail-open) e ampliar a lista fechada (STJ, TSE, MPU, DETRAN).
