[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$WebDir = Join-Path $RepoRoot "studio-web"
$VenvDir = Join-Path $RepoRoot ".venv3.12"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$EnvFile = Join-Path $RepoRoot ".env.local"
$RuntimeDir = Join-Path $RepoRoot ".cutsceneai-studio"
$LogDir = Join-Path $RuntimeDir "logs"
$BackendOutLog = Join-Path $LogDir "backend.stdout.log"
$BackendErrLog = Join-Path $LogDir "backend.stderr.log"
$FrontendOutLog = Join-Path $LogDir "frontend.stdout.log"
$FrontendErrLog = Join-Path $LogDir "frontend.stderr.log"

function Show-LogTail {
    param([string]$Path, [int]$Lines = 80)
    if (Test-Path -LiteralPath $Path) {
        Write-Host ""
        Write-Host "----- $Path -----"
        Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
        Write-Host "----- end log -----"
        Write-Host ""
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " CutSceneAI Studio Launcher"
Write-Host "============================================================"
Write-Host ""

if (-not (Test-Path -LiteralPath $BackendDir)) { throw "Backend directory not found: $BackendDir" }
if (-not (Test-Path -LiteralPath $WebDir)) { throw "Studio web directory not found: $WebDir" }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "npm is required for the Studio web UI." }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
foreach ($LogFile in @($BackendOutLog, $BackendErrLog, $FrontendOutLog, $FrontendErrLog)) {
    if (Test-Path -LiteralPath $LogFile) { Remove-Item -LiteralPath $LogFile -Force }
}

# Use one repository-local Python environment so launcher behavior is deterministic.
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating repository Python 3.12 virtual environment..."
    if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) {
        throw "Python launcher py.exe was not found. Python 3.12 is required."
    }
    & py.exe -3.12 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        throw "Failed to create Python 3.12 virtual environment: $VenvDir"
    }
}

Write-Host "Python:"
Write-Host $VenvPython
Write-Host ""

# Verify that the existing backend environment can import the complete app.
Push-Location $BackendDir
try {
    & $VenvPython -c "import fastapi, uvicorn, app.main, cutsceneai_cir, cutsceneai_preview, cutsceneai_unity, cutsceneai_unreal"
    $BackendImportOk = ($LASTEXITCODE -eq 0)
} finally {
    Pop-Location
}

if (-not $BackendImportOk) {
    Write-Host "Backend environment is incomplete. Installing local CutSceneAI packages..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

    $EditablePackages = @(
        (Join-Path $RepoRoot "cir[dev]"),
        (Join-Path $RepoRoot "preview[dev]"),
        (Join-Path $RepoRoot "dialogue[dev]"),
        (Join-Path $RepoRoot "performance[dev]"),
        (Join-Path $RepoRoot "parity[dev]"),
        (Join-Path $RepoRoot "adapters\unreal[dev]"),
        (Join-Path $RepoRoot "adapters\unity[dev]"),
        (Join-Path $RepoRoot "backend[dev]")
    )

    $PipArgs = @("-m", "pip", "install")
    foreach ($Package in $EditablePackages) { $PipArgs += @("-e", $Package) }
    & $VenvPython @PipArgs
    if ($LASTEXITCODE -ne 0) { throw "CutSceneAI backend dependency installation failed." }

    Push-Location $BackendDir
    try {
        & $VenvPython -c "import fastapi, uvicorn, app.main, cutsceneai_cir, cutsceneai_preview, cutsceneai_unity, cutsceneai_unreal"
        if ($LASTEXITCODE -ne 0) { throw "Backend import preflight still fails after installation." }
    } finally {
        Pop-Location
    }
}

Write-Host "CUTSCENEAI_BACKEND_IMPORTS=PASS"
Write-Host ""

$NodeModules = Join-Path $WebDir "node_modules"
if (-not (Test-Path -LiteralPath $NodeModules)) {
    Write-Host "Installing Studio web dependencies..."
    Push-Location $WebDir
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

$BackendArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")
if (Test-Path -LiteralPath $EnvFile) {
    # Start-Process flattens ArgumentList. Embed quotes because the repository path contains spaces.
    $QuotedEnvFile = [char]34 + $EnvFile + [char]34
    $BackendArgs += @("--env-file", $QuotedEnvFile)
    Write-Host "Environment file:"
    Write-Host $EnvFile
    Write-Host ""
} else {
    Write-Host "NOTE: .env.local was not found. Live Director generation may be unavailable."
    Write-Host ""
}

Write-Host "Starting CutSceneAI Studio..."
Write-Host "API: http://127.0.0.1:8000"
Write-Host "Web: http://127.0.0.1:5173"
Write-Host ""

$Backend = Start-Process -FilePath $VenvPython -ArgumentList $BackendArgs -WorkingDirectory $BackendDir -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrLog -PassThru
$Frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory $WebDir -RedirectStandardOutput $FrontendOutLog -RedirectStandardError $FrontendErrLog -PassThru

try {
    $Deadline = (Get-Date).AddSeconds(45)
    $ApiReady = $false
    $WebReady = $false

    while ((Get-Date) -lt $Deadline -and (-not $ApiReady -or -not $WebReady)) {
        if ($Backend.HasExited -and -not $ApiReady) {
            Write-Host "Backend exited before becoming healthy. Exit code: $($Backend.ExitCode)"
            Show-LogTail -Path $BackendOutLog
            Show-LogTail -Path $BackendErrLog
            throw "CutSceneAI backend process exited during startup."
        }

        if ($Frontend.HasExited -and -not $WebReady) {
            Write-Host "Frontend exited before becoming ready. Exit code: $($Frontend.ExitCode)"
            Show-LogTail -Path $FrontendOutLog
            Show-LogTail -Path $FrontendErrLog
            throw "CutSceneAI frontend process exited during startup."
        }

        if (-not $ApiReady) {
            try {
                $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
                $ApiReady = ($Health.status -eq "ok")
            } catch { $ApiReady = $false }
        }

        if (-not $WebReady) {
            try {
                $Response = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 2 -UseBasicParsing
                $WebReady = ($Response.StatusCode -eq 200)
            } catch { $WebReady = $false }
        }

        if (-not $ApiReady -or -not $WebReady) { Start-Sleep -Milliseconds 500 }
    }

    if (-not $ApiReady) {
        Show-LogTail -Path $BackendOutLog
        Show-LogTail -Path $BackendErrLog
        throw "CutSceneAI API did not become healthy on port 8000."
    }

    if (-not $WebReady) {
        Show-LogTail -Path $FrontendOutLog
        Show-LogTail -Path $FrontendErrLog
        throw "CutSceneAI Studio web UI did not become available on port 5173."
    }

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " CUTSCENEAI STUDIO READY"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host "CUTSCENEAI_STUDIO_API=READY"
    Write-Host "CUTSCENEAI_STUDIO_WEB=READY"
    Write-Host ""
    Write-Host "API: http://127.0.0.1:8000"
    Write-Host "Web: http://127.0.0.1:5173"
    Write-Host "Logs: $LogDir"
    Write-Host ""

    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:5173" }

    Write-Host "Studio is running. Press ENTER here to stop both services."
    [void](Read-Host)
} finally {
    foreach ($Process in @($Frontend, $Backend)) {
        if ($null -ne $Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
