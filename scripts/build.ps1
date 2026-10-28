<#
.SYNOPSIS
    Construit Py Network Launcher pour Windows : exécutable PyInstaller, archive portable,
    installateur Inno Setup et sommes de contrôle SHA-256.

.EXAMPLE
    .\scripts\build.ps1
    .\scripts\build.ps1 -Python .\.venv\Scripts\python.exe -SkipInstall
    .\scripts\build.ps1 -SkipInstaller          # sans Inno Setup

    Les fichiers produits sont placés dans dist\ :
      Py Network Launcher\                         (dossier de l'application)
      PyNetworkLauncher-<version>-portable.zip
      PyNetworkLauncher-Setup-<version>.exe
      SHA256SUMS.txt
#>
param(
    [string]$Python = "python",
    [string]$IsccPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    [switch]$SkipInstall,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$appName = "Py Network Launcher"

function Invoke-Step([string]$Title, [scriptblock]$Command) {
    Write-Host "==> $Title" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Échec : $Title (code $LASTEXITCODE)" }
}

$initFile = Join-Path $root "src\py_network_launcher\__init__.py"
$version = [regex]::Match((Get-Content $initFile -Raw), '__version__ = "([^"]+)"').Groups[1].Value
if (-not $version) { throw "Version introuvable dans $initFile" }
Write-Host "Py Network Launcher $version" -ForegroundColor Green

if (-not $SkipInstall) {
    Invoke-Step "Installation des dépendances de build" { & $Python -m pip install --disable-pip-version-check -q -e "$root[build]" }
}

Remove-Item -Recurse -Force (Join-Path $root "build"), $dist -ErrorAction SilentlyContinue

Invoke-Step "PyInstaller" { & $Python -m PyInstaller --noconfirm --clean --distpath $dist --workpath (Join-Path $root "build") (Join-Path $root "py-network-launcher.spec") }

$zip = Join-Path $dist "PyNetworkLauncher-$version-portable.zip"
Invoke-Step "Archive portable" { Compress-Archive -Path (Join-Path $dist $appName) -DestinationPath $zip -CompressionLevel Optimal -Force }

if (-not $SkipInstaller) {
    if (-not (Test-Path $IsccPath)) { throw "Inno Setup introuvable ($IsccPath). Installe-le ou utilise -SkipInstaller." }
    Invoke-Step "Installateur Inno Setup" { & $IsccPath /Q "/DAppVersion=$version" (Join-Path $root "installer\py-network-launcher.iss") }
}

$artifacts = Get-ChildItem $dist -File | Where-Object { $_.Extension -in ".zip", ".exe" }
$artifacts | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } |
    Set-Content -Encoding ascii (Join-Path $dist "SHA256SUMS.txt")

Write-Host "`nArtefacts :" -ForegroundColor Green
Get-ChildItem $dist -File | ForEach-Object { "  {0,-45} {1,8:N1} Mo" -f $_.Name, ($_.Length / 1MB) }
