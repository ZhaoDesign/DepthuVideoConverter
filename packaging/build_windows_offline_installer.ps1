# build_windows_offline_installer.ps1
# Builds a self-contained Windows installer with bundled Python runtime and all dependencies.
# No internet connection required at install time.

param(
    [switch]$SkipRuntimeBuild,
    [switch]$Clean,
    [string]$AppVersion = "0.1.0"
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectRoot = Split-Path -Parent $ScriptDir
$BuildDir = Join-Path $ProjectRoot "build"
$RuntimeDir = Join-Path $BuildDir "runtime"
$CacheDir = Join-Path $BuildDir "cache"

$PythonVersion = "3.11.9"
$PythonZipUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$PythonZipFile = Join-Path $CacheDir "python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipFile = Join-Path $CacheDir "get-pip.py"
$RequirementsFile = Join-Path $ProjectRoot "packaging\windows-web-installer\runtime-requirements-cpu.txt"
$VerifyScript = Join-Path $ProjectRoot "packaging\windows-web-installer\verify_runtime.py"
$IssFile = Join-Path $ProjectRoot "packaging\windows-offline-installer\ContourControlToolSetup.iss"

# --- Find ISCC.exe ---
$IsccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $null
foreach ($p in $IsccPaths) {
    if (Test-Path $p) { $Iscc = $p; break }
}
if (-not $Iscc) {
    $Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $Iscc) {
    Write-Error "Inno Setup 6 (ISCC.exe) not found. Please install from https://jrsoftware.org/isdl.php"
    exit 1
}
Write-Host "[OK] ISCC.exe: $Iscc" -ForegroundColor Green

# --- Clean build directory ---
if ($Clean -and (Test-Path $BuildDir)) {
    Write-Host "Cleaning build directory..."
    Remove-Item -Recurse -Force $BuildDir
}

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

if (-not $SkipRuntimeBuild) {
    # --- Remove old runtime build ---
    if (Test-Path $RuntimeDir) {
        Write-Host "Removing previous runtime build..."
        Remove-Item -Recurse -Force $RuntimeDir
    }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

    # --- Download Python embed ---
    if (-not (Test-Path $PythonZipFile)) {
        Write-Host "Downloading Python $PythonVersion embed..."
        curl.exe -L --retry 3 -o $PythonZipFile $PythonZipUrl
        if ($LASTEXITCODE -ne 0) { throw "Failed to download Python embed zip" }
    } else {
        Write-Host "[cached] Python embed zip"
    }

    # --- Extract Python ---
    Write-Host "Extracting Python runtime..."
    Expand-Archive -LiteralPath $PythonZipFile -DestinationPath $RuntimeDir -Force

    # --- Configure ._pth ---
    Write-Host "Configuring Python path..."
    $pthFile = Join-Path $RuntimeDir "python311._pth"
    @("python311.zip", ".", "Lib\site-packages", "import site") | Set-Content -LiteralPath $pthFile -Encoding ASCII
    New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir "Lib\site-packages") | Out-Null

    # --- Install pip ---
    if (-not (Test-Path $GetPipFile)) {
        Write-Host "Downloading get-pip.py..."
        curl.exe -L --retry 3 -o $GetPipFile $GetPipUrl
        if ($LASTEXITCODE -ne 0) { throw "Failed to download get-pip.py" }
    } else {
        Write-Host "[cached] get-pip.py"
    }

    $pythonExe = Join-Path $RuntimeDir "python.exe"
    Write-Host "Installing pip..."
    & $pythonExe $GetPipFile --no-warn-script-location 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "pip installation failed" }

    # --- Install dependencies ---
    Write-Host "Installing dependencies (this may take a few minutes)..."
    $attempts = 0
    $maxAttempts = 3
    $success = $false
    # Use Tsinghua mirror for faster downloads in China
    $pipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"
    while (-not $success -and $attempts -lt $maxAttempts) {
        $attempts++
        if ($attempts -gt 1) {
            Write-Host "Retry attempt $attempts of $maxAttempts..."
            Start-Sleep -Seconds 5
        }
        # Remove --no-cache-dir to reuse downloads on retry
        & $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location --retries 10 --timeout 300 --index-url $pipIndex -r $RequirementsFile 2>&1 | Write-Host
        if ($LASTEXITCODE -eq 0) {
            $success = $true
        }
    }
    if (-not $success) { throw "Dependency installation failed after $maxAttempts attempts" }

    # --- Verify runtime ---
    Write-Host "Verifying runtime..."
    $appDir = Join-Path $ProjectRoot "."
    & $pythonExe $VerifyScript $appDir 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "Runtime verification failed" }

    Write-Host "[OK] Runtime build complete" -ForegroundColor Green
}

# --- Get runtime size ---
$runtimeSize = (Get-ChildItem -Recurse $RuntimeDir | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ("Runtime size: {0:N0} MB (uncompressed)" -f $runtimeSize)

# --- Compile installer ---
Write-Host "Compiling Inno Setup installer..."
$env:APP_VERSION = $AppVersion
& $Iscc $IssFile
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

$outputExe = Join-Path $ProjectRoot "dist\windows-installer\ContourControlTool-Windows-x64-OfflineSetup.exe"
if (Test-Path $outputExe) {
    $exeSize = (Get-Item $outputExe).Length / 1MB
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " Build successful!" -ForegroundColor Green
    Write-Host " Output: $outputExe" -ForegroundColor Green
    Write-Host (" Size:   {0:N1} MB" -f $exeSize) -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
} else {
    throw "Output file not found: $outputExe"
}
