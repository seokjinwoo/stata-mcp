param(
    [string]$PythonPath,
    [string]$InstallDir,
    [string]$StataHome,
    [ValidateSet('be', 'se', 'mp')][string]$Edition,
    [string]$WorkDir,
    [string]$CodexConfig,
    [switch]$NonInteractive,
    [switch]$ReplaceExisting
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$OutputEncoding = [Console]::OutputEncoding

. (Join-Path $PSScriptRoot 'python-discovery.ps1')

try {
    Write-Host 'Stata MCP setup - Windows / Codex'
    $selectedPython = $null
    if ($PythonPath) {
        $selectedPython = Test-Python $PythonPath @()
    } else {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            foreach ($version in @('-3.12', '-3.11', '-3')) {
                $selectedPython = Test-Python 'py' @($version)
                if ($selectedPython) { break }
            }
        }
        if (-not $selectedPython -and (Get-Command python -ErrorAction SilentlyContinue)) {
            $selectedPython = Test-Python 'python' @()
        }
        if (-not $selectedPython) {
            $selectedPython = Find-RegisteredPython
        }
    }
    if (-not $selectedPython) {
        Write-Host '64-bit Python 3.11+ is required. Python 3.12 is the tested version.'
        Write-Host 'Install Python from https://www.python.org/downloads/windows/ and run this installer again.'
        Write-Host 'If Python is already installed, use: install.ps1 -PythonPath "C:\path\python.exe"'
        exit 1
    }
    Write-Host "Python: $selectedPython"
    $installerArgs = @((Join-Path $PSScriptRoot 'bootstrap.py'))
    if ($InstallDir) { $installerArgs += @('--install-dir', $InstallDir) }
    if ($StataHome) { $installerArgs += @('--stata-home', $StataHome) }
    if ($Edition) { $installerArgs += @('--edition', $Edition) }
    if ($WorkDir) { $installerArgs += @('--workdir', $WorkDir) }
    if ($CodexConfig) { $installerArgs += @('--codex-config', $CodexConfig) }
    if ($NonInteractive) { $installerArgs += '--non-interactive' }
    if ($ReplaceExisting) { $installerArgs += '--replace-existing' }
    & $selectedPython @installerArgs
    exit $LASTEXITCODE
} catch {
    Write-Host "Setup failed: $_"
    exit 1
}
