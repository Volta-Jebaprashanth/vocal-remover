<#
.SYNOPSIS
  Builds Vocal Remover (onedir), packages it with Inno Setup, tags the repo, and
  publishes a GitHub Release with the installer attached -- one command.

.EXAMPLE
  .\scripts\release.ps1 -Version 1.0.0
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Resolve-Tool($Name, $Candidates) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($path in $Candidates) {
        if (Test-Path $path) { return $path }
    }
    throw "Could not find $Name. Looked on PATH and: $($Candidates -join ', ')"
}

$Iscc = Resolve-Tool "ISCC.exe" @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$Gh = Resolve-Tool "gh.exe" @(
    "C:\Program Files\GitHub CLI\gh.exe"
)

Write-Host "== 1/5: cleaning old build/dist ==" -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "== 2/5: pyinstaller (onedir) ==" -ForegroundColor Cyan
& ".\venv\Scripts\pyinstaller.exe" build.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "== 3/5: Inno Setup installer ==" -ForegroundColor Cyan
& $Iscc "installer.iss" "/DMyAppVersion=$Version"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }

$InstallerPath = "dist\installer\VocalRemoverSetup-$Version.exe"
if (-not (Test-Path $InstallerPath)) { throw "Expected installer not found at $InstallerPath" }

Write-Host "== 4/5: tagging v$Version ==" -ForegroundColor Cyan
git tag "v$Version"
git push origin "v$Version"

Write-Host "== 5/5: publishing GitHub release ==" -ForegroundColor Cyan
& $Gh release create "v$Version" $InstallerPath `
    --title "Vocal Remover v$Version" `
    --notes "Vocal Remover v$Version. Download VocalRemoverSetup-$Version.exe and run it -- no Python or ffmpeg install needed. Separation models download automatically the first time you use each mode (needs an internet connection once per mode)."

Write-Host "`nDone. Installer: $InstallerPath" -ForegroundColor Green
