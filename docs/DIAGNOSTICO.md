# Diagnóstico da produção

Coleta a evidência dos últimos 30 dias do monitor numa saída única, para o operador rodar no notebook e colar
de volta. **Somente leitura**: não cria arquivo, não toca no banco, não manda mensagem, não roda varredura.
Sai sempre com código `0` — o diagnóstico **relata**, não julga.

## Como rodar

No notebook, dentro de `~/monitor_concursos_ti`, a partir da raiz do repo:

```bash
bash scripts/diagnostico_producao.sh
```

Funciona num Debian/Ubuntu padrão (`bash`, `grep`, `sed`, `awk`, `sort`, `uniq`, `date`; para o banco usa
`sqlite3` e, se faltar, cai no `python3` com sqlite3 da stdlib). Arquivo ou pasta que não existe produz a
linha "ausente" da seção e o script segue — nunca morre no meio.

**Segredos**: token, chave de API e `chat_id` saem sempre como `<omitido>`. O script lê
`~/concursos-secrets/monitor.env` apenas para listar **nomes** de chave e extrair a estrutura do
`MONITOR_TARGETS_JSON` — nenhum valor é impresso.

## O que cada seção significa — e o que é sinal de problema

### 1. Identidade

Data/hora, host, commit curto, branch e se a árvore do git está limpa. Contexto para interpretar o resto.

- **Sinal de problema**: árvore suja em produção (alguém editou à mão e não voltou); branch que não é a de
  produção.

### 2. Último sucesso

Conteúdo de `logs/.last_success_date` (o dia da última varredura que terminou com exit 0) e quantos dias
tem isso.

- **Sinal de problema**: mais de 2 dias — a máquina está desligada, o cron não roda, ou toda varredura está
  falhando.

### 3. Saúde por dia (últimos 30 dias)

Uma linha por dia, com o código de saída que o fim de `logs/run_AAAAMMDD.log` registra e as contagens de
`novos` e `atualizacoes` da linha "Ciclo finalizado" (somadas entre as áreas em rodada multi-área). Dia sem
arquivo aparece como `ausente`.

- **Sinal de problema**: dia faltando no meio da série (a máquina esteve desligada ou o cron morreu);
  `exit=1` ou outro código recorrente; `novos=0` e `atualizacoes=-` por muitos dias seguidos (a varredura
  roda mas nunca termina o ciclo de envio).

### 4. Erros recorrentes

As 15 mensagens de nível `ERROR`/`CRITICAL` mais frequentes nos 30 dias, com contagem, agrupadas pelo texto
com os números variáveis normalizados (vira `N`).

- **Sinal de problema**: o mesmo `ERROR` repetindo todo dia — é a falha crônica que ninguém viu. Uma
  mensagem com contagem alta na casa das centenas costuma ser o motivo real do `exit=1` da seção 3.

### 5. Falha de credencial

Quantas vezes por dia o marcador de chave recusada (o alerta com o emoji de chave 🔑) apareceu no log.

- **Sinal de problema**: qualquer ocorrência — a chave da IA expirou ou foi revogada; enquanto durar, os
  blocos do PCI entram sem extração e o bot fica surdo.

### 6. Banco

Total de linhas em `data/concursos.db` (tabela `editais`), contagem por `area`, por `fonte`, por
`estado_usuario` e a `ultima_atualizacao` mais recente.

- **Sinal de problema**: total parado (igual ao diagnóstico anterior); `fonte` com contagem parada —
  indica que uma porta não insere nada há dias; banco vazio com logs mostrando exit 0 é pior: algo apagou
  ou o bot está apontando para outro banco.

### 7. Agendamento

As linhas do projeto no `crontab` (entrada horária e `@reboot`) e se há processo do monitor rodando agora.

- **Sinal de problema**: nenhuma entrada no crontab (a varredura não dispara sozinha); entrada com caminho
  de outro diretório (instalada numa cópia antiga do repo).

### 8. Config efetiva

Áreas configuradas, portas ligadas e parâmetros de filtragem em cada uma (`gran` ligada pela URL; `pci_cargos`
quando há `pci_slugs`, com contagem de slugs; `pci_nacional` quando a flag está ligada; `pci_mcp` quando a flag
está ligada, com a contagem de termos de `pci_mcp_cargos`; além de `filtro_salarial` com padrão `"desligado"`
[`desligado` ou `ativo`], `corte_fora_sul` com padrão `0` e `resumo_filtrados` com padrão `"nunca"` [`nunca` ou
`semanal`]), lidos do `MONITOR_TARGETS_JSON` do ambiente de produção com `token` e `chat_ids` substituídos
por `<omitido>`; na sequência, os **nomes** das chaves encontradas no `.env` local e no arquivo de segredos.

- **Sinal de problema**: área esperada ausente; porta esperada desligada (ex.: `pci_nacional: desligada`
  explica estatal federal não aparecer; `pci_mcp: desligada` ou com `0 termo(s)` explica busca MCP não rodar);
  `filtro_salarial`, `corte_fora_sul` ou `resumo_filtrados` em desacordo com o esperado (ex.: valor inválido de
  `filtro_salarial` caindo em `desligado`); `MONITOR_TARGETS_JSON` ausente — a produção está no modo legado
  de URL única.

## Dica de leitura

Cruze as seções: dia `ausente` na seção 3 + `.last_success_date` velho na seção 2 = máquina/cron; `exit=1`
todo dia + um `ERROR` com contagem alta na seção 4 = falha de código ou de fonte; `ERROR` com 🔑 na seção 5
= credencial da IA. O que o diagnóstico achar não se conserta aqui: cada achado vira avaliação própria.
