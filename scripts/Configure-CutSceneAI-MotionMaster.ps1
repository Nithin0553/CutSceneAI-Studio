[CmdletBinding()]
param(
    [ValidateSet("Local", "Remote")]
    [string]$Mode = "Local",

    [string]$RepoRoot = "D:\Research\CutSceneAI Foundation v0.1\cutscene-ai",

    [string]$MotionMasterRoot = "E:\CutSceneAI-Research\models\MotionMaster",

    [string]$MotionMasterPython = "",

    [ValidateSet("+z", "-z")]
    [string]$SourceForwardAxis = "+z",

    [ValidateRange(1, 240)]
    [int]$SourceFps = 30,

    [string]$RemoteProviderUrl = "",

    [string]$RemoteHealthUrl = "",

    [string]$RemoteBearerToken = "",

    [switch]$CloneRepository,

    [switch]$CreatePythonEnvironment,

    [switch]$InstallDependencies,

    [switch]$WriteEnvironment
)

$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " $Title"
    Write-Host "============================================================"
    Write-Host ""
}

function Require-Path {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description was not found: $Path"
    }
}

function Resolve-Python310 {
    param([string]$Preferred)

    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        Require-Path -Path $Preferred -Description "MotionMaster Python"
        return (Resolve-Path -LiteralPath $Preferred).Path
    }

    $Candidate = Join-Path $MotionMasterRoot ".venv310\Scripts\python.exe"
    if (Test-Path -LiteralPath $Candidate) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $PyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $PyLauncher) {
        $Result = & $PyLauncher.Source -3.10 -c "import sys; print(sys.executable)"
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($Result)) {
            return $Result.Trim()
        }
    }

    throw @"
Python 3.10 is required by MotionMaster and was not found.

Install Python 3.10, or create a MotionMaster Python 3.10 environment and pass:
  -MotionMasterPython "X:\path\to\python.exe"
"@
}

function Assert-Python310 {
    param([string]$Python)

    $Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0 -or $Version.Trim() -ne "3.10") {
        throw "MotionMaster requires Python 3.10; '$Python' reported '$Version'."
    }
}

function Set-DotEnvValue {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Name,
        [string]$Value
    )

    $EscapedName = [Regex]::Escape($Name)
    $Index = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^\s*$EscapedName\s*=") {
            $Index = $i
            break
        }
    }

    $Line = "$Name=$Value"
    if ($Index -ge 0) {
        $Lines[$Index] = $Line
    } else {
        $Lines.Add($Line)
    }
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-GitRevision {
    param([string]$Root)

    $GitDir = Join-Path $Root ".git"
    if (-not (Test-Path -LiteralPath $GitDir)) {
        return "unknown"
    }

    Push-Location $Root
    try {
        $Revision = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Revision)) {
            return "unknown"
        }
        return $Revision
    } finally {
        Pop-Location
    }
}

function Quote-JsonString {
    param([string]$Value)
    return ($Value | ConvertTo-Json -Compress)
}

Write-Section "CutSceneAI MotionMaster Provider Configuration"

Require-Path -Path $RepoRoot -Description "CutSceneAI repository"

$ProviderWrapper = Join-Path $RepoRoot "tools\providers\motionmaster_provider.py"
Require-Path -Path $ProviderWrapper -Description "CutSceneAI MotionMaster provider wrapper"

$EnvFile = Join-Path $RepoRoot ".env.local"

if ($Mode -eq "Remote") {
    if ([string]::IsNullOrWhiteSpace($RemoteProviderUrl)) {
        throw "-RemoteProviderUrl is required when -Mode Remote is selected."
    }
    if (-not $RemoteProviderUrl.StartsWith("https://", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Remote provider URL must use HTTPS."
    }
    if (
        -not [string]::IsNullOrWhiteSpace($RemoteHealthUrl) -and
        -not $RemoteHealthUrl.StartsWith("https://", [StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Remote health URL must use HTTPS."
    }

    if ($WriteEnvironment) {
        $Lines = [System.Collections.Generic.List[string]]::new()
        if (Test-Path -LiteralPath $EnvFile) {
            foreach ($Line in Get-Content -LiteralPath $EnvFile) {
                $Lines.Add($Line)
            }
        }

        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER" -Value "motionmaster-cvpr2026"
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL" -Value "mllm_single_3b"
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL_REVISION" -Value "remote-managed"
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_DETERMINISTIC" -Value "false"
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_URL" -Value $RemoteProviderUrl
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS" -Value "1200"

        if (-not [string]::IsNullOrWhiteSpace($RemoteHealthUrl)) {
            Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_HEALTH_URL" -Value $RemoteHealthUrl
        }
        if (-not [string]::IsNullOrWhiteSpace($RemoteBearerToken)) {
            Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_TOKEN" -Value $RemoteBearerToken
        }

        [IO.File]::WriteAllLines($EnvFile, $Lines)
        Write-Host "CUTSCENEAI_MOTIONMASTER_ENV=WRITTEN"
    }

    Write-Host "CUTSCENEAI_MOTIONMASTER_MODE=REMOTE"
    Write-Host "Provider URL: $RemoteProviderUrl"
    Write-Host ""
    Write-Host "Restart CutSceneAI Studio after writing .env.local."
    exit 0
}

if ($CloneRepository -and -not (Test-Path -LiteralPath $MotionMasterRoot)) {
    $Parent = Split-Path -Parent $MotionMasterRoot
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null

    Write-Host "Cloning MotionMaster..."
    & git clone https://github.com/liyanhu666666/MotionMaster.git $MotionMasterRoot
    if ($LASTEXITCODE -ne 0) {
        throw "MotionMaster clone failed."
    }
}

Require-Path -Path $MotionMasterRoot -Description "MotionMaster repository"
Require-Path -Path (Join-Path $MotionMasterRoot "infer.py") -Description "MotionMaster infer.py"

if ($CreatePythonEnvironment) {
    $VenvPython = Join-Path $MotionMasterRoot ".venv310\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        $BasePython = Resolve-Python310 -Preferred $MotionMasterPython
        Assert-Python310 -Python $BasePython

        Write-Host "Creating MotionMaster Python 3.10 environment..."
        & $BasePython -m venv (Join-Path $MotionMasterRoot ".venv310")
        if ($LASTEXITCODE -ne 0) {
            throw "MotionMaster virtual environment creation failed."
        }
    }
    $MotionMasterPython = $VenvPython
}

$Python = Resolve-Python310 -Preferred $MotionMasterPython
Assert-Python310 -Python $Python

if ($InstallDependencies) {
    Write-Host ""
    Write-Host "Installing MotionMaster dependencies into:"
    Write-Host $Python

    & $Python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade MotionMaster packaging tools."
    }

    & $Python -m pip install -r (Join-Path $MotionMasterRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "MotionMaster requirements installation failed."
    }

    & $Python -m pip install "git+https://github.com/facebookresearch/pytorch3d.git@stable" --no-build-isolation
    if ($LASTEXITCODE -ne 0) {
        throw @"
PyTorch3D installation failed.

MotionMaster's official setup requires PyTorch3D. On Windows this dependency can require
a compatible CUDA/compiler environment. Keep the failure output as evidence; do not
silently install an unrelated wheel.
"@
    }

    & $Python -m pip install -e (Join-Path $MotionMasterRoot "src\human_body_prior_repo")
    if ($LASTEXITCODE -ne 0) {
        throw "MotionMaster human_body_prior installation failed."
    }
}

$MllmPath = Join-Path $MotionMasterRoot "checkpoints\mllm_single_3b"
$TokenizerPath = Join-Path $MotionMasterRoot "checkpoints\tokenizer.pt"
$StatsPath = Join-Path $MotionMasterRoot "checkpoints\norm_stats.npz"
$SmplxPath = Join-Path $MotionMasterRoot "checkpoints\smplx_model"
$SmplxMale = Join-Path $SmplxPath "SMPLX_MALE.npz"
$VposerPath = Join-Path $MotionMasterRoot "src\human_body_prior_repo\support_data\dowloads\V02_05"

$Missing = [System.Collections.Generic.List[string]]::new()
foreach ($Item in @(
    @{ Path = $MllmPath; Name = "MotionMaster mllm_single_3b checkpoint" },
    @{ Path = $TokenizerPath; Name = "MotionMaster tokenizer.pt" },
    @{ Path = $StatsPath; Name = "MotionMaster norm_stats.npz" },
    @{ Path = $SmplxMale; Name = "SMPL-X SMPLX_MALE.npz" },
    @{ Path = $VposerPath; Name = "VPoser V02_05 weights" }
)) {
    if (-not (Test-Path -LiteralPath $Item.Path)) {
        $Missing.Add("$($Item.Name): $($Item.Path)")
    }
}

if ($Missing.Count -gt 0) {
    Write-Host ""
    Write-Host "CUTSCENEAI_MOTIONMASTER_ASSETS=INCOMPLETE"
    Write-Host ""
    Write-Host "The following licensed/model assets are still required:"
    foreach ($Item in $Missing) {
        Write-Host " - $Item"
    }
    Write-Host ""
    Write-Host "MotionMaster's README requires the MLLM/tokenizer/stats checkpoints plus"
    Write-Host "separately acquired SMPL-X and VPoser assets. CutSceneAI will not fabricate"
    Write-Host "or substitute those files."
    exit 2
}

$GitRevision = Get-GitRevision -Root $MotionMasterRoot
$TokenizerSha = Get-FileSha256 -Path $TokenizerPath
$StatsSha = Get-FileSha256 -Path $StatsPath
$RevisionMaterial = "$GitRevision|$TokenizerSha|$StatsSha"
$RevisionBytes = [Text.Encoding]::UTF8.GetBytes($RevisionMaterial)
$RevisionHash = [Security.Cryptography.SHA256]::HashData($RevisionBytes)
$RevisionDigest = -join ($RevisionHash | ForEach-Object { $_.ToString("x2") })
$ProviderRevision = "motionmaster-$($RevisionDigest.Substring(0,16))"

Write-Host ""
Write-Host "MotionMaster preflight:"
Write-Host " Python: $Python"
Write-Host " Git revision: $GitRevision"
Write-Host " Provider revision: $ProviderRevision"
Write-Host " Source FPS: $SourceFps"
Write-Host " Source forward axis: $SourceForwardAxis"

if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "GPU:"
    & nvidia-smi.exe --query-gpu=name,memory.total,driver_version --format=csv,noheader
} else {
    Write-Warning "nvidia-smi.exe was not found. MotionMaster requires a CUDA-capable GPU."
}

if ($WriteEnvironment) {
    $Lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($Line in Get-Content -LiteralPath $EnvFile) {
            $Lines.Add($Line)
        }
    }

    $CommandJson = @($Python, $ProviderWrapper) | ConvertTo-Json -Compress

    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER" -Value "motionmaster-cvpr2026"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL" -Value "mllm_single_3b"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL_REVISION" -Value $ProviderRevision
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_DETERMINISTIC" -Value "false"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_COMMAND" -Value $CommandJson
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS" -Value "1200"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_ROOT" -Value $MotionMasterRoot
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_REVISION" -Value $ProviderRevision
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_SOURCE_FPS" -Value "$SourceFps"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_FORWARD_AXIS" -Value $SourceForwardAxis
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_MLLM_PATH" -Value $MllmPath
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_TOKENIZER_PATH" -Value $TokenizerPath
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_STATS_PATH" -Value $StatsPath
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MOTIONMASTER_SMPLX_PATH" -Value $SmplxPath

    [IO.File]::WriteAllLines($EnvFile, $Lines)

    Write-Host ""
    Write-Host "CUTSCENEAI_MOTIONMASTER_ENV=WRITTEN"
    Write-Host "Updated: $EnvFile"
    Write-Host "Secrets were not printed."
}

Write-Host ""
Write-Host "CUTSCENEAI_MOTIONMASTER_PREFLIGHT=PASS"
Write-Host ""
Write-Host "Restart CutSceneAI Studio after writing .env.local."
Write-Host "Then Stage 04 should report Body = READY."
