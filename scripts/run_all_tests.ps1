$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "BackEnd\venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Ambiente virtual Python não encontrado em $Python"
    exit 1
}

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[FALHA] Etapa falhou com código ${LASTEXITCODE}: $Title" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[OK] $Title" -ForegroundColor Green
}

Run-Step "1/6 BackEnd — Django check & migrations check" {
    Push-Location (Join-Path $Root "BackEnd")
    try {
        & $Python manage.py check
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $Python manage.py makemigrations core --check --dry-run
    } finally {
        Pop-Location
    }
}

Run-Step "2/6 BackEnd — Testes unitários, integração e implantação (PostgreSQL)" {
    Push-Location (Join-Path $Root "BackEnd")
    try {
        & $Python manage.py test core --verbosity=2
    } finally {
        Pop-Location
    }
}

Run-Step "3/6 Portaria — Compilação e testes unitários/offline (SQLite WAL, Tracker, Engine, HUD)" {
    Push-Location $Root
    try {
        $pyFiles = Get-ChildItem (Join-Path $Root "portaria") -Filter "*.py" | ForEach-Object { $_.FullName }
        & $Python -m py_compile $pyFiles
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $Python -m unittest discover -s portaria/tests -t . -v
    } finally {
        Pop-Location
    }
}

Run-Step "4/6 FrontEnd — Testes unitários e de integração (Vitest + Testing Library)" {
    Push-Location (Join-Path $Root "FrontEnd")
    try {
        npm.cmd test
    } finally {
        Pop-Location
    }
}

Run-Step "5/6 FrontEnd — Build de produção (Vite)" {
    Push-Location (Join-Path $Root "FrontEnd")
    try {
        npm.cmd run build
    } finally {
        Pop-Location
    }
}

Run-Step "6/6 Implantação — Smoke test HTTP ponta a ponta (API + PostgreSQL + Portaria)" {
    Push-Location $Root
    try {
        & $Python (Join-Path $Root "scripts\smoke_deploy.py")
    } finally {
        Pop-Location
    }
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " TODAS AS 6 CAMADAS DE TESTES PASSARAM COM SUCESSO!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
