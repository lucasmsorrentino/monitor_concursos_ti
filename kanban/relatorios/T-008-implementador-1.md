ENTREGUE
Esteira: implementador · glm-flash (zai-coding-plan/glm-5.3-flash) · nível P+ · esforço high · 2026-11-23 11:38 → 2026-11-23 12:10 (33 min)
Resumo: Script de diagnóstico da produção entregue em TDD (4 commits: chore → test → feat → docs). Coleta
evidência dos últimos 30 dias nas 8 seções do aceite, por uma árvore falsa em tmp_path via subprocess+bash;
12 testes, todos passando na ponta. Segredos omitidos (`<omitido>`), saída sempre com código 0, degradação
para "ausente" em qualquer arquivo faltante.
Arquivos:
  - scripts/diagnostico_producao.sh (toca)
  - docs/DIAGNOSTICO.md (toca)
  - tests/test_diagnostico_producao.py (FORA do toca — justificativa: o próprio plano de testes do ticket
    especifica esse caminho; segue a convenção do repo `tests/test_<modulo>.py` espelhando o artefato)
Commits:
  - b667dce chore: esqueleto do script de diagnostico da producao (secoes nao implementadas)
  - 546f5e1 test: diagnostico da producao precisa reportar as 8 secoes, sobreviver a arvore vazia e omitir segredo
  - ec89a36 feat: diagnostico da producao coleta evidencia dos ultimos 30 dias sem vazar segredo
  - 33af986 docs: guia do diagnostico da producao (como rodar, o que cada secao significa, sinais de problema)
Testes:
  "C:/Users/Lucas/Documents/automation/monitor_concursos/.venv/Scripts/python.exe" -m pytest -q
  → base 296 passed / 0 failed · ponta 308 passed / 0 failed (0 skipped nesta máquina; o módulo novo tem
  `pytest.mark.skipif` por ausência de bash e seria 12 skipped sem Git Bash). Lint: não configurado no repo,
  nada rodado. Condição da medição: Windows com Git Bash 5.2 disponível; PATH do subprocesso recebe o venv
  para garantir um `python` funcional no fallback do banco.
  Red conferido: com o esqueleto (exit 2, "nao implementado" — análogo do NotImplementedError), os 11 testes
  do plano falham pelo motivo certo (returncode 2 e stdout vazio; nenhum por coleta/importação).
Testes que nascem verdes: 1 guarda — test_config_efetiva_mostra_areas_e_omite_segredo_do_json, escrito junto
  do feat porque a fonte JSON é o principal vetor de segredo da config de produção e o plano não cobria esse
  caminho (só cobria o `.env`). Os outros 11 (10 do plano + test_conta_chave_ausente_por_dia, acréscimo ao
  plano para cobrir o item de aceite 5) nasceram vermelhos.
Desvios e riscos:
  - Dois bugs reais pegos pelo vermelho, já resolvidos no feat: sed com `s/re/` sem o segundo delimitador
    ("unterminated `s' command") e dependência de locale que impedia grep/sed de atravessar emoji. O script
    agora força `LC_ALL=C` (semântica de bytes, determinística em qualquer Debian) e constrói o marcador de
    credencial por bytes ($'\xf0\x9f\x94\x91'), imune a conversão de encoding.
  - Probes do ambiente: o `python3` desta máquina Windows é o alias da Microsoft Store (rc=49); o script
    sonda `python3 -c pass` antes de aceitar e cai para `python`. No notebook Debian o `python3` real é
    aceito de primeira.
  - Risco: nesta máquina o fallback python do banco não foi exercitado (o `sqlite3` CLI existe e é o caminho
    tomado pelos testes). O caminho python3 (PY_BANCO, `mode=ro`) só roda em máquinas sem o CLI — conferir
    na primeira rodada no notebook. O `sqlite3 -readonly` garante que nenhuma leitura cria journal/wal/shm.
  - Ajuste de interpretação: a seção 3 caminha nos 30 dias do calendário (presente ou `ausente` por dia), e
    não apenas nos arquivos existentes — foi o modo mais literal de cumprir "dia sem arquivo aparece como
    ausente" mantendo a série visível. As contagens de "Ciclo finalizado" são somadas entre áreas no dia
    (rodada multi-área grava uma linha por área; conferido em logs/run_20260610.log do repo principal).
  - O revisor deve olhar: normalização de números nos erros recorrentes (`[0-9]+`→`N`) pode agrupar
    mensagens distintas que só divergem por dígitos; aceito porque o aceite pede exatamente "agrupadas pelo
    texto sem os números variáveis". A lista de chaves do `.env`/monitor.env imprime `CHAVE=<omitido>` via
    sed (valor nunca carregado em variável).
Pendências:
  - Rodar no notebook e colar a saída: ticket de deploy do dono (fora do escopo deste, como o ticket define).
  - Conclusão sobre o que está quebrado a partir da evidência: nevoa da SPEC-001 seção 8, ticket futuro.
  - Suíte num ambiente sem Git Bash (os 12 testes pulam): primeira rodada de CI Windows sem bash deve
    confirmar a degradação.
Push: não feito — regra do projeto ("Nao faca push"); o trabalho está em commit local na branch do worktree.
