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
$RuntimeDir = Join-Path $BuildDir "runtime-cuda"
$CacheDir = Join-Path $BuildDir "cache"

$PythonVersion = "3.11.9"
$PythonZipUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$PythonZipFile = Join-Path $CacheDir "python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipFile = Join-Path $CacheDir "get-pip.py"
$TorchWheelName = "torch-2.13.0+cu126-cp311-cp311-win_amd64.whl"
$TorchWheelUrls = @(
    "https://download-r2.pytorch.org/whl/cu126/torch-2.13.0%2Bcu126-cp311-cp311-win_amd64.whl",
    "https://download.pytorch.org/whl/cu126/torch-2.13.0%2Bcu126-cp311-cp311-win_amd64.whl"
)
$TorchWheelLength = 2594548547
$TorchWheelSha256 = "8095729db14e7fd5178a39676fdd679208eff4041407ea34e3d898336c90f5c5"
$RequirementsFile = Join-Path $ProjectRoot "packaging\windows-web-installer\runtime-requirements-cuda.txt"
$pipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"
$ModelsDir = Join-Path $BuildDir "models"
$HfMirror = if ([string]::IsNullOrWhiteSpace($env:HF_MIRROR)) {
    "https://hf-mirror.com"
} else {
    $env:HF_MIRROR.TrimEnd("/")
}
$BundledModels = @(
    @{
        Label = "Small (fastest, ~99 MB)"
        FileName = "depth_anything_v2_vits.pth"
        CacheFile = "depth_anything_v2_vits.pth"
        Repo = "depth-anything/Depth-Anything-V2-Small"
    },
    @{
        Label = "Base (balanced, ~392 MB)"
        FileName = "depth_anything_v2_vitb.pth"
        CacheFile = "depth_anything_v2_vitb.pth"
        Repo = "depth-anything/Depth-Anything-V2-Base"
    }
)
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

function Test-DownloadedFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][long]$ExpectedLength,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $length = (Get-Item -LiteralPath $Path).Length
    if ($length -ne $ExpectedLength) {
        return $false
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    return $hash.Equals($ExpectedSha256, [System.StringComparison]::OrdinalIgnoreCase)
}

function Invoke-ResumableDownload {
    param(
        [Parameter(Mandatory = $true)][string[]]$Urls,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][long]$ExpectedLength,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    if (Test-DownloadedFile -Path $Destination -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256) {
        Write-Host "[cached] verified CUDA PyTorch wheel"
        return
    }
    if (Test-DownloadedFile -Path "$Destination.part" -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256) {
        Move-Item -LiteralPath "$Destination.part" -Destination $Destination -Force
        Write-Host "[cached] verified completed CUDA PyTorch partial download"
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }

    $partial = "$Destination.part"
    foreach ($url in $Urls) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            Write-Host ("Downloading CUDA PyTorch wheel (attempt {0}/10): {1}" -f $attempt, $url)
            & curl.exe -L --fail --retry 3 --retry-delay 5 --retry-all-errors --continue-at - -o $partial $url
            if (Test-DownloadedFile -Path $partial -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256) {
                Move-Item -LiteralPath $partial -Destination $Destination -Force
                Write-Host "CUDA PyTorch wheel download and hash verification completed."
                return
            }
            if (Test-Path -LiteralPath $partial) {
                $partialLength = (Get-Item -LiteralPath $partial).Length
                if ($partialLength -gt $ExpectedLength) {
                    Remove-Item -LiteralPath $partial -Force
                }
            }
            Start-Sleep -Seconds 5
        }
    }

    throw "CUDA PyTorch wheel download failed or hash verification failed."
}

function Get-ModelUrls {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string]$FileName
    )

    $hfPath = "$Repo/resolve/main/$FileName"
    return @(
        "$HfMirror/$hfPath",
        "https://huggingface.co/$hfPath",
        "https://mirror.ghproxy.com/https://huggingface.co/$hfPath"
    )
}

function Test-TorchCheckpoint {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $checker = Join-Path $CacheDir "verify_torch_checkpoint.py"
    if (-not (Test-Path -LiteralPath $checker)) {
        @'
import sys
import torch

try:
    torch.load(sys.argv[1], map_location="cpu", weights_only=True)
except TypeError:
    torch.load(sys.argv[1], map_location="cpu")
'@ | Set-Content -LiteralPath $checker -Encoding ASCII
    }

    $stamp = [Guid]::NewGuid().ToString("N")
    $stdout = Join-Path $CacheDir "verify_torch_checkpoint_$stamp.out"
    $stderr = Join-Path $CacheDir "verify_torch_checkpoint_$stamp.err"
    try {
        $proc = Start-Process -FilePath $PythonExe -ArgumentList @($checker, $Path) -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        return ($proc.ExitCode -eq 0)
    } finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Install-BundledModel {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$CachePath
    )

    $minBytes = 1000000
    if ((Test-Path -LiteralPath $Destination) -and ((Get-Item -LiteralPath $Destination).Length -gt $minBytes) -and (Test-TorchCheckpoint -PythonExe $PythonExe -Path $Destination)) {
        Write-Host "[cached] $Label"
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }

    if ((Test-Path -LiteralPath $CachePath) -and ((Get-Item -LiteralPath $CachePath).Length -gt $minBytes) -and (Test-TorchCheckpoint -PythonExe $PythonExe -Path $CachePath)) {
        Copy-Item -LiteralPath $CachePath -Destination $Destination -Force
        Write-Host "[cached] $Label from build cache"
        return
    }
    if (Test-Path -LiteralPath $CachePath) {
        Remove-Item -LiteralPath $CachePath -Force
    }

    Write-Host "Downloading $Label..."
    foreach ($url in (Get-ModelUrls -Repo $Repo -FileName $FileName)) {
        Write-Host "  -> $url"
        $tmp = "$Destination.tmp"
        try {
            if (Test-Path -LiteralPath $tmp) {
                Remove-Item -LiteralPath $tmp -Force
            }
            curl.exe -L --retry 3 --retry-delay 5 --retry-all-errors -o $tmp $url
            if ($LASTEXITCODE -ne 0) { throw "download failed" }
            if (-not (Test-TorchCheckpoint -PythonExe $PythonExe -Path $tmp)) {
                throw "checkpoint verification failed"
            }
            Move-Item -LiteralPath $tmp -Destination $Destination -Force
            Copy-Item -LiteralPath $Destination -Destination $CachePath -Force
            return
        } catch {
            Write-Host "  !! download failed, trying next source..."
            if (Test-Path -LiteralPath $tmp) {
                Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            }
        }
    }

    throw "Failed to download the $Label."
}

function Remove-NonRuntimeFiles {
    param([Parameter(Mandatory = $true)][string]$Root)

    $sitePackages = Join-Path $Root "Lib\site-packages"
    $removeExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($extension in @(".pyc", ".pyo", ".pdb", ".lib", ".h", ".hpp", ".hxx", ".cuh", ".pyi")) {
        [void]$removeExtensions.Add($extension)
    }

    $files = Get-ChildItem -LiteralPath $sitePackages -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $removeExtensions.Contains($_.Extension) }
    foreach ($file in $files) {
        Remove-Item -LiteralPath $file.FullName -Force -ErrorAction SilentlyContinue
    }

    $thirdPartyLicenseDirs = Get-ChildItem -LiteralPath $sitePackages -Recurse -Directory -Filter "third_party" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\.dist-info\\licenses\\third_party$' }
    foreach ($directory in $thirdPartyLicenseDirs) {
        Remove-Item -LiteralPath $directory.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }

    $directories = Get-ChildItem -LiteralPath $Root -Recurse -Directory -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending
    foreach ($directory in $directories) {
        if (-not (Get-ChildItem -LiteralPath $directory.FullName -Force -ErrorAction SilentlyContinue | Select-Object -First 1)) {
            Remove-Item -LiteralPath $directory.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

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

    $torchWheel = Join-Path $CacheDir $TorchWheelName
    Write-Host "Downloading CUDA PyTorch wheel with resume support..."
    Invoke-ResumableDownload -Urls $TorchWheelUrls -Destination $torchWheel -ExpectedLength $TorchWheelLength -ExpectedSha256 $TorchWheelSha256

    Write-Host "Installing CUDA PyTorch wheel..."
    & $pythonExe -m pip install --no-compile --disable-pip-version-check --no-warn-script-location --index-url "https://download.pytorch.org/whl/cu126" --extra-index-url $pipIndex $torchWheel 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "CUDA PyTorch installation failed" }

    # --- Install dependencies ---
    Write-Host "Installing dependencies (this may take a few minutes)..."
    $attempts = 0
    $maxAttempts = 3
    $success = $false
    # Use Tsinghua mirror for faster downloads in China
    while (-not $success -and $attempts -lt $maxAttempts) {
        $attempts++
        if ($attempts -gt 1) {
            Write-Host "Retry attempt $attempts of $maxAttempts..."
            Start-Sleep -Seconds 5
        }
        # Remove --no-cache-dir to reuse downloads on retry
        & $pythonExe -m pip install --no-compile --disable-pip-version-check --no-warn-script-location --retries 10 --timeout 300 --index-url "https://download.pytorch.org/whl/cu126" --extra-index-url $pipIndex -r $RequirementsFile 2>&1 | Write-Host
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

if (-not (Test-Path $RuntimeDir)) {
    throw "CUDA runtime build is missing. Run this script without -SkipRuntimeBuild first."
}

$pythonExe = Join-Path $RuntimeDir "python.exe"
$appDir = Join-Path $ProjectRoot "."

Write-Host "Preparing runtime bundle for installer..."
Remove-NonRuntimeFiles -Root $RuntimeDir
Write-Host "Verifying runtime after cleanup..."
& $pythonExe $VerifyScript $appDir 2>&1 | Write-Host
if ($LASTEXITCODE -ne 0) { throw "Runtime verification failed after cleanup" }
Remove-NonRuntimeFiles -Root $RuntimeDir

# --- Download bundled PyTorch models ---
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
foreach ($model in $BundledModels) {
    $modelFile = Join-Path $ModelsDir $model.FileName
    $modelCache = Join-Path $CacheDir $model.CacheFile
    Install-BundledModel -PythonExe $pythonExe -Label $model.Label -Repo $model.Repo -FileName $model.FileName -Destination $modelFile -CachePath $modelCache
}

# --- Get runtime size ---
$runtimeSize = (Get-ChildItem -Recurse $RuntimeDir | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ("Runtime size: {0:N0} MB (uncompressed)" -f $runtimeSize)

# --- Compile installer ---
Write-Host "Compiling Inno Setup installer..."
$env:APP_VERSION = $AppVersion
& $Iscc $IssFile
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

$outputExe = Join-Path $ProjectRoot "dist\windows-installer\DepthuVideoConverter-Windows-x64-OfflineSetup.exe"
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
