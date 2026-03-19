param(
    [string]$Python = "python",
    [string]$IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

& $Python -m pip install -e "$projectRoot[build]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m PyInstaller --noconfirm "$projectRoot\py-network-launcher.spec"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $IsccPath "$projectRoot\installer\py-network-launcher.iss"
exit $LASTEXITCODE
