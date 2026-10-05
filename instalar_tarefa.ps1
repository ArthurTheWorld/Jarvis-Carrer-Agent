# Cria a tarefa que inicia o Jarvis automaticamente quando você entra no Windows.
# Rode UMA vez, de dentro da pasta do projeto:
#   powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1
$pasta = $PSScriptRoot
$pythonw = Join-Path $pasta ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    Write-Error "Não encontrei $pythonw. Rode este script dentro da pasta do projeto, com o .venv criado."
    exit 1
}

$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "supervisor.py" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$gatilho.Delay = "PT1M"   # espera 1 minuto após o login (dá tempo da internet conectar)
$config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Jarvis" -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Bot Jarvis no Telegram (inicia no login)" -Force | Out-Null

Write-Host "Tarefa 'Jarvis' criada. Ela inicia sozinha no próximo login."
Write-Host "Para iniciar agora: Start-ScheduledTask -TaskName Jarvis"