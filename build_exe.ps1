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
    --add-data "$PSScriptRoot\data\converted\manual_sections.json;data\converted" `
    --add-data "$PSScriptRoot\data\original\B01.PAR;data\original" `
    --add-data "$PSScriptRoot\data\original\B02.PAR;data\original" `
    "$PSScriptRoot\main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller завершился с кодом $LASTEXITCODE"
}

Write-Host "Готово: $PSScriptRoot\dist\FAST.exe"
