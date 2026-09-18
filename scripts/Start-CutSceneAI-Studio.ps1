[CmdletBinding()]
param(
    [string]$Python = "py -3.12",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$WebDir = Join-Path $RepoRoot "studio-web"

if (-not (Test-Path -LiteralPath $BackendDir)) { throw "Backend directory not found: $BackendDir" }
if (-not (Test-Path -LiteralPath $WebDir)) { throw "Studio web directory not found: $WebDir" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required for the Studio web UI." }

$PythonExe = $null
$PythonArgs = @()
$VenvPython = Join-Path $RepoRoot ".venv3.12\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $parts = $Python -split " "
    $PythonExe = $parts[0]
    if ($parts.Count -gt 1) { $PythonArgs = @($parts[1..($parts.Count - 1)]) }
}

$NodeModules = Join-Path $WebDir "node_modules"
if (-not (Test-Path -LiteralPath $NodeModules)) {
    Write-Host "Installing Studio web dependencies..."
    Push-Location $WebDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Starting CutSceneAI Studio..."
Write-Host "API: http://127.0.0.1:8000"
Write-Host "Web: http://127.0.0.1:5173"
Write-Host ""

$BackendCommand = @($PythonArgs + @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"))
$EnvFile = Join-Path $RepoRoot ".env.local"
if (Test-Path -LiteralPath $EnvFile) {
    $BackendCommand += @("--env-file", $EnvFile)
}
$Backend = Start-Process -FilePath $PythonExe -ArgumentList $BackendCommand -WorkingDirectory $BackendDir -PassThru
$Frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory $WebDir -PassThru

try {
    $Deadline = (Get-Date).AddSeconds(30)
    $ApiReady = $false
    $WebReady = $false
    while ((Get-Date) -lt $Deadline -and (-not $ApiReady -or -not $WebReady)) {
        if (-not $ApiReady) {
            try {
                $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
                $ApiReady = $Health.status -eq "ok"
            } catch {}
        }
        if (-not $WebReady) {
            try {
                $Response = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 1 -UseBasicParsing
                $WebReady = $Response.StatusCode -eq 200
            } catch {}
        }
        if (-not $ApiReady -or -not $WebReady) { Start-Sleep -Milliseconds 500 }
    }

    if (-not $ApiReady) { throw "CutSceneAI API did not become healthy on port 8000." }
    if (-not $WebReady) { throw "CutSceneAI Studio web UI did not become available on port 5173." }

    Write-Host "CUTSCENEAI_STUDIO_API=READY"
    Write-Host "CUTSCENEAI_STUDIO_WEB=READY"
    Write-Host ""
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:5173" }
    Write-Host "Studio is running. Press ENTER to stop both services."
    [void](Read-Host)
} finally {
    foreach ($Process in @($Frontend, $Backend)) {
        if ($null -ne $Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
