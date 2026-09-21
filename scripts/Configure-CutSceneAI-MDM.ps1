[CmdletBinding()]
param(
    [string]$RepoRoot = "D:\Research\CutSceneAI Foundation v0.1\cutscene-ai",
    [string]$ResearchRoot = "E:\CutSceneAI-Research",
    [string]$MdmRoot = "",
    [string]$MdmPython = "",
    [string]$Device = "",
    [switch]$WriteEnvironment
)

$ErrorActionPreference = "Stop"

$ExpectedCheckpointSha256 = "0fbdc8547c8f262b8838645586790b55f983d90db3bb7ed58e4b5d49429587ca"
$ExpectedClipSha256 = "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " $Title"
    Write-Host "============================================================"
    Write-Host ""
}

function Require-Path {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description was not found: $Path"
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

function Remove-DotEnvValue {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Name
    )
    $EscapedName = [Regex]::Escape($Name)
    for ($i = $Lines.Count - 1; $i -ge 0; $i--) {
        if ($Lines[$i] -match "^\s*$EscapedName\s*=") {
            $Lines.RemoveAt($i)
        }
    }
}

function Find-MdmSourceRoot {
    param([string]$Base)

    if (-not [string]::IsNullOrWhiteSpace($MdmRoot)) {
        $Candidate = (Resolve-Path -LiteralPath $MdmRoot).Path
        Require-Path -Path (Join-Path $Candidate "sample\generate.py") -Description "MDM sample.generate"
        return $Candidate
    }

    $FixedCandidates = @(
        (Join-Path $Base "models\mdm\motion-diffusion-model"),
        (Join-Path $Base "models\mdm\source\motion-diffusion-model"),
        (Join-Path $Base "models\mdm\source"),
        (Join-Path $Base "models\mdm")
    )

    foreach ($Candidate in $FixedCandidates) {
        if (Test-Path -LiteralPath (Join-Path $Candidate "sample\generate.py")) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }

    $SearchRoot = Join-Path $Base "models\mdm"
    Require-Path -Path $SearchRoot -Description "MDM research asset root"

    $GenerateFiles = @(
        Get-ChildItem -LiteralPath $SearchRoot -Filter "generate.py" -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq "sample" }
    )

    $Roots = @(
        $GenerateFiles |
        ForEach-Object { Split-Path -Parent $_.Directory.FullName } |
        Sort-Object -Unique
    )

    if ($Roots.Count -eq 0) {
        throw "Could not locate an MDM source checkout containing sample\generate.py under $SearchRoot"
    }

    if ($Roots.Count -gt 1) {
        Write-Host "Multiple MDM source roots were found:"
        foreach ($Root in $Roots) {
            Write-Host " - $Root"
        }
        throw "Pass -MdmRoot explicitly so the research runtime is not selected ambiguously."
    }

    return $Roots[0]
}

function Test-MdmPython {
    param([string]$Python, [string]$SourceRoot)

    if (-not (Test-Path -LiteralPath $Python)) {
        return $false
    }

    Push-Location $SourceRoot
    try {
        $Code = 'import sys,numpy,torch; from utils import parser_util; print("CUTSCENEAI_MDM_PYTHON=PASS"); print(sys.executable); print(sys.version.split()[0]); print(torch.__version__); print(numpy.__version__)'
        $Output = & $Python -c $Code 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        return (($Output -join [Environment]::NewLine) -match "CUTSCENEAI_MDM_PYTHON=PASS")
    } catch {
        return $false
    } finally {
        Pop-Location
    }
}

function Find-MdmPython {
    param([string]$SourceRoot, [string]$Base)

    if (-not [string]::IsNullOrWhiteSpace($MdmPython)) {
        $Candidate = (Resolve-Path -LiteralPath $MdmPython).Path
        if (-not (Test-MdmPython -Python $Candidate -SourceRoot $SourceRoot)) {
            throw "The supplied MDM Python cannot import the retained MDM runtime: $Candidate"
        }
        return $Candidate
    }

    $Candidates = [System.Collections.Generic.List[string]]::new()

    foreach ($Fixed in @(
        (Join-Path $Base "models\mdm\.venv\Scripts\python.exe"),
        (Join-Path $Base "models\mdm\.venv310\Scripts\python.exe"),
        (Join-Path $Base "environments\mdm\Scripts\python.exe"),
        (Join-Path $Base "environments\mdm\python.exe")
    )) {
        if ((Test-Path -LiteralPath $Fixed) -and -not $Candidates.Contains($Fixed)) {
            $Candidates.Add($Fixed)
        }
    }

    foreach ($SearchRoot in @(
        (Join-Path $Base "environments"),
        (Join-Path $Base "models\mdm")
    )) {
        if (-not (Test-Path -LiteralPath $SearchRoot)) {
            continue
        }
        foreach ($Item in Get-ChildItem -LiteralPath $SearchRoot -Filter "python.exe" -File -Recurse -ErrorAction SilentlyContinue) {
            if (-not $Candidates.Contains($Item.FullName)) {
                $Candidates.Add($Item.FullName)
            }
        }
    }

    foreach ($Candidate in $Candidates) {
        Write-Host "Testing MDM Python candidate:"
        Write-Host "  $Candidate"
        if (Test-MdmPython -Python $Candidate -SourceRoot $SourceRoot) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }

    throw @"
The retained MDM Python environment could not be discovered.

No reinstall was attempted. The model/runtime handoff records that MDM was previously validated.
Locate its existing Python executable and rerun with -MdmPython "E:\...\python.exe".
"@
}

function Get-GitRevision {
    param([string]$Root)

    if (-not (Test-Path -LiteralPath (Join-Path $Root ".git"))) {
        return "unknown"
    }

    Push-Location $Root
    try {
        $Value = (& git rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Value)) {
            return "unknown"
        }
        return $Value.Trim()
    } finally {
        Pop-Location
    }
}

Write-Section "CutSceneAI MDM Body Provider Preflight"

Require-Path -Path $RepoRoot -Description "CutSceneAI repository"
Require-Path -Path $ResearchRoot -Description "CutSceneAI research root"

$ProviderWrapper = Join-Path $RepoRoot "tools\providers\mdm_humanml_provider.py"
Require-Path -Path $ProviderWrapper -Description "CutSceneAI MDM provider wrapper"

$Checkpoint = Join-Path $ResearchRoot "models\mdm\checkpoints\humanml-encoder-512-50steps\model000750000.pt"
$ArgsJson = Join-Path $ResearchRoot "models\mdm\checkpoints\humanml-encoder-512-50steps\args.json"
$ClipPath = Join-Path $ResearchRoot "cache\clip\ViT-B-32.pt"
$RuntimeManifest = Join-Path $ResearchRoot "environments\manifests\mdm-runtime-assets.json"

Require-Path -Path $Checkpoint -Description "Validated MDM checkpoint"
Require-Path -Path $ArgsJson -Description "MDM checkpoint args.json"
Require-Path -Path $RuntimeManifest -Description "MDM runtime manifest"

Write-Host "Verifying retained MDM checkpoint SHA-256..."
$CheckpointHash = (Get-FileHash -LiteralPath $Checkpoint -Algorithm SHA256).Hash.ToLowerInvariant()

if ($CheckpointHash -ne $ExpectedCheckpointSha256) {
    throw @"
MDM checkpoint hash mismatch.

Expected:
$ExpectedCheckpointSha256

Actual:
$CheckpointHash

The retained research checkpoint must not be substituted silently.
"@
}

if (Test-Path -LiteralPath $ClipPath) {
    Write-Host "Verifying retained CLIP SHA-256..."
    $ClipHash = (Get-FileHash -LiteralPath $ClipPath -Algorithm SHA256).Hash.ToLowerInvariant()

    if ($ClipHash -ne $ExpectedClipSha256) {
        throw @"
CLIP ViT-B/32 hash mismatch.

Expected:
$ExpectedClipSha256

Actual:
$ClipHash
"@
    }
}

$SourceRoot = Find-MdmSourceRoot -Base $ResearchRoot
$Python = Find-MdmPython -SourceRoot $SourceRoot -Base $ResearchRoot
$GitRevision = Get-GitRevision -Root $SourceRoot

$RevisionSuffix = if ($GitRevision -eq "unknown") {
    "source-unrecorded"
} else {
    $GitRevision.Substring(0, [Math]::Min(12, $GitRevision.Length))
}
$ProviderRevision = "mdm-$($CheckpointHash.Substring(0,12))-$RevisionSuffix"

Write-Host ""
Write-Host "Retained MDM runtime:"
Write-Host " Source root:        $SourceRoot"
Write-Host " Python:             $Python"
Write-Host " Checkpoint:         $Checkpoint"
Write-Host " Checkpoint SHA-256: $CheckpointHash"
Write-Host " Source revision:    $GitRevision"
Write-Host " Provider revision:  $ProviderRevision"
Write-Host " HumanML FPS:        20"

$Previous = @{
    CUTSCENEAI_MDM_ROOT = $env:CUTSCENEAI_MDM_ROOT
    CUTSCENEAI_MDM_CHECKPOINT = $env:CUTSCENEAI_MDM_CHECKPOINT
    CUTSCENEAI_MDM_CHECKPOINT_SHA256 = $env:CUTSCENEAI_MDM_CHECKPOINT_SHA256
    CUTSCENEAI_MDM_REVISION = $env:CUTSCENEAI_MDM_REVISION
}

try {
    $env:CUTSCENEAI_MDM_ROOT = $SourceRoot
    $env:CUTSCENEAI_MDM_CHECKPOINT = $Checkpoint
    $env:CUTSCENEAI_MDM_CHECKPOINT_SHA256 = $CheckpointHash
    $env:CUTSCENEAI_MDM_REVISION = $ProviderRevision

    $HealthOutput = & $Python $ProviderWrapper --health 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw @"
The retained MDM provider health probe failed.

$($HealthOutput -join [Environment]::NewLine)

No model reinstall was attempted and .env.local was not changed.
"@
    }

    try {
        $Health = ($HealthOutput -join [Environment]::NewLine) | ConvertFrom-Json
    } catch {
        throw "MDM provider health probe did not return valid JSON: $HealthOutput"
    }

    if ($Health.status -ne "ready") {
        throw "MDM provider health status was '$($Health.status)', not 'ready'."
    }
} finally {
    foreach ($Name in $Previous.Keys) {
        [Environment]::SetEnvironmentVariable($Name, $Previous[$Name], "Process")
    }
}

Write-Host ""
Write-Host "MDM provider health:"
Write-Host " Status:         $($Health.status)"
Write-Host " CUDA available: $($Health.cuda_available)"
Write-Host " CUDA device:    $($Health.cuda_device)"
Write-Host " Torch:          $($Health.torch_version)"
Write-Host " NumPy:          $($Health.numpy_version)"

if ($WriteEnvironment) {
    $EnvFile = Join-Path $RepoRoot ".env.local"
    $Lines = [System.Collections.Generic.List[string]]::new()

    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($Line in Get-Content -LiteralPath $EnvFile) {
            $Lines.Add($Line)
        }
    }

    $ProviderCommand = @($Python, $ProviderWrapper) | ConvertTo-Json -Compress
    $HealthCommand = @($Python, $ProviderWrapper, "--health") | ConvertTo-Json -Compress

    foreach ($Name in @(
        "CUTSCENEAI_BODY_PROVIDER_URL",
        "CUTSCENEAI_BODY_PROVIDER_HEALTH_URL",
        "CUTSCENEAI_BODY_PROVIDER_TOKEN"
    )) {
        Remove-DotEnvValue -Lines $Lines -Name $Name
    }

    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER" -Value "mdm-local"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL" -Value "humanml-encoder-512-50steps"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL_REVISION" -Value $ProviderRevision
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_DETERMINISTIC" -Value "false"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_COMMAND" -Value $ProviderCommand
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_HEALTH_COMMAND" -Value $HealthCommand
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS" -Value "1200"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_HEALTH_TIMEOUT_SECONDS" -Value "30"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MAX_CONCURRENCY" -Value "1"

    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_ROOT" -Value $SourceRoot
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_CHECKPOINT" -Value $Checkpoint
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_CHECKPOINT_SHA256" -Value $CheckpointHash
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_REVISION" -Value $ProviderRevision
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_MAX_DURATION_SECONDS" -Value "9.8"

    if ([string]::IsNullOrWhiteSpace($Device)) {
        Remove-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_DEVICE"
    } else {
        Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_MDM_DEVICE" -Value $Device
    }

    [IO.File]::WriteAllLines($EnvFile, $Lines)

    Write-Host ""
    Write-Host "CUTSCENEAI_MDM_ENV=WRITTEN"
    Write-Host "Environment file: $EnvFile"
    Write-Host "Existing unrelated entries and secrets were preserved."
}

Write-Host ""
Write-Host "CUTSCENEAI_MDM_PREFLIGHT=PASS"

if (-not $WriteEnvironment) {
    Write-Host ""
    Write-Host "Preflight passed. Rerun with -WriteEnvironment to activate MDM in Studio."
} else {
    Write-Host ""
    Write-Host "MDM is configured for CutSceneAI Studio."
    Write-Host "Restart Studio so the backend reloads .env.local."
}
