<#
.SYNOPSIS
    Cria (ou atualiza) a tarefa diaria do Monitor de Concursos no Windows
    Task Scheduler.

.DESCRIPTION
    Registra uma tarefa que dispara `scripts\run_daily.bat` uma vez por dia
    no horario informado (default: 03:00). A tarefa e configurada para:

    - Rodar mesmo se o usuario nao estiver logado (RunLevel Limited,
      Principal do usuario atual).
    - Reexecutar logo que o PC acorde/ligue se o horario foi perdido
      (StartWhenAvailable).
    - Nao empilhar execucoes (MultipleInstances = IgnoreNew).
    - Parar se passar de 1h rodando (ExecutionTimeLimit = PT1H).

.PARAMETER Time
    Horario no formato HH:mm (24h). Default: 03:00.

.PARAMETER TaskName
    Nome da tarefa no Task Scheduler. Default: MonitorConcursos.

.EXAMPLE
    PS> .\scripts\install_schedule.ps1
    PS> .\scripts\install_schedule.ps1 -Time 04:30
    PS> .\scripts\install_schedule.ps1 -TaskName MonitorConcursosDev -Time 22:00

.NOTES
    Desinstalar:  schtasks /delete /tn MonitorConcursos /f
    Inspecionar: schtasks /query /tn MonitorConcursos /v /fo LIST
    Rodar agora: schtasks /run /tn MonitorConcursos
#>
[CmdletBinding()]
param(
    [string]$Time = "03:00",
    [string]$TaskName = "MonitorConcursos"
)

$ErrorActionPreference = "Stop"

# Resolve paths absolutos baseados na localizacao deste script.
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$RunBat     = Join-Path $ProjectDir "scripts\run_daily.bat"

if (-not (Test-Path $RunBat)) {
    throw "run_daily.bat nao encontrado em: $RunBat"
}

if ($Time -notmatch '^\d{2}:\d{2}$') {
    throw "Horario invalido '$Time'. Use HH:mm, ex: 03:00."
}

Write-Host "Registrando tarefa '$TaskName' para rodar diariamente as $Time..."
Write-Host "Executavel: $RunBat"
Write-Host "Working dir: $ProjectDir"

$action = New-ScheduledTaskAction `
    -Execute $RunBat `
    -WorkingDirectory $ProjectDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $Time

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Monitor de Concursos - varredura diaria via Gran Cursos Online"

# Register-ScheduledTask substitui se ja existir.
Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $task `
    -Force | Out-Null

Write-Host ""
Write-Host "Tarefa registrada. Comandos uteis:"
Write-Host "  Inspecionar : schtasks /query /tn $TaskName /v /fo LIST"
Write-Host "  Rodar agora : schtasks /run /tn $TaskName"
Write-Host "  Remover     : schtasks /delete /tn $TaskName /f"
