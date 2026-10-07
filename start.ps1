# start.ps1 — One-click launcher for Smart Farming AI
# Run from the smart-farming-agent directory:
#   cd smart-farming-agent
#   .\start.ps1

$ErrorActionPreference = "Stop"

# ── Resolve paths ──────────────────────────────────────────────────────────────
$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv    = Join-Path $Root "venv"
$Python  = Join-Path $Venv  "Scripts\python.exe"
$Uvicorn = Join-Path $Venv  "Scripts\uvicorn.exe"
$Streamlit = Join-Path $Venv "Scripts\streamlit.exe"

# ── Validate venv ──────────────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: venv not found at $Venv" -ForegroundColor Red
    Write-Host "Create it first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor Cyan
    Write-Host "  venv\Scripts\pip install -r requirements.txt" -ForegroundColor Cyan
    exit 1
}

# ── Copy .env if missing ───────────────────────────────────────────────────────
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example — add your IBM keys if you have them." -ForegroundColor Yellow
}

# ── Ingest docs if ChromaDB is empty ──────────────────────────────────────────
$ChromaDir = Join-Path $Root "backend\vectorstore\chroma_db"
if (-not (Test-Path $ChromaDir)) {
    Write-Host ""
    Write-Host "First run: ingesting crop guides into ChromaDB..." -ForegroundColor Cyan
    Set-Location $Root
    & $Python -m scripts.ingest_docs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: ingest failed — RAG responses will fall back to stubs." -ForegroundColor Yellow
    } else {
        Write-Host "Crop guides ingested." -ForegroundColor Green
    }
}

# ── Start Backend ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting Backend (FastAPI) on http://localhost:8000 ..." -ForegroundColor Green
$BackendLog = Join-Path $Root "backend.log"
$BackendProc = Start-Process -FilePath $Python `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError  $BackendLog `
    -PassThru -NoNewWindow

Write-Host "  PID: $($BackendProc.Id)  |  Logs: $BackendLog" -ForegroundColor Gray

# ── Wait for backend to be ready ──────────────────────────────────────────────
Write-Host "  Waiting for backend to be ready..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.status -eq "ok") {
            Write-Host "  Backend is UP! (status: $($r.status))" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch { }
}
if (-not $ready) {
    Write-Host "  WARNING: Backend health check timed out. Check backend.log for errors." -ForegroundColor Yellow
}

# ── Start Frontend ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting Frontend (Streamlit) on http://localhost:8501 ..." -ForegroundColor Green
$FrontendLog = Join-Path $Root "frontend.log"
$FrontendProc = Start-Process -FilePath $Python `
    -ArgumentList "-m", "streamlit", "run", "frontend\app.py", `
                  "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true" `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError  $FrontendLog `
    -PassThru -NoNewWindow

Write-Host "  PID: $($FrontendProc.Id)  |  Logs: $FrontendLog" -ForegroundColor Gray

# ── Print summary ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Smart Farming AI is running!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Dashboard  : http://localhost:8501" -ForegroundColor White
Write-Host "  API docs   : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Health     : http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop both servers." -ForegroundColor Gray
Write-Host "  Backend log : $BackendLog" -ForegroundColor Gray
Write-Host "  Frontend log: $FrontendLog" -ForegroundColor Gray
Write-Host "==========================================" -ForegroundColor Cyan

# ── Keep script alive; kill both on Ctrl+C ────────────────────────────────────
try {
    Wait-Process -Id $FrontendProc.Id
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if (-not $BackendProc.HasExited)  { Stop-Process -Id $BackendProc.Id  -Force -ErrorAction SilentlyContinue }
    if (-not $FrontendProc.HasExited) { Stop-Process -Id $FrontendProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Both servers stopped." -ForegroundColor Green
}
