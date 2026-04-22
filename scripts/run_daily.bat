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

REM Forca stdout/stderr em UTF-8 — sem isso, prints com emoji quebram
REM porque o Windows usa cp1252 quando a saida nao e um console TTY.
set "PYTHONIOENCODING=utf-8"

REM Usa o python.exe do .venv diretamente (evita dependencia do activate.bat,
REM que nem sempre se propaga corretamente via Task Scheduler).
set "VENV_PY=%PROJECT_DIR%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [%DATE% %TIME%] ERRO: %VENV_PY% nao encontrado. Rode `python -m venv .venv` primeiro. >> "%LOG_FILE%"
    popd
    endlocal & exit /b 2
)

echo [%DATE% %TIME%] Iniciando monitor_concursos >> "%LOG_FILE%"
"%VENV_PY%" main.py >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%DATE% %TIME%] Finalizado com codigo %EXIT_CODE% >> "%LOG_FILE%"

popd
endlocal & exit /b %EXIT_CODE%
