param(
    [string]$OutputDir = "",
    [string]$AppVersion = "0.1.0",
    [string]$ISCC = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$InstallerDir = Join-Path $Root "packaging\windows-web-installer"
$ScriptPath = Join-Path $InstallerDir "ContourControlToolSetup.iss"

if ($OutputDir -ne "") {
    $DistDir = [System.IO.Path]::GetFullPath($OutputDir)
}
else {
    $DistDir = Join-Path $Root "dist\windows-installer"
}
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

if ($ISCC -eq "") {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $ISCC = $candidate
            break
        }
    }
}

if ($ISCC -eq "") {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        $ISCC = $command.Source
    }
}

if ($ISCC -eq "") {
    throw "ISCC.exe was not found. Install Inno Setup 6 first, or pass -ISCC with the full path to ISCC.exe."
}

$env:APP_VERSION = $AppVersion
$isccArgs = @("/O$DistDir", $ScriptPath)
& $ISCC @isccArgs
if ($LASTEXITCODE -ne 0) {
    throw "Installer compilation failed."
}

Get-ChildItem -LiteralPath $DistDir -Filter "*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 FullName, Length, LastWriteTime
