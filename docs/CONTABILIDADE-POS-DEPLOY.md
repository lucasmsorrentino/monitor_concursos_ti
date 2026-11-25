# Contabilidade pós-deploy — rechave de `fonte` e conciliação log × banco

> **Resposta em uma frase:** a porta do servidor MCP reescreveu a coluna `fonte` de **59** linhas
> pré-existentes (e não 30 — o saldo líquido de −30 nas portas antigas escondia +29 inserções novas
> da porta `pci` em `EDUCACAO` e `SOCIOLOGIA_ARTES`), nenhuma linha foi apagada do banco
> (`1629 + 71 = 1700`), a rechave de `fonte` em si é **desejada**, mas a rodada expôs um **defeito
> real de identidade**: **4** linhas pré-existentes (`id`s `563`, `1131`, `1445` e `1587`) sofreram
> colisão de editais distintos do mesmo órgão sob o mesmo `id` (mais **2** pares duvidosos, `930` e
> `1113`, para julgamento humano).

**Condição da medição:** banco de produção `~/monitor_concursos_ti/data/concursos.db` no notebook
(`100.98.50.59`), aberto somente leitura (`file:...?mode=ro`). Medição original em `2026-11-24
23:55–00:02 -0300` (`2026-11-25 02:55–03:02 UTC`); **re-verificação independente em `2026-11-25
00:31–00:44 -0300`** (`03:31–03:44 UTC`), com os mesmos números: `COUNT(*) = 1700`, `MIN(id) = 1`,
`MAX(id) = 1712`, nenhuma linha além de `id=1712`, `COUNT(id <= 1641) = 1629`, `59` linhas
pré-existentes com `fonte = 'pci_mcp'` e as quatro fontes nas contagens do retrato das `12:50`
(`gran=180`, `pci=1411`, `pci_mcp=101`, `pci_nacional=8`). Às `00:31`, o arquivo ainda tinha `mtime`
de `24/11 12:49` e `MAX(ultima_atualizacao) = '2026-11-24 15:49:58'` (UTC, equivalente a `12:49:58`
hora local): nenhuma escrita desde a rodada do deploy. A rodada do cron das `00:20` de `25/11` (em
execução durante a re-verificação) escreveu às `00:37` refrescos dela mesma e não alterou contagem
nenhuma até a última consulta, às `00:44`: as contagens deste documento usam as janelas estáveis de
`id` (`<= 1641` e `1642..1712`), imunes a linhas e refrescos novos.

**Fontes primárias consultadas:**
- Retrato anterior: `~/diagnostico-monitor-antes-2026-11-24.txt` (`2026-11-24 12:14:29 -0300`, 1629 linhas).
- Retrato posterior: `~/diagnostico-monitor-depois-2026-11-24.txt` (`2026-11-24 12:50:48 -0300`, 1700 linhas).
- Log do dia: `~/monitor_concursos_ti/logs/run_20261124.log` (1163 linhas; rodada da madrugada `00:20–00:32` e rodada real pós-deploy `12:24–12:49`).
- Log de ensaio `--dry-run`: `~/monitor_concursos_ti/logs/bot_concursos.log` (`12:17–12:23`).
- Logs históricos de criação: `~/monitor_concursos_ti/logs/run_20260815.log` a `run_20261123.log`.
- Código e decisões: `src/database/manager.py`, `src/core/bot.py`, `src/scrapers/pci_mcp_scraper.py`, `docs/adr/0001-mcp-como-unica-porta-do-pci.md` e `docs/specs/SPEC-001-pci-mcp-e-elegibilidade.md`.

---

## 1. Decomposição de 1629 para 1700 — nenhuma linha foi apagada

Consulta de integridade e fronteira de `id` (chave `INTEGER PRIMARY KEY AUTOINCREMENT`):

```sql
SELECT name, seq FROM sqlite_sequence;
-- editais | 1712

SELECT COUNT(*) AS n, MIN(id) AS min_id, MAX(id) AS max_id FROM editais;
-- 1700 | 1 | 1712

SELECT COUNT(*) FROM editais WHERE id <= 1641;  -- 1629
SELECT COUNT(*) FROM editais WHERE id >  1641;  --   71
```

As 12 lacunas de `id` entre `1` e `1712` são todas históricas e anteriores ao deploy
(`18, 29, 31, 44, 49, 70, 82, 100, 101, 102, 103, 104`). Entre `1642` e `1712` não há nenhuma
lacuna, e o log `run_20261124.log` registra **0** fusões (`Fundido id=`). Logo, **nenhuma linha foi
apagada** na rodada de 24/11: todas as 1629 linhas das 12:14 continuam presentes em `id <= 1641`.

Decomposição aditiva das **71** linhas inseridas entre 12:14 e 12:50 (`id 1642..1712`):

```sql
SELECT area, fonte, elegibilidade, motivo_filtro, COUNT(*) AS n
  FROM editais
 WHERE id > 1641
 GROUP BY area, fonte, elegibilidade, motivo_filtro
 ORDER BY area, fonte, elegibilidade, motivo_filtro;
```

| Área | `fonte` | `elegibilidade` (`motivo_filtro`) | Linhas novas | Faixa de `id` |
| :--- | :--- | :--- | ---: | :--- |
| `TI` | `pci_mcp` | `elegivel` (`sul`) | 17 | `1648..1681` |
| `TI` | `pci_mcp` | `elegivel` (`federal`) | 4 | `1665..1678` |
| `TI` | `pci_mcp` | `elegivel` (`acima_do_corte`) | 3 | `1650..1679` |
| `TI` | `pci_mcp` | `filtrado` (`abaixo_do_corte`) | 12 | `1644..1683` |
| `TI` | `pci_mcp` | `filtrado` (`municipal_inflado`) | 6 | `1642..1649` |
| `EDUCACAO` | `pci` | `NULL` (17 `[NOVO]` + 1 `[NOVO+INATIVO]`, `id=1686`) | 18 | `1684..1701` |
| `SOCIOLOGIA_ARTES` | `pci` | `NULL` (10 `[NOVO]` + 1 `[NOVO+INATIVO]`, `id=1703`) | 11 | `1702..1712` |
| **Total novo** | | | **71** | `1642..1712` |

Conta sem subtração: **`1629` (pré-deploy, `id <= 1641`) + `42` (`TI`) + `18` (`EDUCACAO`) + `11` (`SOCIOLOGIA_ARTES`) = `1700`**.

---

## 2. Por que foram 59 rechaveadas e não 30

Consulta das linhas pré-existentes (`id <= 1641`) cuja coluna `fonte` agora é `'pci_mcp'`:

```sql
SELECT area, fonte, COUNT(*) AS n
  FROM editais
 WHERE id <= 1641
 GROUP BY area, fonte
 ORDER BY area, fonte;
```

Resultado para `id <= 1641`:
- `EDUCACAO`: `gran=71`, `pci=854` (total 925 — igual ao retrato de antes)
- `SOCIOLOGIA_ARTES`: `gran=2`, `pci=381` (total 383 — igual ao retrato de antes)
- `TI`: `gran=107`, `pci=147`, `pci_nacional=8`, **`pci_mcp=59`** (total 321 — igual ao retrato de antes)

O número **não fecha em 30 — fecha em 59** — porque os totais por `fonte` do diagnóstico são
**globais** (somando as três áreas):

| `fonte` | Antes (12:14) | Inseridas na rodada (`id > 1641`) | Rechaveadas para `pci_mcp` (`id <= 1641`) | Depois (12:50) | Delta líquido |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `pci` | 1439 | +29 (`18 EDUCACAO` + `11 SOCIOLOGIA_ARTES`) | −57 (`TI`) | 1411 | −28 |
| `gran` | 181 | 0 | −1 (`TI`, `id=1128`) | 180 | −1 |
| `pci_nacional` | 9 | 0 | −1 (`TI`, `id=1446`) | 8 | −1 |
| `pci_mcp` | 0 | +42 (`TI`) | +59 (`TI`) | 101 | +101 |
| **Total** | **1629** | **+71** | **0** | **1700** | **+71** |

Assim:
- As `101` linhas de `pci_mcp` são **`59` rechaveadas (`id <= 1641`) + `42` inéditas (`id 1642..1683`)**.
- O delta aparente de `−30` nas portas antigas é o saldo líquido de `−59` linhas rechaveadas em `TI`
  compensadas por `+29` linhas novas da porta `pci` em `EDUCACAO` e `SOCIOLOGIA_ARTES`.

**Origem exata das 2 rechaveadas que não vieram de `pci`:**
- **`gran → pci_mcp` (`id=1128`, Prefeitura de Serra Grande - PB):** criada por `pci` em `22/10/2026`
  (`run_20261022.log:L249`), mas na rodada da madrugada de `24/11` (`run_20261124.log:L54–55`, `00:22:23`),
  o Gran casou a linha por entidade (`'Concurso Prefeitura de Serra Grande (PB)' = 'Prefeitura de Serra Grande - PB'`)
  e sobrescreveu `nome` e `fonte='gran'`. Como o concurso já havia saído das páginas de cargo do PCI às `00:24`,
  ele chegou ao retrato das `12:14` com `fonte='gran'` e `nome='Concurso Prefeitura de Serra Grande (PB)'`
  (confirmado no `--dry-run` das `12:18:29`, em que o Gran casou por nome exato sem `Casou por entidade`;
  o salvamento da madrugada foi silencioso — refresh sem transição grava sem logar linha, e entre o
  `Casou por entidade` das `00:22` e o ensaio das `12:18` nada mais tocou a linha).
  Às `12:31:26`, a porta do MCP casou `id=1128` por `pci_id=296050` (preservado via `COALESCE`) e gravou
  `fonte='pci_mcp'`.
- **`pci_nacional → pci_mcp` (`id=1446`, Ministério da Saúde):** duas das 59 linhas foram originalmente
  criadas por `pci_nacional`: `id=1446` (`run_20261113.log:L150`, `SAA MS - Subsecretaria de Assuntos
  Administrativos do Ministério da Saúde`) e `id=1467` (`run_20261114.log:L150`, `APS - Associação das
  Pioneiras Sociais`). Como `pci_nacional` caiu apenas de 9 para 8 (`−1`), uma delas já havia sido
  rechaveada para `pci` antes das 12:14 (a evidência aponta `id=1467`, cujo cargo é analista de TI e
  que partiu de `Edital publicado`, típico da porta de cargos, enquanto `id=1446` já estava em
  `inscricoes_abertas` e passou em refresh silencioso). Nos logs de 15–23/11 não há linha alguma
  para `Pioneiras`: refresh sem mudança grava sem logar evento, então o toque que regravou `id=1467`
  não deixou rastro — a atribuição acima é inferência e segue marcada como tal.

### Lista completa das 59 linhas rechaveadas (`id <= 1641 AND fonte = 'pci_mcp'`)

Consulta:

```sql
SELECT id, pci_id, elegibilidade, motivo_filtro, nome, link
  FROM editais
 WHERE id <= 1641 AND fonte = 'pci_mcp'
 ORDER BY id;
```

| `id` | `fonte` antes (12:14) | `fonte` agora | `pci_id` | Elegibilidade | Nome atual (e link) | Situação do casamento |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 395 | `pci` | `pci_mcp` | `294444` | `filtrado` (`municipal_inflado`) | Prefeitura de Contagem - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-contagem-mg-retifica-edital-de-concurso-publico)) | Mesmo concurso |
| 553 | `pci` | `pci_mcp` | `294732` | `filtrado` (`abaixo_do_corte`) | Câmara de Unaí - MG ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-unai-mg-abre-concurso-publico-com-remuneracao-de-9193)) | Mesmo concurso |
| 555 | `pci` | `pci_mcp` | `294784` | `elegivel` (`acima_do_corte`) | SETEC - Serviços Técnicos Gerais de Campinas - SP ([notícia](https://www.pciconcursos.com.br/noticias/setec-campinas-sp-abre-concurso-publico-com-salarios-de-ate-10428)) | Mesmo concurso |
| 559 | `pci` | `pci_mcp` | `294812` | `filtrado` (`municipal_inflado`) | Prefeitura de Moreilândia - PE ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-moreilandia-pe-retifica-dois-concursos-publicos)) | Mesmo concurso |
| 563 | `pci` | `pci_mcp` | `296897` | `filtrado` (`abaixo_do_corte`) | Unesp - Universidade Estadual Paulista - SP ([notícia](https://www.pciconcursos.com.br/noticias/unesp-sp-abre-concursos-para-professor-substituto-em-aracatuba)) | **COLISÃO (edital de nov/2026 em linha de set/2026)** |
| 821 | `pci` | `pci_mcp` | `295546` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Santa Luzia - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-santa-luzia-mg-abre-concurso-publico-com-salarios-de-ate-8628)) | Mesmo concurso |
| 824 | `pci` | `pci_mcp` | `295448` | `filtrado` (`municipal_inflado`) | Prefeitura de Patis - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-patis-mg-abre-concurso-publico-com-salarios-de-ate-13500)) | Mesmo concurso |
| 831 | `pci` | `pci_mcp` | `295601` | `filtrado` (`municipal_inflado`) | Prefeitura de Luislândia - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-luislandia-mg-abre-concurso-publico-com-vagas-em-diversas-areas)) | Mesmo concurso |
| 930 | `pci` | `pci_mcp` | `296153` | `elegivel` (`federal`) | UNIFEI - Universidade Federal de Itajubá - MG ([notícia](https://www.pciconcursos.com.br/noticias/unifei-mg-abre-concurso-publico-para-professores-do-magisterio-superior)) | **DUVIDOSO** (ver seção 3) |
| 1061 | `pci` | `pci_mcp` | `295908` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Ribeirãozinho do Maranhão - MA ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-ribeiraozinho-do-maranhao-ma-publica-editais-de-concurso-e-processo-seletivo)) | Mesmo concurso |
| 1113 | `pci` | `pci_mcp` | `294463` | `filtrado` (`abaixo_do_corte`) | UERJ - Universidade do Estado do Rio de Janeiro - RJ ([notícia](https://www.pciconcursos.com.br/noticias/uerj-abre-concurso-publico-para-professor-adjunto-de-ciencia-da-computacao)) | **DUVIDOSO** (ver seção 3) |
| 1115 | `pci` | `pci_mcp` | `296029` | `filtrado` (`municipal_inflado`) | Prefeitura de Canto do Buriti - PI ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-canto-do-buriti-pi-retifica-edital-de-concurso-publico)) | Mesmo concurso |
| 1125 | `pci` | `pci_mcp` | `296057` | `filtrado` (`municipal_inflado`) | Prefeitura de Birigui - SP ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-birigui-sp-abre-concurso-publico-com-salarios-de-ate-13881)) | Mesmo concurso |
| 1128 | `gran` | `pci_mcp` | `296050` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Serra Grande - PB ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-serra-grande-pb-retifica-concurso-publico-com-vagas-para-diversos-cargos)) | Mesmo concurso (era `gran` às 12:14) |
| 1131 | `pci` | `pci_mcp` | `296044` | `elegivel` (`federal`) | IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo - SP ([notícia](https://www.pciconcursos.com.br/noticias/ifsp-sp-abre-processo-seletivo-para-professor-substituto-com-salarios-de-ate-8340)) | **COLISÃO (2 editais do IFSP na mesma rodada)** |
| 1159 | `pci` | `pci_mcp` | `296084` | `elegivel` (`sul`) | TRT 4 - Tribunal Regional do Trabalho da 4ª Região - RS ([notícia](https://www.pciconcursos.com.br/noticias/trt4-rs-abre-concurso-publico-para-analistas-e-tecnicos-judiciarios)) | Mesmo concurso (`TRT4` → `TRT 4`) |
| 1171 | `pci` | `pci_mcp` | `296112` | `elegivel` (`sul`) | Prefeitura de Novo Xingu - RS ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-novo-xingu-rs-abre-concurso-publico-com-salarios-de-ate-8797)) | Mesmo concurso |
| 1172 | `pci` | `pci_mcp` | `296125` | `elegivel` (`sul`) | Prefeitura de Ijuí - RS ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-ijui-rs-retifica-edital-de-concurso-publico)) | Mesmo concurso |
| 1193 | `pci` | `pci_mcp` | `296158` | `elegivel` (`acima_do_corte`) | DPDF - Defensoria Pública do Distrito Federal - DF ([notícia](https://www.pciconcursos.com.br/noticias/dpdf-abre-concurso-publico-para-analista-de-apoio-a-assistencia-judiciaria)) | Mesmo concurso |
| 1194 | `pci` | `pci_mcp` | `296174` | `filtrado` (`abaixo_do_corte`) | Câmara de Portel - PA ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-portel-pa-retifica-edital-de-concurso-publico)) | Mesmo concurso |
| 1196 | `pci` | `pci_mcp` | `296186` | `filtrado` (`municipal_inflado`) | Câmara de Cuiabá - MT ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-cuiaba-mt-abre-concurso-publico-com-salarios-de-ate-11629)) | Mesmo concurso |
| 1228 | `pci` | `pci_mcp` | `296235` | `filtrado` (`abaixo_do_corte`) | Prefeitura de São Julião - PI ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-sao-juliao-pi-suspende-concurso-publico)) | Mesmo concurso |
| 1229 | `pci` | `pci_mcp` | `296236` | `filtrado` (`municipal_inflado`) | Prefeitura de Belém do Piauí - PI ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-belem-do-piaui-pi-abre-concurso-com-remuneracoes-de-ate-12000)) | Mesmo concurso |
| 1230 | `pci` | `pci_mcp` | `296250` | `elegivel` (`sul`) | Câmara de São Francisco do Sul - SC ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-sao-francisco-do-sul-sc-retifica-edital-de-concurso-publico)) | Mesmo concurso |
| 1231 | `pci` | `pci_mcp` | `271576` | `filtrado` (`municipal_inflado`) | Prefeitura e Câmara de Faina - GO ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-e-camara-de-faina-go-reabrem-concurso-publico-com-diversas-vagas)) | Mesmo concurso (notícia antiga reaberta) |
| 1266 | `pci` | `pci_mcp` | `296287` | `elegivel` (`acima_do_corte`) | SECITECI - Secretaria de Estado de Ciência, Tecnologia e Inovação de Mato Grosso - MT ([notícia](https://www.pciconcursos.com.br/noticias/seciteci-mt-retifica-edital-de-processo-seletivo-para-formacao-de-cadastro-de-reserva)) | Mesmo concurso |
| 1267 | `pci` | `pci_mcp` | `296272` | `filtrado` (`abaixo_do_corte`) | IPAM - Instituto de Previdência e Assistência dos Servidores do Município de Porto Velho - RO ([notícia](https://www.pciconcursos.com.br/noticias/ipam-de-porto-velho-ro-abre-concurso-publico-com-salarios-de-ate-5000)) | Mesmo concurso |
| 1268 | `pci` | `pci_mcp` | `296256` | `filtrado` (`municipal_inflado`) | Prefeitura de Leme - SP ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-leme-sp-abre-concurso-publico-com-salarios-de-ate-13359)) | Mesmo concurso |
| 1285 | `pci` | `pci_mcp` | `296303` | `elegivel` (`federal`) | UFMS - Fundação Universidade Federal de Mato Grosso do Sul - MS ([notícia](https://www.pciconcursos.com.br/noticias/ufms-abre-concurso-publico-para-cargos-tecnico-administrativos-em-educacao)) | Mesmo concurso |
| 1286 | `pci` | `pci_mcp` | `296319` | `elegivel` (`sul`) | Prefeitura de Nova Trento - SC ([notícia](https://www.pciconcursos.com.br/noticias/municipio-de-nova-trento-sc-abre-tres-novos-processos-seletivos-com-salarios-de-ate-14189)) | Mesmo concurso |
| 1325 | `pci` | `pci_mcp` | `296357` | `filtrado` (`abaixo_do_corte`) | Prefeitura de São José do Divino - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-sao-jose-do-divino-mg-abre-concurso-publico-para-diversos-cargos)) | Mesmo concurso |
| 1326 | `pci` | `pci_mcp` | `296345` | `elegivel` (`sul`) | Prefeitura de Guarujá do Sul - SC ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-guaruja-do-sul-sc-abre-concurso-e-selecoes-com-salarios-de-ate-30-7-mil)) | Mesmo concurso |
| 1327 | `pci` | `pci_mcp` | `296340` | `filtrado` (`abaixo_do_corte`) | DPE - Defensoria Pública do Estado do Amazonas - AM ([notícia](https://www.pciconcursos.com.br/noticias/dpe-am-abre-concurso-publico-com-salarios-de-ate-8006)) | Mesmo concurso |
| 1349 | `pci` | `pci_mcp` | `296373` | `filtrado` (`municipal_inflado`) | Prefeitura da Estância Turística de Guaratinguetá - SP ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-guaratingueta-sp-abre-concurso-publico-com-salarios-de-ate-18540)) | Mesmo concurso |
| 1351 | `pci` | `pci_mcp` | `296395` | `elegivel` (`sul`) | IMA - Instituto do Meio Ambiente do Estado de Santa Catarina - SC ([notícia](https://www.pciconcursos.com.br/noticias/ima-sc-abre-concurso-publico-com-salarios-de-ate-12300)) | Mesmo concurso |
| 1365 | `pci` | `pci_mcp` | `296434` | `filtrado` (`municipal_inflado`) | Prefeitura de Boa Viagem - CE ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-boa-viagem-ce-abre-concurso-publico-com-vagas-para-diversas-areas-de-atuacao)) | Mesmo concurso |
| 1385 | `pci` | `pci_mcp` | `296464` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Jandira - SP ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-jandira-sp-abre-concurso-publico-com-salarios-de-ate-6812)) | Mesmo concurso |
| 1386 | `pci` | `pci_mcp` | `296457` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Anchieta - ES ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-anchieta-es-abre-concurso-publico-com-salarios-de-ate-7362)) | Mesmo concurso |
| 1387 | `pci` | `pci_mcp` | `296456` | `filtrado` (`abaixo_do_corte`) | Câmara de Petrolina - PE ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-petrolina-pe-abre-concurso-publico-com-salarios-de-ate-8561)) | Mesmo concurso |
| 1407 | `pci` | `pci_mcp` | `296500` | `filtrado` (`abaixo_do_corte`) | CIS - Companhia Ituana de Saneamento - SP ([notícia](https://www.pciconcursos.com.br/noticias/cis-itu-sp-abre-concurso-publico-com-salarios-de-ate-7553)) | Mesmo concurso |
| 1408 | `pci` | `pci_mcp` | `296536` | `elegivel` (`acima_do_corte`) | SP-Águas - Agência de Águas do Estado de São Paulo - SP ([notícia](https://www.pciconcursos.com.br/noticias/sp-aguas-sp-abre-concurso-publico-com-salarios-de-ate-12070)) | Mesmo concurso |
| 1434 | `pci` | `pci_mcp` | `296537` | `filtrado` (`abaixo_do_corte`) | CETESB - Companhia Ambiental do Estado de São Paulo - SP ([notícia](https://www.pciconcursos.com.br/noticias/cetesb-sp-abre-concursos-publicos-para-diversos-cargos)) | Mesmo concurso |
| 1443 | `pci` | `pci_mcp` | `296594` | `filtrado` (`abaixo_do_corte`) | Banestes - Banco do Estado do Espírito Santo - ES ([notícia](https://www.pciconcursos.com.br/noticias/banestes-es-abre-concurso-publico-para-cargos-de-nivel-superior)) | Mesmo concurso |
| 1444 | `pci` | `pci_mcp` | `296583` | `filtrado` (`abaixo_do_corte`) | Prefeitura do Município de Santana de Parnaíba - SP ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-santana-de-parnaiba-sp-abre-concurso-publico-com-salarios-de-ate-7497)) | Mesmo concurso |
| 1445 | `pci` | `pci_mcp` | `296735` | `filtrado` (`abaixo_do_corte`) | UNESP - Universidade Estadual Paulista "Júlio de Mesquita Filho" - SP ([notícia](https://www.pciconcursos.com.br/noticias/unesp-abre-tres-concursos-publicos-para-professores-substitutos-em-rio-claro)) | **COLISÃO (3 editais da UNESP na mesma rodada)** |
| 1446 | `pci_nacional` | `pci_mcp` | `296620` | `elegivel` (`federal`) | Ministério da Saúde ([notícia](https://www.pciconcursos.com.br/noticias/saa-ms-abre-processo-seletivo-com-salarios-de-ate-10354)) | Mesmo concurso (`SAA MS - Subsecretaria...` → `Ministério da Saúde`, mesmo link) |
| 1463 | `pci` | `pci_mcp` | `296603` | `filtrado` (`abaixo_do_corte`) | Câmara de Carapicuíba - SP ([notícia](https://www.pciconcursos.com.br/noticias/camara-de-carapicuiba-sp-abre-concurso-publico-para-oficial-de-manutencao-e-tecnico-em-tecnologia-da-informacao)) | Mesmo concurso |
| 1464 | `pci` | `pci_mcp` | `296621` | `filtrado` (`abaixo_do_corte`) | CRP/05 - Conselho Regional de Psicologia da 5ª Região - RJ ([notícia](https://www.pciconcursos.com.br/noticias/crp-05-rj-abre-concurso-publico-com-salarios-de-ate-7313)) | Mesmo concurso |
| 1465 | `pci` | `pci_mcp` | `296614` | `elegivel` (`sul`) | IFFar - Instituto Federal de Educação, Ciência e Tecnologia Farroupilha - RS ([notícia](https://www.pciconcursos.com.br/noticias/iffar-rs-abre-concurso-publico-com-vagas-para-diversas-areas)) | Mesmo concurso |
| 1467 | `pci` (criada `pci_nacional`) | `pci_mcp` | `296663` | `elegivel` (`acima_do_corte`) | APS - Associação das Pioneiras Sociais ([notícia](https://www.pciconcursos.com.br/noticias/associacao-das-pioneiras-sociais-abre-processo-seletivo-para-analista-de-tecnologia-da-informacao)) | Mesmo concurso |
| 1491 | `pci` | `pci_mcp` | `296654` | `filtrado` (`municipal_inflado`) | Prefeitura de Italva - RJ ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-italva-rj-abre-concurso-publico-com-salarios-de-ate-12132)) | Mesmo concurso |
| 1492 | `pci` | `pci_mcp` | `296657` | `filtrado` (`abaixo_do_corte`) | Prefeitura de Muqui - ES ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-muqui-es-abre-concurso-publico-com-diversas-vagas)) | Mesmo concurso |
| 1512 | `pci` | `pci_mcp` | `296678` | `elegivel` (`sul`) | Prefeitura de Araranguá - SC ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-ararangua-sc-abre-processos-seletivos-para-diferentes-areas)) | Mesmo concurso |
| 1513 | `pci` | `pci_mcp` | `296683` | `elegivel` (`federal`) | IFG - Instituto Federal de Educação, Ciência e Tecnologia de Goiás - GO ([notícia](https://www.pciconcursos.com.br/noticias/ifg-go-abre-concurso-publico-para-tecnicos-administrativos-em-educacao)) | Mesmo concurso |
| 1514 | `pci` | `pci_mcp` | `296701` | `elegivel` (`acima_do_corte`) | TCEES - Tribunal de Contas do Estado do Espírito Santo - ES ([notícia](https://www.pciconcursos.com.br/noticias/tce-es-abre-processo-seletivo-com-vagas-na-area-de-tecnologia)) | Mesmo concurso |
| 1543 | `pci` | `pci_mcp` | `296742` | `filtrado` (`abaixo_do_corte`) | SEMSA - Secretaria Municipal de Saúde de Nova Lima - MG ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-nova-lima-mg-abre-processo-seletivo-com-salarios-de-ate-8106)) | Mesmo concurso |
| 1560 | `pci` | `pci_mcp` | `296777` | `elegivel` (`acima_do_corte`) | SEAD - Secretaria de Estado da Administração - MA ([notícia](https://www.pciconcursos.com.br/noticias/sead-ma-abre-concurso-publico-com-salarios-de-ate-14950)) | Mesmo concurso |
| 1587 | `pci` | `pci_mcp` | `296823` | `elegivel` (`federal`) | IFMS - Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso do Sul - MS ([notícia](https://www.pciconcursos.com.br/noticias/ifms-ms-abre-vagas-para-professores-substitutos-no-campus-jardim)) | **COLISÃO (2 editais do IFMS na mesma rodada)** |
| 1627 | `pci` | `pci_mcp` | `296867` | `filtrado` (`municipal_inflado`) | Prefeitura de Araripina - PE ([notícia](https://www.pciconcursos.com.br/noticias/prefeitura-de-araripina-pe-abre-1099-vagas-em-processos-seletivos)) | Mesmo concurso |

---

## 3. Verificação de casamento — 4 colisões confirmadas e 2 pares duvidosos

**Nota metodológica:** o banco não guarda histórico de `link` ou `pci_id` anteriores ao `UPDATE`.
A verificação das 59 linhas cruzou: (a) nome de criação nos logs `run_*.log` contra o nome atual no
banco; (b) eventos repetidos no mesmo nome na rodada das `12:24` (`run_20261124.log:L566–761`) e no
`--dry-run` (`bot_concursos.log`, `12:20`); e (c) monotonicidade de `pci_id` em relação à data de
criação da linha (os números de notícia do PCI crescem com o tempo).

Das 59 linhas rechaveadas:
- **53** não têm indício de colisão: mesmo nome na criação e agora (com exceção de `id=1159`, que só
  ganhou espaço em `TRT4` → `TRT 4`, e `id=1446`, que mudou `SAA MS - Subsecretaria de Assuntos
  Administrativos do Ministério da Saúde` → `Ministério da Saúde` mantendo o mesmo link `saa-ms-...`),
  evento único na rodada e `pci_id` compatível com a época de criação (em `id=1231`, Faina-GO, o
  `pci_id=271576` antigo corresponde à notícia de reabertura do concurso).
- **4** têm **colisão comprovada de editais distintos** sob o mesmo `id`:
- **2** são **pares duvidosos** para julgamento do Lucas.

### 3.1. Colisões comprovadas (editais distintos do mesmo órgão sobrescrevendo o mesmo `id`)

A porta do MCP retornou **106 concursos distintos** (`run_20261124.log:L566`), mas o banco só ficou
com **101** linhas `pci_mcp`: **5** itens colidiram com linhas já tocadas na própria rodada — 4
visíveis em nível `INFO` (abaixo) e 1 invisível, porque refresh sem mudança de fase/data grava no
banco sem deixar linha de evento. A conta fecha por aritmética, medida na seção `L566–761`: `102`
eventos `INFO` (`56` `[FILTRADO]` + `25` `[NOVO]` + `21` `[TRANSICAO]`), dos quais `4` são
duplicatas sobre linhas já tocadas (`98` linhas distintas), mais `3` toques que só fizeram refresh
silencioso (`101` linhas); o `106º` item foi refresh silencioso sobre linha já tocada — a 5ª
colisão, que o log não mostra.

| `id` | Nome antes (criação) | Nome e link agora (pós-deploy) | Evidência da colisão |
| ---: | :--- | :--- | :--- |
| **`563`** | `UNESP - Universidade Estadual Paulista - SP` (`run_20260903.log:L113`, `03/09/2026`; vizinhos de criação com `pci_id` `294719..294903`, ids `560–566`) | `Unesp - Universidade Estadual Paulista - SP` · `pci_id=296897` · [Araçatuba](https://www.pciconcursos.com.br/noticias/unesp-sp-abre-concursos-para-professor-substituto-em-aracatuba) | Um edital novo de novembro/2026 (`pci_id=296897`, prazo `2026-12-14`) sobrescreveu a linha criada em 03/09/2026, cerca de 2.000 notícias depois; o toque visível foi o `[FILTRADO]` das `12:32:31` (`run_20261124.log:L672`, teto `3511.9`). |
| **`1131`** | `IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo - SP` (`run_20261022.log:L260`, `22/10/2026`) | `IFSP - Instituto Federal de Educação, Ciência e Tecnologia de São Paulo - SP` · `pci_id=296044` · [professor substituto](https://www.pciconcursos.com.br/noticias/ifsp-sp-abre-processo-seletivo-para-professor-substituto-com-salarios-de-ate-8340) | Atingida **2 vezes** na mesma rodada: `L582` (`12:27:38`, `Edital publicado → Inscrições abertas, data_mudou=True`) e `L661` (`12:31:59`, `Inscrições abertas → Inscrições abertas, data_mudou=True`). Dois editais distintos do IFSP disputaram a mesma linha. |
| **`1445`** | `UNESP - Universidade Estadual Paulista "Júlio de Mesquita Filho" - SP` (`run_20261113.log:L145`, `13/11/2026`; vizinhos `pci_id` `296583..296620`) | `UNESP - Universidade Estadual Paulista "Júlio de Mesquita Filho" - SP` · `pci_id=296735` · [Rio Claro](https://www.pciconcursos.com.br/noticias/unesp-abre-tres-concursos-publicos-para-professores-substitutos-em-rio-claro) | Atingida **3 vezes** na mesma rodada: `L614` (`12:30:00`, `[FILTRADO]`, teto `3511.9`) → `L658–660` (`12:31:58`, **`[NOVO]`**, edital **elegível** que foi notificado porque a linha acabara de ficar `filtrado`!) → `L732` (`12:37:20`, `[FILTRADO]`, teto `3511.9`, sobrescrevendo o edital elegível de volta para `filtrado`!). |
| **`1587`** | `IFMS - Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso do Sul - MS` (`run_20261121.log:L125`, `21/11/2026`) | `IFMS - Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso do Sul - MS` · `pci_id=296823` · [campus Jardim](https://www.pciconcursos.com.br/noticias/ifms-ms-abre-vagas-para-professores-substitutos-no-campus-jardim) | Atingida **2 vezes** na mesma rodada: `L708` (`12:34:59`, `Edital publicado → Inscrições abertas, data_mudou=False`) e `L714` (`12:35:29`, `Inscrições abertas → Inscrições abertas, data_mudou=True`). Dois editais distintos do IFMS disputaram a mesma linha. |

### 3.2. Lista de duvidosos para o Lucas julgar

| `id` | Nome antes (criação) | Nome e link agora (pós-deploy) | Por que é duvidoso |
| ---: | :--- | :--- | :--- |
| **`930`** | `UNIFEI - Universidade Federal de Itajubá - MG` (`run_20261014.log:L267`, `14/10/2026`; vizinhos `pci_id` `295655..295725`) | `UNIFEI - Universidade Federal de Itajubá - MG` · `pci_id=296153` · [magistério superior](https://www.pciconcursos.com.br/noticias/unifei-mg-abre-concurso-publico-para-professores-do-magisterio-superior) | `pci_id=296153` é ~430 notícias posterior à criação em `14/10` e a linha sofreu `[TRANSICAO]` com `data_mudou=True` em `L747` (`12:38:02`). Pode ser edital novo da UNIFEI sobrescrevendo o de outubro, ou notícia posterior de retificação/abertura do mesmo edital. |
| **`1113`** | `UERJ - Universidade do Estado do Rio de Janeiro - RJ` (`run_20261021.log:L1751`, `21/10/2026`; vizinhos `pci_id` `296017..296018`) | `UERJ - Universidade do Estado do Rio de Janeiro - RJ` · `pci_id=294463` · [professor adjunto CC](https://www.pciconcursos.com.br/noticias/uerj-abre-concurso-publico-para-professor-adjunto-de-ciencia-da-computacao) | `pci_id=294463` é ~1.550 notícias anterior à criação em `21/10` (prazo `2027-01-31`). Pode ser a mesma notícia antiga que só entrou nos slugs de TI em outubro, ou outro edital da UERJ com o mesmo nome. |

---

## 4. Conciliação dos 61 `[NOVO]` do log contra os +71 do banco

A discrepância aparente (`61` no log do dia × `+71` no banco entre os retratos) vem de **quatro
parcelas exatas**:

1. **Dois períodos diferentes:** o `61` do diagnóstico soma as **duas rodadas** do dia 24/11 —
   **9** `[NOVO]` na rodada da madrugada (`00:20–00:32`, código antigo, cujas linhas já estavam dentro
   das `1629` das 12:14) + **52** `[NOVO]` na rodada pós-deploy (`12:24–12:49`, entre os retratos).
2. **Filtrados inéditos salvos em silêncio em `TI` (`+18`):** dos **56** `[FILTRADO]` logados na
   rodada pós-deploy (`36 abaixo_do_corte + 20 municipal_inflado`), **18** eram concursos inéditos
   (inseriram linhas novas em `id 1642..1683`) e **38** ocorreram sobre **37** linhas pré-existentes
   (`id <= 1641`, com `id=1445` UNESP filtrada 2 vezes, em `L614` e `L732`, o que fecha exatamente as
   `18 + 37 = 55` linhas com `elegibilidade = 'filtrado'` no banco).
3. **`[NOVO+INATIVO]` salvos em silêncio nas outras áreas (`+2`):** `id=1686` em `EDUCACAO` e
   `id=1703` em `SOCIOLOGIA_ARTES` (ambos `Prefeitura de Lutécia - SP`, inscrição encerrada, que
   gravam no banco e retornam `"skip"` sem incrementar `novos_cont`).
4. **Um `[NOVO]` que não inseriu linha nova (`−1`):** `id=1445` (UNESP, `L658–660`), linha
   pré-existente que foi marcada como `filtrado` às `12:30:00` e, dois minutos depois, atingida por
   um segundo edital elegível da UNESP — disparando `inedito = True` e contando `+1` em `novos_cont`
   sem fazer `INSERT`.

| Parcela | Rodada pós-deploy (`52 → 71`) | Dia inteiro vs retrato (`61 → 71`) |
| :--- | ---: | ---: |
| `[NOVO]` contados no log | `52` (`25 TI + 17 EDU + 10 SOC`) | `61` (`9 madrugada + 52 pós-deploy`) |
| `−` `[NOVO]` da madrugada (já nas 1629 das 12:14) | `0` | `−9` |
| `−` `[NOVO]` sobre linha pré-existente (`id=1445`, UNESP) | `−1` | `−1` |
| `+` Filtrados inéditos salvos em silêncio em `TI` (`12 abaixo_do_corte + 6 municipal_inflado`) | `+18` | `+18` |
| `+` `[NOVO+INATIVO]` salvos em silêncio (`id=1686` EDU + `id=1703` SOC) | `+2` | `+2` |
| **Total de linhas novas no banco (`id 1642..1712`)** | **`71`** | **`71`** |

Consulta de conferência dos filtrados no banco:

```sql
SELECT elegibilidade, motivo_filtro,
       SUM(CASE WHEN id <= 1641 THEN 1 ELSE 0 END) AS pre_existentes,
       SUM(CASE WHEN id >  1641 THEN 1 ELSE 0 END) AS ineditas,
       COUNT(*) AS total
  FROM editais
 WHERE area = 'TI' AND elegibilidade IS NOT NULL
 GROUP BY elegibilidade, motivo_filtro
 ORDER BY elegibilidade, motivo_filtro;
-- elegivel | acima_do_corte    |  7 |  3 | 10
-- elegivel | federal           |  6 |  4 | 10
-- elegivel | sul               |  9 | 17 | 26
-- filtrado | abaixo_do_corte   | 23 | 12 | 35  (+1 repeticao no log em id=1445 = 36)
-- filtrado | municipal_inflado | 14 |  6 | 20
```

---

## 5. Veredito: rechave desejada × defeito de colisão por nome

1. **A rechave de `fonte` (`pci`/`gran`/`pci_nacional` → `pci_mcp`) é DESEJADA.**
   Pela `ADR-0001` e `SPEC-001`, o `pci_id` do MCP é a mesma chave de notícia da porta HTML, e
   `DatabaseManager.atualizar_concurso` (`src/database/manager.py:411`) atualiza
   `fonte = COALESCE(?, fonte)` preservando `id` (e os botões já enviados no Telegram). Para as 53
   linhas sem colisão, a troca de `fonte` funcionou exatamente como previsto.

2. **A colisão de editais distintos do mesmo órgão no mesmo `id` é DEFEITO — e pode esconder concurso.**
   A causa raiz está na regra de identidade em `src/database/manager.py`: a tabela impõe
   `UNIQUE(area, nome)` (linha 24) e `buscar_registro` (linhas 256–281) cai para `(area, nome)
   COLLATE NOCASE` mesmo quando o item novo já traz `pci_id` e `link` diferentes dos da linha
   existente. Para prefeituras com um edital ativo por vez isso não aparece, mas para universidades
   e institutos federais com vários editais simultâneos (UNESP, IFSP, IFMS — exatamente os órgãos
   que o corte fora do Sul preserva quando federais), um edital sobrescreve o outro na mesma linha.
   No caso extremo de `id=1445` (UNESP), um edital **elegível** foi sobrescrito 5 minutos depois
   por um edital **filtrado** da mesma universidade.

### Tickets recomendados para a fase seguinte

- **Correção estrutural de identidade (banco/dedup):** quando o candidato traz `pci_id` (ou `link`
  específico) diferente do `pci_id`/`link` já gravado na linha, não colidir por `(area, nome)` —
  permitir múltiplos editais simultâneos do mesmo órgão (revisando a restrição `UNIQUE(area, nome)`
  em migração aditiva/compatível e a ordem de busca em `buscar_registro`).
- **Casos concretos afetados nesta rodada (para verificação/reprocessamento após o conserto):**
  - `id=563` — Unesp (edital de nov/2026 `pci_id=296897` sobrescreveu linha de set/2026)
  - `id=1131` — IFSP (2 editais distintos colidiram na rodada de 24/11)
  - `id=1445` — UNESP (3 editais distintos colidiram na rodada de 24/11; 1 elegível foi sobrescrito por filtrado)
  - `id=1587` — IFMS (2 editais distintos colidiram na rodada de 24/11)
  - `id=930` — UNIFEI (duvidoso; aguarda julgamento do Lucas)
  - `id=1113` — UERJ (duvidoso; aguarda julgamento do Lucas)
