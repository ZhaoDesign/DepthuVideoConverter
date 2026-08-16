param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls13
}
catch {
    # Older Windows PowerShell builds do not expose TLS 1.3.
}

$PythonVersion = "3.11.9"
$RuntimeVersion = "2026.08.08-cuda"
$PythonZipName = "python-$PythonVersion-embed-amd64.zip"
$PythonZipUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZipName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$TorchWheelName = "torch-2.13.0+cu126-cp311-cp311-win_amd64.whl"
$TorchWheelUrls = @(
    "https://download-r2.pytorch.org/whl/cu126/torch-2.13.0%2Bcu126-cp311-cp311-win_amd64.whl",
    "https://download.pytorch.org/whl/cu126/torch-2.13.0%2Bcu126-cp311-cp311-win_amd64.whl"
)
$TorchWheelLength = 2594548547
$TorchWheelSha256 = "8095729db14e7fd5178a39676fdd679208eff4041407ea34e3d898336c90f5c5"

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$InstallerDir = Join-Path $InstallDir "installer"
$AppDir = Join-Path $InstallDir "app"
$CacheDir = Join-Path $env:TEMP "DepthuVideoConverterInstaller"
$PreferredDataDir = Join-Path $env:LOCALAPPDATA "DepthuVideoConverter"
$LegacyDataDir = Join-Path $env:LOCALAPPDATA "DepthVideoConverter"
if ((Test-Path -LiteralPath $PreferredDataDir) -or -not (Test-Path -LiteralPath $LegacyDataDir)) {
    $DataDir = $PreferredDataDir
}
else {
    $DataDir = $LegacyDataDir
}
$RuntimeRoot = Join-Path $env:LOCALAPPDATA "CCT"
$RuntimeDir = Join-Path $RuntimeRoot "rt311cuda"
$LogPath = Join-Path $DataDir "installer.log"
$MarkerPath = Join-Path $RuntimeDir ".runtime-cuda-ok"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $Message
}

function Invoke-Download {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    Write-Log "Downloading: $Url"
    $tmp = "$Destination.tmp"
    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -LiteralPath $tmp -Force
    }

    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source -L --retry 5 --retry-delay 3 --retry-all-errors -o $tmp $Url
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed: $Url"
        }
    }
    else {
        Invoke-WebRequest -Uri $Url -OutFile $tmp -Headers @{ "User-Agent" = "DepthuVideoConverterInstaller" }
    }

    Move-Item -LiteralPath $tmp -Destination $Destination -Force
}

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
        Write-Log "Using verified cached wheel: $Destination"
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }

    $partial = "$Destination.part"
    foreach ($url in $Urls) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            Write-Log ("Downloading CUDA PyTorch wheel (attempt {0}/10): {1}" -f $attempt, $url)
            & curl.exe -L --fail --retry 3 --retry-delay 5 --retry-all-errors --continue-at - -o $partial $url
            if (Test-DownloadedFile -Path $partial -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256) {
                Move-Item -LiteralPath $partial -Destination $Destination -Force
                Write-Log "CUDA PyTorch wheel download and hash verification completed."
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

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Log $Name
    & $Action
}

function ConvertTo-ProcessArgument {
    param([string]$Argument)

    if ($null -eq $Argument -or $Argument -eq "") {
        return '""'
    }
    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }
    return '"' + ($Argument -replace '"', '\"') + '"'
}

function Invoke-LoggedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = ""
    )

    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    try {
        $argumentText = ($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "
        if ($WorkingDirectory -ne "") {
            $WorkingDirectory = [System.IO.Path]::GetFullPath($WorkingDirectory)
        }
        $startInfo = @{
            FilePath = $FileName
            ArgumentList = $argumentText
            Wait = $true
            PassThru = $true
            RedirectStandardOutput = $stdout
            RedirectStandardError = $stderr
            WindowStyle = "Hidden"
        }
        if ($WorkingDirectory -ne "") {
            $startInfo["WorkingDirectory"] = $WorkingDirectory
        }
        $process = Start-Process @startInfo
        foreach ($path in @($stdout, $stderr)) {
            if (Test-Path -LiteralPath $path) {
                Get-Content -LiteralPath $path -ErrorAction SilentlyContinue | ForEach-Object {
                    if ($_ -ne "") {
                        Write-Log $_
                    }
                }
            }
        }
        return $process.ExitCode
    }
    finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-LoggedProcessWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int]$Attempts = 3,
        [int]$DelaySeconds = 10,
        [string]$WorkingDirectory = ""
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if ($Attempts -gt 1) {
            Write-Log ("Attempt {0} of {1}" -f $attempt, $Attempts)
        }
        $code = Invoke-LoggedProcess -FileName $FileName -Arguments $Arguments -WorkingDirectory $WorkingDirectory
        if ($code -eq 0) {
            return 0
        }
        if ($attempt -lt $Attempts) {
            Write-Log ("Command failed with exit code {0}. Retrying in {1} seconds..." -f $code, $DelaySeconds)
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $code
}

function Test-RuntimeReady {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$Marker
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $Marker)) {
        return $false
    }
    $markerText = Get-Content -LiteralPath $Marker -Raw -ErrorAction SilentlyContinue
    if ($markerText -notmatch [regex]::Escape("runtime_version=$RuntimeVersion")) {
        return $false
    }
    return $true
}

try {
    Write-Log "Installing runtime into: $InstallDir"
    Write-Log "Runtime path: $RuntimeDir"

    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "This installer supports Windows 64-bit only."
    }
    if (-not (Test-Path -LiteralPath $AppDir)) {
        throw "Application files are missing: $AppDir"
    }

    $pythonExe = Join-Path $RuntimeDir "python.exe"
    if (Test-RuntimeReady -PythonExe $pythonExe -Marker $MarkerPath) {
        Write-Log "Runtime is already installed. Skipping download."
        exit 0
    }
    if (Test-Path -LiteralPath $MarkerPath) {
        Write-Log "Runtime marker is missing the current runtime version. Reinstalling runtime."
    }

    if (Test-Path -LiteralPath $RuntimeDir) {
        $resolvedRuntime = [System.IO.Path]::GetFullPath($RuntimeDir)
        $resolvedRuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
        if (-not $resolvedRuntime.StartsWith($resolvedRuntimeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unexpected path: $resolvedRuntime"
        }
        Remove-Item -LiteralPath $RuntimeDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

    $pythonZip = Join-Path $CacheDir $PythonZipName
    $getPip = Join-Path $CacheDir "get-pip.py"

    Invoke-Step "Download Python runtime" {
        Invoke-Download -Url $PythonZipUrl -Destination $pythonZip
    }

    Invoke-Step "Extract Python runtime" {
        Expand-Archive -LiteralPath $pythonZip -DestinationPath $RuntimeDir -Force
    }

    Invoke-Step "Configure Python package path" {
        $pth = Join-Path $RuntimeDir "python311._pth"
        $content = @(
            "python311.zip",
            ".",
            "Lib\site-packages",
            "import site"
        )
        Set-Content -LiteralPath $pth -Value $content -Encoding ASCII
        New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir "Lib\site-packages") | Out-Null
    }

    Invoke-Step "Download pip bootstrapper" {
        Invoke-Download -Url $GetPipUrl -Destination $getPip
    }

    Invoke-Step "Install pip" {
        $code = Invoke-LoggedProcess -FileName $pythonExe -Arguments @($getPip, "--no-warn-script-location")
        if ($code -ne 0) {
            throw "pip installation failed."
        }
    }

    $torchWheel = Join-Path $CacheDir $TorchWheelName
    Invoke-Step "Download CUDA PyTorch wheel with resume support" {
        Invoke-ResumableDownload -Urls $TorchWheelUrls -Destination $torchWheel -ExpectedLength $TorchWheelLength -ExpectedSha256 $TorchWheelSha256
    }

    Invoke-Step "Install CUDA PyTorch wheel" {
        $code = Invoke-LoggedProcessWithRetry -FileName $pythonExe -Arguments @(
            "-m", "pip", "install",
            "--no-compile",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "--index-url", "https://download.pytorch.org/whl/cu126",
            "--extra-index-url", "https://pypi.tuna.tsinghua.edu.cn/simple",
            $torchWheel
        ) -Attempts 3 -DelaySeconds 15
        if ($code -ne 0) {
            throw "CUDA PyTorch installation failed."
        }
    }

    $requirements = Join-Path $InstallerDir "runtime-requirements-cuda.txt"
    Invoke-Step "Install application dependencies (CUDA PyTorch runtime)" {
        $code = Invoke-LoggedProcessWithRetry -FileName $pythonExe -Arguments @(
            "-m", "pip", "install",
            "--no-cache-dir",
            "--no-compile",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "--index-url", "https://download.pytorch.org/whl/cu126",
            "--extra-index-url", "https://pypi.tuna.tsinghua.edu.cn/simple",
            "--retries", "10",
            "--timeout", "120",
            "--resume-retries", "10",
            "-r", $requirements
        ) -Attempts 3 -DelaySeconds 15
        if ($code -ne 0) {
            throw "Dependency installation failed."
        }
    }

    $verifyScript = Join-Path $InstallerDir "verify_runtime.py"
    Invoke-Step "Verify runtime" {
        $code = Invoke-LoggedProcess -FileName $pythonExe -Arguments @($verifyScript, $AppDir)
        if ($code -ne 0) {
            throw "Runtime verification failed."
        }
    }

    Set-Content -LiteralPath $MarkerPath -Value @(
        "runtime_version=$RuntimeVersion",
        "installed=" + (Get-Date -Format o)
    ) -Encoding ASCII
    Write-Log "Runtime installation completed."
}
catch {
    Write-Log ("Installation failed: " + $_.Exception.Message)
    Write-Log "Please send this log to the developer: $LogPath"
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "Runtime installation failed: $($_.Exception.Message)`n`nLog path: $LogPath",
            "DepthuVideoConverter",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }
    catch {
        Write-Host "Runtime installation failed: $($_.Exception.Message)"
        Write-Host "Log path: $LogPath"
    }
    exit 1
}
