@echo off
REM ---------------------------------------------------------------
REM  Monitor de Concursos — disparo diario via Task Scheduler.
REM  Ativa o .venv local, executa main.py e registra stdout/stderr
REM  em logs\run_YYYYMMDD.log (nao subscreve — um arquivo por dia).
REM ---------------------------------------------------------------
setlocal

REM Resolve o diretorio raiz do projeto (pasta-pai deste script).
set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%"

REM Cria a pasta de logs se ainda nao existir.
if not exist "logs" mkdir "logs"

REM Data no formato YYYYMMDD (independente de locale pt-BR).
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"`) do set "TODAY=%%d"
set "LOG_FILE=logs\run_%TODAY%.log"

REM Ativa o venv e roda o bot, redirecionando toda a saida para o log.
call ".venv\Scripts\activate.bat"
echo [%DATE% %TIME%] Iniciando monitor_concursos >> "%LOG_FILE%"
python main.py >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%DATE% %TIME%] Finalizado com codigo %EXIT_CODE% >> "%LOG_FILE%"

popd
endlocal & exit /b %EXIT_CODE%
