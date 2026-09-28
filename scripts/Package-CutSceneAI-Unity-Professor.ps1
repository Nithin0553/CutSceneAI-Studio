[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepoRoot "build\professor-submission"
}

$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
$RequiredDirectories = @("Assets", "Packages", "ProjectSettings")

foreach ($Name in $RequiredDirectories) {
    $Candidate = Join-Path $ProjectPath $Name
    if (-not (Test-Path -LiteralPath $Candidate -PathType Container)) {
        throw "Not a valid Unity project root. Missing directory: $Candidate"
    }
}

$ProjectVersionPath = Join-Path $ProjectPath "ProjectSettings\ProjectVersion.txt"
if (-not (Test-Path -LiteralPath $ProjectVersionPath -PathType Leaf)) {
    throw "Not a valid Unity project root. Missing ProjectSettings\ProjectVersion.txt"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

$ProjectName = Split-Path -Leaf $ProjectPath
$SafeProjectName = ($ProjectName -replace '[^A-Za-z0-9._-]', '-').Trim('-')
if ([string]::IsNullOrWhiteSpace($SafeProjectName)) {
    $SafeProjectName = "UnityProject"
}

$ZipName = "CutSceneAI-Unity-Professor-v0.1-$SafeProjectName.zip"
$ZipPath = Join-Path $OutputDirectory $ZipName
$HashPath = "$ZipPath.sha256.txt"
$ManifestPath = Join-Path $OutputDirectory "CutSceneAI-Unity-Professor-v0.1-manifest.json"

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
if (Test-Path -LiteralPath $HashPath) {
    Remove-Item -LiteralPath $HashPath -Force
}

$UnityVersionLine = (Get-Content -LiteralPath $ProjectVersionPath -ErrorAction Stop |
    Where-Object { $_ -match '^m_EditorVersion:' } |
    Select-Object -First 1)

$UnityVersion = if ($UnityVersionLine) {
    ($UnityVersionLine -split ':', 2)[1].Trim()
} else {
    "unknown"
}

$GitBranch = "unknown"
$GitCommit = "unknown"
try {
    $GitBranch = (& git -C $RepoRoot branch --show-current 2>$null).Trim()
    $GitCommit = (& git -C $RepoRoot rev-parse HEAD 2>$null).Trim()
} catch {
    # Packaging does not require Git to be available.
}

$Files = New-Object System.Collections.Generic.List[object]
$TotalBytes = [int64]0

foreach ($TopLevel in $RequiredDirectories) {
    $Root = Join-Path $ProjectPath $TopLevel
    Get-ChildItem -LiteralPath $Root -Recurse -Force -File | ForEach-Object {
        if ($_.Name -in @(".DS_Store", "Thumbs.db")) {
            return
        }

        $Relative = [System.IO.Path]::GetRelativePath($ProjectPath, $_.FullName)
        $Files.Add([pscustomobject]@{
            FullName = $_.FullName
            RelativePath = $Relative.Replace("\", "/")
            Length = $_.Length
        })
        $TotalBytes += $_.Length
    }
}

if ($Files.Count -eq 0) {
    throw "No Unity project source files were found."
}

$Manifest = [ordered]@{
    package_version = "0.1"
    created_at_utc = [DateTime]::UtcNow.ToString("o")
    project_name = $ProjectName
    unity_version = $UnityVersion
    cutsceneai_branch = $GitBranch
    cutsceneai_commit = $GitCommit
    included_roots = $RequiredDirectories
    excluded_generated_roots = @(
        "Library",
        "Temp",
        "Logs",
        "obj",
        "Build",
        "Builds",
        ".vs",
        ".idea",
        ".vscode"
    )
    file_count = $Files.Count
    uncompressed_bytes = $TotalBytes
    note = "Open the extracted folder in Unity Hub. CutSceneAI source is distributed separately from the GitHub Cutsceneai_test-v.1 branch."
}

$ManifestJson = $Manifest | ConvertTo-Json -Depth 6
Set-Content -LiteralPath $ManifestPath -Value $ManifestJson -Encoding UTF8

$PackageReadme = @"
CutSceneAI Unity Professor Package v0.1
=======================================

This archive contains only the Unity project source required to reopen the project:
- Assets/
- Packages/
- ProjectSettings/

It intentionally excludes generated/local folders such as:
Library/, Temp/, Logs/, obj/, Build/, Builds/, IDE settings, and caches.

Unity version recorded by the project:
$UnityVersion

CutSceneAI source branch:
$GitBranch

CutSceneAI source commit:
$GitCommit

Professor setup:
1. Extract this ZIP to a normal local folder.
2. Open the extracted project folder in Unity Hub using the recorded Unity version when available.
3. Clone the CutSceneAI repository branch Cutsceneai_test-v.1 separately.
4. Start CutSceneAI Studio with scripts\Start-CutSceneAI-Studio.ps1.
5. In Studio, connect this extracted Unity project.
6. Choose Install bridge.
7. Keep the backend and Unity open on the same computer so the bridge can reach http://127.0.0.1:8000.
8. Follow PROFESSOR_TEST_GUIDE.md in the CutSceneAI repository.
"@

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$FileStream = [System.IO.File]::Open(
    $ZipPath,
    [System.IO.FileMode]::Create,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
)

try {
    $Archive = New-Object System.IO.Compression.ZipArchive(
        $FileStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )

    try {
        foreach ($File in $Files) {
            $EntryName = "$SafeProjectName/$($File.RelativePath)"
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $Archive,
                $File.FullName,
                $EntryName,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }

        $ReadmeEntry = $Archive.CreateEntry(
            "$SafeProjectName/PROFESSOR_PACKAGE_README.txt",
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        $Writer = New-Object System.IO.StreamWriter($ReadmeEntry.Open())
        try {
            $Writer.Write($PackageReadme)
        } finally {
            $Writer.Dispose()
        }

        $ManifestEntry = $Archive.CreateEntry(
            "$SafeProjectName/CUTSCENEAI_PACKAGE_MANIFEST.json",
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        $Writer = New-Object System.IO.StreamWriter($ManifestEntry.Open())
        try {
            $Writer.Write($ManifestJson)
        } finally {
            $Writer.Dispose()
        }
    } finally {
        $Archive.Dispose()
    }
} finally {
    $FileStream.Dispose()
}

$Hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $ZipName" | Set-Content -LiteralPath $HashPath -Encoding ASCII

$ZipItem = Get-Item -LiteralPath $ZipPath

Write-Host ""
Write-Host "============================================================"
Write-Host " CUTSCENEAI PROFESSOR UNITY PACKAGE READY"
Write-Host "============================================================"
Write-Host ""
Write-Host "Unity project: $ProjectPath"
Write-Host "Unity version: $UnityVersion"
Write-Host "Files packed: $($Files.Count)"
Write-Host "ZIP: $ZipPath"
Write-Host "ZIP size: $($ZipItem.Length) bytes"
Write-Host "SHA-256: $Hash"
Write-Host "Hash file: $HashPath"
Write-Host "Manifest: $ManifestPath"
Write-Host ""
Write-Host "Upload the ZIP and .sha256.txt file to the professor submission Drive folder."
