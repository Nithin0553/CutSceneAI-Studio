[CmdletBinding()]
param(
    [string]$RepoRoot = "D:\Research\CutSceneAI Foundation v0.1\cutscene-ai",
    [string]$ResearchRoot = "E:\CutSceneAI-Research",
    [string]$MdmRoot = "E:\CutSceneAI-Research\source\motion-diffusion-model",
    [string]$MdmPythonWsl = "/mnt/e/CutSceneAI-Research/environments/conda-envs/mdm-py38/bin/python",
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

function Convert-ToWslPath {
    param([string]$WindowsPath)

    $Output = & wsl.exe -e wslpath -a -u $WindowsPath 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($Output -join ""))) {
        $Detail = $Output -join [Environment]::NewLine
        throw "WSL could not convert Windows path: $WindowsPath. $Detail"
    }
    return ($Output -join "").Trim()
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

Write-Section "CutSceneAI MDM Body Provider Preflight (WSL)"

if ($null -eq (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "wsl.exe was not found. This configuration requires the validated WSL MDM runtime."
}

Require-Path -Path $RepoRoot -Description "CutSceneAI repository"
Require-Path -Path $ResearchRoot -Description "CutSceneAI research root"
Require-Path -Path $MdmRoot -Description "MDM source root"
Require-Path -Path (Join-Path $MdmRoot "sample\generate.py") -Description "MDM sample.generate"

$ProviderWrapper = Join-Path $RepoRoot "tools\providers\mdm_humanml_provider.py"
$Checkpoint = Join-Path $ResearchRoot "models\mdm\checkpoints\humanml-encoder-512-50steps\model000750000.pt"
$ArgsJson = Join-Path $ResearchRoot "models\mdm\checkpoints\humanml-encoder-512-50steps\args.json"
$ClipPath = Join-Path $ResearchRoot "cache\clip\ViT-B-32.pt"
$RuntimeManifest = Join-Path $ResearchRoot "environments\manifests\mdm-runtime-assets.json"

Require-Path -Path $ProviderWrapper -Description "CutSceneAI MDM provider wrapper"
Require-Path -Path $Checkpoint -Description "Validated MDM checkpoint"
Require-Path -Path $ArgsJson -Description "MDM checkpoint args.json"
Require-Path -Path $RuntimeManifest -Description "MDM runtime manifest"

Write-Host "Verifying retained MDM checkpoint SHA-256..."
$CheckpointHash = (Get-FileHash -LiteralPath $Checkpoint -Algorithm SHA256).Hash.ToLowerInvariant()
if ($CheckpointHash -ne $ExpectedCheckpointSha256) {
    throw "MDM checkpoint SHA-256 mismatch. Expected $ExpectedCheckpointSha256, got $CheckpointHash."
}

if (Test-Path -LiteralPath $ClipPath) {
    Write-Host "Verifying retained CLIP SHA-256..."
    $ClipHash = (Get-FileHash -LiteralPath $ClipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ClipHash -ne $ExpectedClipSha256) {
        throw "CLIP ViT-B/32 SHA-256 mismatch. Expected $ExpectedClipSha256, got $ClipHash."
    }
}

$MdmRootWsl = Convert-ToWslPath -WindowsPath $MdmRoot
$CheckpointWsl = Convert-ToWslPath -WindowsPath $Checkpoint
$ProviderWrapperWsl = Convert-ToWslPath -WindowsPath $ProviderWrapper

& wsl.exe -e test -x $MdmPythonWsl
if ($LASTEXITCODE -ne 0) {
    throw "The retained WSL MDM Python was not found or is not executable: $MdmPythonWsl"
}

& wsl.exe -e test -f "$MdmRootWsl/sample/generate.py"
if ($LASTEXITCODE -ne 0) {
    throw "WSL cannot read the MDM source checkout: $MdmRootWsl"
}

$Manifest = Get-Content -LiteralPath $RuntimeManifest -Raw | ConvertFrom-Json
$GitRevision = (& wsl.exe -e git -C $MdmRootWsl rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($GitRevision -join ""))) {
    $GitRevision = [string]$Manifest.mdm_commit
} else {
    $GitRevision = ($GitRevision -join "").Trim()
}
if ([string]::IsNullOrWhiteSpace($GitRevision) -or $GitRevision -eq "unknown") {
    throw "The MDM source revision could not be established from Git or the runtime manifest."
}
if (
    -not [string]::IsNullOrWhiteSpace([string]$Manifest.mdm_commit) -and
    $GitRevision -ne [string]$Manifest.mdm_commit
) {
    throw "MDM source revision mismatch. Manifest records $($Manifest.mdm_commit), checkout is $GitRevision."
}

$ProviderRevision = "mdm-$($CheckpointHash.Substring(0,12))-$($GitRevision.Substring(0,12))"

$ProviderEnvironment = @(
    "CUTSCENEAI_MDM_ROOT=$MdmRootWsl",
    "CUTSCENEAI_MDM_CHECKPOINT=$CheckpointWsl",
    "CUTSCENEAI_MDM_CHECKPOINT_SHA256=$CheckpointHash",
    "CUTSCENEAI_MDM_REVISION=$ProviderRevision",
    "CUTSCENEAI_MDM_MAX_DURATION_SECONDS=9.8",
    "CUTSCENEAI_MDM_INFERENCE_TIMEOUT_SECONDS=1200"
)

$ProviderArgs = @("-e", "env") + $ProviderEnvironment + @(
    $MdmPythonWsl,
    $ProviderWrapperWsl
)
$HealthArgs = $ProviderArgs + @("--health")

Write-Host ""
Write-Host "Validated WSL runtime:"
Write-Host " Source root:        $MdmRootWsl"
Write-Host " Python:             $MdmPythonWsl"
Write-Host " Checkpoint:         $CheckpointWsl"
Write-Host " Checkpoint SHA-256: $CheckpointHash"
Write-Host " Source revision:    $GitRevision"
Write-Host " Provider revision:  $ProviderRevision"
Write-Host ""
Write-Host "Checking provider health..."

$HealthOutput = & wsl.exe @HealthArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    $Detail = $HealthOutput -join [Environment]::NewLine
    throw "The retained WSL MDM provider health probe failed. $Detail"
}

try {
    $Health = ($HealthOutput -join [Environment]::NewLine) | ConvertFrom-Json
} catch {
    throw "MDM provider health probe did not return valid JSON: $($HealthOutput -join [Environment]::NewLine)"
}

if ($Health.status -ne "ready") {
    throw "MDM provider health status was '$($Health.status)', not 'ready'."
}
if ($Health.provider -ne "mdm-local" -or $Health.model -ne "humanml-encoder-512-50steps") {
    throw "MDM provider health identity did not match the expected provider/model."
}
if ($Health.model_revision -ne $ProviderRevision) {
    throw "MDM provider health revision '$($Health.model_revision)' did not match '$ProviderRevision'."
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
    $BackupDirectory = Join-Path $RepoRoot ".cutsceneai-studio\env-backups"
    if (Test-Path -LiteralPath $EnvFile) {
        New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
        $BackupPath = Join-Path $BackupDirectory ("env-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".local")
        Copy-Item -LiteralPath $EnvFile -Destination $BackupPath -Force
        Write-Host ""
        Write-Host "Preserved existing environment file:"
        Write-Host " $BackupPath"
    }

    $Lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($Line in Get-Content -LiteralPath $EnvFile) {
            $Lines.Add($Line)
        }
    }

    foreach ($Name in @(
        "CUTSCENEAI_BODY_PROVIDER_URL",
        "CUTSCENEAI_BODY_PROVIDER_HEALTH_URL",
        "CUTSCENEAI_BODY_PROVIDER_TOKEN"
    )) {
        Remove-DotEnvValue -Lines $Lines -Name $Name
    }

    $ProviderCommand = @("wsl.exe") + $ProviderArgs | ConvertTo-Json -Compress
    $HealthCommand = @("wsl.exe") + $HealthArgs | ConvertTo-Json -Compress

    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER" -Value "mdm-local"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL" -Value "humanml-encoder-512-50steps"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MODEL_REVISION" -Value $ProviderRevision
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROMPT_VERSION" -Value "body-v0.1"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_DETERMINISTIC" -Value "false"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_COMMAND" -Value $ProviderCommand
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_HEALTH_COMMAND" -Value $HealthCommand
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_TIMEOUT_SECONDS" -Value "1200"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_PROVIDER_HEALTH_TIMEOUT_SECONDS" -Value "60"
    Set-DotEnvValue -Lines $Lines -Name "CUTSCENEAI_BODY_MAX_CONCURRENCY" -Value "1"

    [IO.File]::WriteAllLines($EnvFile, $Lines)

    Write-Host ""
    Write-Host "CUTSCENEAI_MDM_WSL_ENV=WRITTEN"
    Write-Host "Environment file: $EnvFile"
    Write-Host "Existing unrelated entries and secrets were preserved."
}

Write-Host ""
Write-Host "CUTSCENEAI_MDM_WSL_PREFLIGHT=PASS"

if (-not $WriteEnvironment) {
    Write-Host ""
    Write-Host "Preflight passed. Rerun with -WriteEnvironment to activate MDM in Studio."
} else {
    Write-Host ""
    Write-Host "MDM is configured for CutSceneAI Studio through the validated WSL runtime."
    Write-Host "Restart Studio so the backend reloads .env.local."
}
