$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Cal crear .venv i instal·lar el projecte. Consulta el README.'
}
Write-Host 'Career Copilot: http://127.0.0.1:8765'
Write-Host 'Mantén aquesta terminal oberta. Ctrl+C per aturar.'
& $taskPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765
exit $LASTEXITCODE
