# ADR-0004 — Fuso do banco em UTC, log em hora local

**Data:** 24/11/2026
**Estado:** aceita

## Contexto

Na comparacao pos-deploy (`docs/DIAGNOSTICO-POS-DEPLOY.md`), os horarios do sistema nao batiam entre si: a rodada que o log marca as **12:49:58** aparece no banco, na coluna `ultima_atualizacao`, como **15:49:58**; a rodada das **00:32** local aparece como **03:32**. A diferenca de tres horas e o deslocamento de Curitiba (`America/Sao_Paulo`, UTC-3) para UTC.

Esse comportamento e consistente e nao e defeito, mas nao estava documentado. Quando o resumo semanal de filtrados foi implementado, quem escreveu o corte de sete dias precisou descobrir sozinho que `ultima_atualizacao` estava em UTC para calcular o limite no mesmo fuso. Sem uma decisao registrada, qualquer pessoa ou agente que comparar o log com o banco vai achar que uma das pontas esta errada.

## Decisao

O banco SQLite grava timestamps em **UTC**, e o log (assim como as datas voltadas ao usuario) usa a **hora local** da maquina.

Onde cada ponta vive hoje no codigo:

- **Quem grava em UTC:** a coluna `ultima_atualizacao` da tabela `editais` em `src/database/manager.py`. Ela usa `DEFAULT CURRENT_TIMESTAMP` do SQLite na criacao e migracao da tabela (`DatabaseManager._create_v3_table` e `DatabaseManager._migrate_to_v3`), e `CURRENT_TIMESTAMP` explicito nos `UPDATE` e `INSERT` de `DatabaseManager.atualizar_concurso`. O formato gravado e texto `AAAA-MM-DD HH:MM:SS` em UTC.
- **Quem grava em hora local:** o logger configurado por `setup_logger` em `src/utils/logger.py`. Ele usa `FormatterSemSegredos` (subclasse de `logging.Formatter`) com `datefmt='%Y-%m-%d %H:%M:%S'`, que por padrao no Python (`time.localtime`) formata `%(asctime)s` na hora local da maquina, tanto no arquivo `logs/bot_concursos.log` quanto no console.
- **Quem le qual:**
  - `DatabaseManager.listar_filtrados` (`src/database/manager.py`) le `ultima_atualizacao` comparando texto (`ultima_atualizacao >= ?`) com o parametro `desde` em UTC no formato `AAAA-MM-DD HH:MM:SS`.
  - `ConcursosBot._enviar_resumo_semanal` (`src/core/bot.py`) calcula `desde` em UTC (`datetime.now(timezone.utc) - timedelta(days=7)`) para consultar `DatabaseManager.listar_filtrados`, enquanto gera a chave da semana do arquivo marcador usando a data local (`date.today()` passado para `marcador_da_semana` em `src/core/resumo_filtrados.py`).
  - `ConcursosBot` (`src/core/bot.py`) tambem usa `date.today()` em hora local para os marcadores diarios e para comparar datas civis de encerramento (`data_fim_inscricao`).

### Regra daqui para frente

- Data/hora nova que vai para o banco usa **UTC**.
- Texto e marcador que vao para o Lucas (mensagens do Telegram, log e controle de dia/semana local) usam **hora local**.
- Qualquer comparacao entre os dois mundos **converte antes** para o fuso do outro lado.

## Consequencias

- **Assimetria proposital no resumo semanal:** em `ConcursosBot._enviar_resumo_semanal` (`src/core/bot.py`), o corte de sete dias (`desde`) e calculado em UTC (`datetime.now(timezone.utc) - timedelta(days=7)`) porque `ultima_atualizacao` esta em UTC, ao mesmo tempo em que o marcador da semana (`marcador_da_semana(date.today())`) usa a data local para acompanhar o calendario do dono. Essa assimetria e intencional e nao deve ser "corrigida".
- Quem depurar uma rodada cruzando `logs/bot_concursos.log` com a tabela `editais` precisa somar o deslocamento local (3 horas em Curitiba) ao horario do log para bater com `ultima_atualizacao`.

## O que nao se vai fazer

- **Nao ha migracao de dado:** nenhuma coluna antiga sera reescrita ou convertida (preservando todo o historico ja gravado no banco de producao), nem sera criada coluna adicional de fuso.
- **O log continua em hora local:** quem le o log e humano, e horario local e o mais direto para acompanhar as rodadas na maquina.
