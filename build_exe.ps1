$ErrorActionPreference = 'Stop'

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Сначала создайте .venv и установите requirements.txt и requirements-build.txt'
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name FAST `
    --add-data "$PSScriptRoot\data;data" `
    "$PSScriptRoot\main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller завершился с кодом $LASTEXITCODE"
}

Write-Host "Готово: $PSScriptRoot\dist\FAST.exe"
