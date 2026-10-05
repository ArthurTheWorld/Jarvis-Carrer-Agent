# Para o Jarvis que roda em segundo plano (supervisor + bot).
# Uso: powershell -ExecutionPolicy Bypass -File parar_jarvis.ps1
$alvos = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'supervisor\.py|telegram_bot\.py' }

if (-not $alvos) {
    Write-Host "O Jarvis não está rodando."
    exit 0
}

# Primeiro o supervisor, para ele não reiniciar o bot
$alvos | Sort-Object { $_.CommandLine -notmatch 'supervisor\.py' } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Encerrado: PID $($_.ProcessId)"
}
Write-Host "Jarvis parado."