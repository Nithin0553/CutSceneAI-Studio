param(
    [Parameter(Mandatory = $true)]
    [string]$ProviderUrl,

    [string]$HealthUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [string]$Provider = "tencent-hymotion",

    [string]$Model = "HY-Motion-1.0-Lite",

    [string]$ModelRevision = "d83f118f8d74db76249db86dcf9982a8229f43ef4e9fa11f683019d6230dd486",

    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $RepoRoot ".env.local"
$BackupDir = Join-Path $RepoRoot ".cutsceneai-studio\env-backups"

function Test-CutSceneAIProviderUrl {
    param(
        [string]$Url,
        [string]$Label
    )

    try {
        $Uri = [System.Uri]$Url
    } catch {
        throw "$Label is not a valid URL: $Url"
    }

    if ($Uri.Scheme -eq "https") {
        return
    }

    if (
        $Uri.Scheme -eq "http" -and
        $Uri.Host -in @("127.0.0.1", "localhost", "::1")
    ) {
        return
    }

    throw "$Label must use HTTPS unless it points to localhost."
}

function Set-CutSceneAIEnvValue {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )

    $Prefix = "$Key="
    $Updated = $false
    $Result = foreach ($Line in $Lines) {
        if ($Line.StartsWith($Prefix, [System.StringComparison]::Ordinal)) {
            $Updated = $true
            "$Key=$Value"
        } else {
            $Line
        }
    }

    if (-not $Updated) {
        $Result += "$Key=$Value"
    }

    return @($Result)
}

Write-Host ""
Write-Host "============================================================"
Write-Host " CutSceneAI Body Provider Configuration"
Write-Host "============================================================"
Write-Host ""

Test-CutSceneAIProviderUrl -Url $ProviderUrl -Label "ProviderUrl"

if ([string]::IsNullOrWhiteSpace($HealthUrl)) {
    $ProviderUri = [System.Uri]$ProviderUrl
    $Builder = [System.UriBuilder]$ProviderUri
    $Builder.Path = "/health"
    $Builder.Query = ""
    $HealthUrl = $Builder.Uri.AbsoluteUri.TrimEnd("/")
}

Test-CutSceneAIProviderUrl -Url $HealthUrl -Label "HealthUrl"

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "Token cannot be empty."
}

if ($TimeoutSeconds -lt 1 -or $TimeoutSeconds -gt 1800) {
    throw "TimeoutSeconds must be between 1 and 1800."
}

$Lines = @()
if (Test-Path -LiteralPath $EnvPath) {
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    $BackupPath = Join-Path $BackupDir ("env-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".local")
    Copy-Item -LiteralPath $EnvPath -Destination $BackupPath -Force
    Write-Host "Preserved existing .env.local:"
    Write-Host $BackupPath
    Write-Host ""

    $Lines = @(Get-Content -LiteralPath $EnvPath)
}

$Settings = [ordered]@{
    "CUTSCENEAI_BODY_PROVIDER_URL" = $ProviderUrl
    "CUTSCENEAI_BODY_PROVIDER_HEALTH_URL" = $HealthUrl
    "CUTSCENEAI_BODY_PROVIDER_TOKEN" = $Token
    "CUTSCENEAI_BODY_PROVIDER" = $Provider
    "CUTSCENEAI_BODY_MODEL" = $Model
    "CUTSCENEAI_BODY_MODEL_REVISION" = $ModelRevision
    "CUTSCENEAI_BODY_PROMPT_VERSION" = "body-v0.1"
    "CUTSCENEAI_BODY_DETERMINISTIC" = "false"
    "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS" = "$TimeoutSeconds"
}

foreach ($Entry in $Settings.GetEnumerator()) {
    $Lines = Set-CutSceneAIEnvValue -Lines $Lines -Key $Entry.Key -Value $Entry.Value
}

Set-Content -LiteralPath $EnvPath -Value $Lines -Encoding UTF8

Write-Host "Provider configuration written to:"
Write-Host $EnvPath
Write-Host ""
Write-Host "Provider: $Provider"
Write-Host "Model: $Model"
Write-Host "Model revision: $ModelRevision"
Write-Host "Generation URL: $ProviderUrl"
Write-Host "Health URL: $HealthUrl"
Write-Host "Token: [stored, not printed]"
Write-Host ""

$Headers = @{
    Authorization = "Bearer $Token"
}

Write-Host "Checking provider health..."
try {
    $Health = Invoke-RestMethod -Method Get -Uri $HealthUrl -Headers $Headers -TimeoutSec 10
} catch {
    Write-Host ""
    Write-Warning "Configuration was saved, but provider health is not reachable yet."
    Write-Warning $_
    Write-Host ""
    Write-Host "Start/fix the GPU provider and rerun this script, or restart Studio after it is reachable."
    exit 2
}

if ($Health.provider -ne $Provider) {
    throw "Health provider mismatch. Expected '$Provider', got '$($Health.provider)'."
}

if ($Health.model -ne $Model) {
    throw "Health model mismatch. Expected '$Model', got '$($Health.model)'."
}

if ($Health.model_revision -ne $ModelRevision) {
    throw "Health model revision mismatch. Expected '$ModelRevision', got '$($Health.model_revision)'."
}

Write-Host ""
Write-Host "CUTSCENEAI_BODY_PROVIDER_HEALTH=PASS"
Write-Host "Status: $($Health.status)"
Write-Host ""
Write-Host "Restart CutSceneAI Studio so the backend reloads .env.local."
