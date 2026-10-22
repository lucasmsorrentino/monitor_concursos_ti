"""Chama o z.ai direto (sem LiteLLM) em cada endpoint x modelo e mostra a resposta.

Serve para separar problema de CONTA (saldo, plano, chave) de problema de
codigo: se a chamada crua tambem falha, o monitor nao tem o que consertar.
Foi assim que, em 22/10/2026, ficou claro que a chave gravada no notebook
respondia 1113 ("Insufficient balance or no resource package") nos dois
endpoints e em todos os modelos pagos.

Le a chave do arquivo de segredos (MONITOR_ENV_FILE ou
~/concursos-secrets/monitor.env) e nunca a imprime. Cada linha e uma chamada
real com max_tokens=20: custo desprezivel quando ha saldo.

Uso, no notebook:
    .venv/bin/python scripts/diagnostico_zai.py
"""
import os
import time

import requests
from dotenv import dotenv_values

ARQUIVO = os.getenv("MONITOR_ENV_FILE") or os.path.expanduser("~/concursos-secrets/monitor.env")
CHAVE = dotenv_values(ARQUIVO).get("ZAI_API_KEY", "")

ENDPOINTS = {
    "geral": "https://api.z.ai/api/paas/v4/chat/completions",
    "coding": "https://api.z.ai/api/coding/paas/v4/chat/completions",
}
MODELOS = ("glm-5.3-flash", "glm-5.3", "glm-4.7", "glm-4.7-flash")


def main() -> None:
    print(f"chave: {len(CHAVE)} caracteres, formato id.segredo: {CHAVE.count('.') == 1}")
    if not CHAVE:
        print(f"ZAI_API_KEY ausente em {ARQUIVO}")
        return

    for nome_ep, url in ENDPOINTS.items():
        for modelo in MODELOS:
            inicio = time.time()
            try:
                r = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {CHAVE}"},
                    json={
                        "model": modelo,
                        "messages": [{"role": "user", "content": "Responda so: ok"}],
                        "max_tokens": 20,
                    },
                    timeout=90,
                )
                corpo = r.text.replace(CHAVE, "<chave>")[:160]
                print(f"{nome_ep:6} | {modelo:13} | HTTP {r.status_code} | "
                      f"{time.time() - inicio:4.1f}s | {corpo}")
            except Exception as e:
                print(f"{nome_ep:6} | {modelo:13} | ERRO {str(e)[:120]}")


if __name__ == "__main__":
    main()
