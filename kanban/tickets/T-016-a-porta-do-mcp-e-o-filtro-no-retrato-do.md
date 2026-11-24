---
id: T-016
titulo: A porta do MCP e o filtro no retrato do diagnostico
tipo: codigo
nivel: P-
status: backlog
repo: principal
spec: [SPEC-001]
depende_de: []
toca: [scripts/diagnostico_producao.sh, tests/test_diagnostico_producao.py]
recursos: []
afinidade:
retornos: 0
---
# T-016 · A porta do MCP e o filtro no retrato do diagnostico

## Contexto

O `scripts/diagnostico_producao.sh` e o retrato da maquina de producao, e foi o que provou o deploy de
24/11/2026. Mas o bloco `== Config efetiva ==` dele nasceu antes das chaves novas: ele imprime as portas
`gran`, `pci_cargos` e `pci_nacional` e **nao imprime** `pci_mcp` nem nada do filtro salarial.

O efeito pratico apareceu no proprio deploy, registrado em `docs/DIAGNOSTICO-POS-DEPLOY.md`: depois de
ligar a porta nova, o retrato mostrava a area TI com `pci_cargos: desligada` e `pci_nacional: desligada`,
e **nenhuma linha dizendo qual porta ficou ligada no lugar**. A prova de que o MCP estava no ar teve de
ser indireta, pela contagem `pci_mcp=101` na secao do banco. Quem abrir esse retrato as 3h da manha com o
bot quieto nao tem como saber, pelo bloco de config, se o filtro esta ligado e com que corte.

## Critério de aceite

- [ ] O bloco `== Config efetiva ==` passa a imprimir, por area, a porta `pci_mcp` no mesmo estilo das
      outras tres (`ligada` com a contagem de termos, ou `desligada`).
- [ ] O mesmo bloco passa a imprimir o estado do filtro salarial por area: `filtro_salarial`,
      `corte_fora_sul` e `resumo_filtrados`. Chave ausente aparece com o padrao da SPEC-001 secao 3.6, nao
      em branco.
- [ ] **Nenhum valor novo e segredo**, e a garantia do cabecalho do script continua valendo: nada de
      token, chave ou `chat_id` na saida. Confira com
      `bash scripts/diagnostico_producao.sh | grep -ciE "bot[0-9]{6,}:|ZAI_API_KEY=[^<]"` devolvendo `0`.
- [ ] O script continua **somente leitura** e continua saindo com `0` mesmo com chave ausente, arquivo
      ausente ou JSON invalido. Essa e a promessa do cabecalho dele: o diagnostico relata, nao julga.
- [ ] A suite inteira continua verde (539 em 24/11/2026).

## Plano de testes

Costura: `bash scripts/diagnostico_producao.sh <raiz>`, pelo `tests/test_diagnostico_producao.py`, que ja
roda o script com uma raiz de mentira montada em `tmp_path`. E a interface publica: o script inteiro, pela
saida que ele imprime. Pega: o texto do bloco de config e o codigo de saida. Nao pega: a maquina de
producao de verdade.

Oráculo: um `monitor.env` de mentira, escrito a mao no teste, com uma area de cada tipo: uma com
`pci_mcp` ligado e filtro ativo, uma com as chaves ausentes (que tem de mostrar os padroes) e uma com o
JSON quebrado (que tem de degradar sem derrubar). O texto esperado vai literal no teste.

Testes que nascem vermelhos em `tests/test_diagnostico_producao.py`:

- `test_config_mostra_a_porta_do_mcp_ligada_com_a_contagem_de_termos`
- `test_config_mostra_o_filtro_salarial_com_corte_e_resumo`
- `test_area_sem_as_chaves_novas_mostra_os_padroes_da_spec`
- `test_config_quebrada_degrada_e_o_script_sai_com_zero`
- `test_a_saida_nova_nao_traz_segredo`

## Fora do escopo

- Qualquer outra secao do script. So o bloco `== Config efetiva ==`.
- Fazer o diagnostico **julgar** o que encontrou, ou consertar o que achar. A SPEC-002 e a ADR-0003
  separam a sonda do conserto de proposito, e esse e assunto da fase da SPEC-002.
- Rodar na producao. O ticket se fecha com o teste; quem roda no notebook e o Lucas, ou a proxima rodada
  de deploy.

## Notas do arquiteto

- **P− porque o padrao esta ao lado:** as tres portas que ja aparecem no bloco sao o molde a copiar, e o
  arquivo de teste ja monta a raiz de mentira. E duas secoes de shell e cinco testes.
- O script exporta `LC_ALL=C` de proposito, para o `grep` e o `sed` tratarem byte e nao caractere. Nao
  mexa nisso: foi o que fez a saida ficar igual em qualquer Debian.
- Esse bloco e ancestral da sonda da SPEC-002. Melhorar o retrato agora e barato e a fase seguinte herda.
