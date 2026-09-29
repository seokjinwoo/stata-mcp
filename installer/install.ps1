param(
    [string]$PythonPath,
    [string]$InstallDir,
    [string]$StataHome,
    [ValidateSet('be', 'se', 'mp')][string]$Edition,
    [string]$WorkDir,
    [string]$CodexConfig,
    [string]$ClaudeConfig,
    [ValidateSet('codex', 'claude', 'both')][string]$Client,
    [ValidateSet('ko', 'en')][string]$Language,
    [switch]$NonInteractive,
    [switch]$ReplaceExisting
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$OutputEncoding = [Console]::OutputEncoding

. (Join-Path $PSScriptRoot 'python-discovery.ps1')

function Text([string]$Korean, [string]$English) {
    if ($Language -eq 'en') { return $English }
    return $Korean
}

try {
    if (-not $Language) {
        if ($NonInteractive) {
            $Language = 'ko'
        } else {
            Write-Host '언어 선택 / Select language: 1. 한국어  2. English'
            $languageChoice = Read-Host '번호 / Number [1]'
            switch ($languageChoice.Trim()) {
                '' { $Language = 'ko' }
                '1' { $Language = 'ko' }
                '2' { $Language = 'en' }
                default { throw '1 또는 2를 선택하세요. / Select 1 or 2.' }
            }
        }
    }
    $env:STATA_MCP_INSTALL_LANGUAGE = $Language
    Write-Host (Text 'Stata MCP 설치 - Windows / Codex / Claude Desktop' 'Stata MCP setup - Windows / Codex / Claude Desktop')
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
        Write-Host (Text '64비트 Python 3.11 이상이 필요합니다. 검증 버전은 Python 3.12입니다.' '64-bit Python 3.11+ is required. Python 3.12 is the tested version.')
        Write-Host (Text 'https://www.python.org/downloads/windows/ 에서 Python을 설치한 뒤 다시 실행하세요.' 'Install Python from https://www.python.org/downloads/windows/ and run this installer again.')
        Write-Host (Text 'Python이 설치되어 있다면 경로를 지정하세요: install.ps1 -PythonPath "C:\path\python.exe"' 'If Python is already installed, use: install.ps1 -PythonPath "C:\path\python.exe"')
        exit 1
    }
    Write-Host "Python: $selectedPython"
    $installerArgs = @((Join-Path $PSScriptRoot 'bootstrap.py'), '--language', $Language)
    if ($InstallDir) { $installerArgs += @('--install-dir', $InstallDir) }
    if ($StataHome) { $installerArgs += @('--stata-home', $StataHome) }
    if ($Edition) { $installerArgs += @('--edition', $Edition) }
    if ($WorkDir) { $installerArgs += @('--workdir', $WorkDir) }
    if ($CodexConfig) { $installerArgs += @('--codex-config', $CodexConfig) }
    if ($ClaudeConfig) { $installerArgs += @('--claude-config', $ClaudeConfig) }
    if ($Client) { $installerArgs += @('--client', $Client) }
    if ($NonInteractive) { $installerArgs += '--non-interactive' }
    if ($ReplaceExisting) { $installerArgs += '--replace-existing' }
    & $selectedPython @installerArgs
    exit $LASTEXITCODE
} catch {
    Write-Host ((Text '설치를 완료하지 못했습니다: ' 'Setup failed: ') + $_)
    exit 1
}
