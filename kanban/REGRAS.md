<!-- Regras do monitor_concursos. O esteira.py cola este arquivo em todo prompt. So o que vale para
     qualquer ticket e que um agente sem contexto erraria. Regra de um ticket so vai no ticket. -->

- Documentos que mandam, nesta ordem: `GLOSSARIO.md` e `docs/adr/` > `docs/specs/SPEC-NNN.md` > o ticket.
  `PLANO_EVOLUCAO_AGENTICA.md` e plano antigo, nao normativo: onde ele discordar da SPEC, vale a SPEC.
- Idioma: codigo, docstrings, logs, mensagens de Telegram e commits em portugues do Brasil. Identificadores e
  comentarios sem acento (padrao do repo); texto que o usuario le pode ter acento.
- **Segredo nunca entra no repo nem no log.** O `.env` e so da maquina; a producao le
  `~/concursos-secrets/monitor.env`, fora do repo. Nenhum ticket escreve token, chave ou chat_id em arquivo
  versionado. Chave quem grava e o Lucas. O `FormatterSemSegredos` em `src/utils/logger.py` ja limpa a saida:
  nao contorne.
- **Sem dependencia nova.** HTTP sai do `requests`, que ja esta no `requirements.txt` e ja tem politica de
  retry em `src/scrapers/base_scraper.py`. Linha nova no `requirements.txt` so com justificativa no ticket: a
  producao instala de la, num notebook sem ninguem por perto.
- **Teste nao toca a rede.** Nada de HTTP real na suite: a resposta do PCI (HTML ou JSON do MCP) entra como
  fixture gravada. `tests/test_<modulo>.py`, pytest, espelhando o modulo.
- **A LLM e so do blog do Gran.** Dado do PCI e estruturado e a extracao dele e deterministica. Mandar lista
  do PCI para a LLM custa horas por rodada; ja foi medido.
- **Erro nunca vira silencio (fail-open).** Pagina que nao abriu, chamada que falhou ou campo ilegivel fazem o
  concurso **entrar**, marcado. So se descarta com evidencia positiva. Vale tambem para config invalida: cai
  no modo mais conservador, nunca no mais agressivo.
- **Migracao de schema e aditiva e idempotente**, dentro de `_ensure_schema` (`ALTER TABLE ... ADD COLUMN`
  guardado por `PRAGMA table_info`). Nunca `DROP`, nunca recriar tabela com dado dentro.
- Nao toque, sem o ticket pedir: `kanban/`, `.env`, `logs/`, `data/concursos.db`, `scripts/install_schedule.*`.
- Commits do ciclo TDD, nesta ordem e separados: `test:` (vermelho), depois `feat:`/`fix:` (verde), depois
  `docs:`. Uma fatia por par.
- IDs do quadro (`T-NNN`): so em relatorio da esteira e mensagem de merge. Nunca em codigo, docstring,
  comentario, README ou doc do repo.
