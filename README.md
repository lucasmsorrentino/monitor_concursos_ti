# 🏠 Monitor de Concursos TI (Inteligente)

Este projeto é um ecossistema automatizado para monitorar, analisar e notificar atualizações de **Concursos Públicos de TI** no Brasil. Ele utiliza raspagem de dados de portais especializados, processamento de linguagem natural (LLM) local para evitar alertas redundantes,* e envio de notificações via Telegram.

## 🚀 Funcionalidades

* **Scraping Modular:** Extração de dados estruturados a partir de portais de notícias (atualmente configurado para o Gran Cursos).
* **Inteligência Artificial (LangChain + Ollama):** Análise semântica que compara o status antigo e o novo para filtrar apenas mudanças significativas (ex: "Banca definida", "Edital publicado").
* **Persistência:** Banco de dados SQLite local para controle de histórico e prevenção de duplicidade.
* **Notificações em Tempo Real:** Alertas formatados em Markdown enviados diretamente para um chat/bot do Telegram.
* **Agendamento Automático:** Motor de execução diária programada.
* **Logging Profissional:** Sistema de registros com rotação de arquivos para monitoramento de saúde do bot.

---

## 📂 Estrutura do Projeto

monitor_concursos_ti/
├── src/
│   ├── utils/                  # Ferramentas de suporte (Logger)
│   │   └── logger.py           # Registros de execução diária
│   ├── scheduler/              # Agendador de tarefas cronometradas
│   │   └── runner.py
│   ├── core/
│   │   └── bot.py              # Classe principal (ConcursoBot)
│   ├── database/
│   │   ├── __init__.py
│   │   └── manager.py          # Classe DatabaseManager
│   ├── intelligence/
│   │   ├── __init__.py
│   │   └── langchain_unit.py   # Classe IntelligenceUnit (Ollama)
│   ├── notifiers/
│   │   ├── __init__.py
│   │   └── telegram.py         # Classe TelegramNotifier
│   └── scrapers/
│       ├── __init__.py
│       └── base_scraper.py     # Interface/Classe base
│       └── gran_scraper.py     # Implementação específica para o site
├── data/
│   └── concursos.db            # Banco de dados SQLite (gerado automaticamente)
├── config/
│   └── settings.py             # Configurações de tokens e URLs
├── .env                        # Variáveis sensíveis (Tokens e IDs)
├── main.py                     # Ponto de entrada (Orquestrador)
├── requirements.txt            # Dependências do projeto
└── README.md                   # Documentação do sistema

📖 Descrição dos Módulos
src/main.py: O arquivo que você executa. Ele importa as peças e inicia o loop de monitoramento.

src/core/: Contém a lógica de negócio principal que une todas as outras partes.

src/database/: Toda a interação com o SQLite fica isolada aqui.

src/intelligence/: Onde reside a lógica do LangChain e as chamadas ao Ollama.

src/notifiers/: Módulo responsável pelas integrações de saída (Telegram, e futuramente outros).

src/scrapers/: Aqui separamos a lógica de captura. Se o site mudar, você só mexe no arquivo correspondente nesta pasta.

config/: Centraliza parâmetros como URLs alvo e caminhos de arquivos para evitar "magic strings" no meio do código.

---

## 🛠️ Instalação e Configuração

### 1. Pré-requisitos
* **Python 3.10+** instalado.
* **Ollama** instalado e rodando.
* Modelo de IA baixado (Recomendado: `llama3.1`):
  > ollama run llama3.1

### 2. Configurar o Ambiente
Clone o repositório (ou abra a pasta do projeto) e instale as dependências:
> pip install -r requirements.txt

### 3. Variáveis de Ambiente (.env)
Crie um arquivo `.env` na raiz do projeto e preencha com suas credenciais:
> TELEGRAM_TOKEN=seu_token_aqui
> TELEGRAM_CHAT_ID=seu_chat_id_aqui
> OLLAMA_MODEL=llama3.1
> URL_ALVO=https://blog.grancursosonline.com.br/concursos-ti/
> HORARIO_EXECUCAO=08:30

---

## ▶️ Como Executar

Para iniciar o bot e deixá-lo em modo de vigia (scheduler), execute o comando na raiz do projeto:
> python main.py

### Monitoramento
* **Logs:** Verifique a pasta `/logs` para ver o histórico de decisões da IA e possíveis erros.
* **Banco de Dados:** Visualize os editais salvos usando qualquer leitor de SQLite na pasta `/data`.

---
**Desenvolvido como um projeto de automação e estudo de Python/IA.**


