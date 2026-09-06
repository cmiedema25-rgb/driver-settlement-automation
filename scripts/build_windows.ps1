$ErrorActionPreference = "Stop"

Write-Host "Installing package and build tools..."
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

$tesseract = Join-Path $env:ProgramFiles "Tesseract-OCR"
if (-not (Test-Path (Join-Path $tesseract "tesseract.exe"))) {
    Write-Host "Installing Tesseract OCR..."
    choco install tesseract --yes --no-progress
}

if (-not (Test-Path (Join-Path $tesseract "tesseract.exe"))) {
    throw "Tesseract was not found at $tesseract"
}

Write-Host "Running unit tests..."
python -m pytest -q

Write-Host "Running internal OCR and settlement self-test..."
python -m driver_settlement.verify

Write-Host "Building standalone Windows executable..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name DriverSettlementAutomation `
    --collect-all fitz `
    --collect-all PIL `
    --add-data "$tesseract;tesseract" `
    app.py

$exe = Join-Path $PWD "dist\DriverSettlementAutomation.exe"
if (-not (Test-Path $exe)) {
    throw "Build completed without expected executable: $exe"
}

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
$size = (Get-Item $exe).Length
Write-Host "Built: $exe"
Write-Host "Size: $size bytes"
Write-Host "SHA256: $hash"
