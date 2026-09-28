# Shared by the launcher; no installation or configuration changes here.
function Test-Python([string]$Executable, [string[]]$Prefix) {
    try {
        $probeCode = "import sys,struct; print(sys.executable) if sys.version_info >= (3,11) and struct.calcsize('P') == 8 else None"
        $probe = & $Executable @Prefix -c $probeCode 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe -and (Test-Path -LiteralPath ([string]$probe))) {
            return [string]$probe
        }
    } catch { }
    return $null
}

function Find-PythonInFolders([string[]]$Folders) {
    foreach ($folder in ($Folders | Select-Object -Unique)) {
        if (-not $folder) { continue }
        $candidate = Join-Path $folder 'python.exe'
        if (Test-Path -LiteralPath $candidate) {
            $found = Test-Python $candidate @()
            if ($found) { return $found }
        }
    }
    return $null
}

function Find-RegisteredPython {
    $folders = @()
    foreach ($registryRoot in @('HKCU:\Software\Python', 'HKLM:\Software\Python', 'HKLM:\Software\WOW6432Node\Python')) {
        if (Test-Path $registryRoot) {
            $keys = Get-ChildItem $registryRoot -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.PSChildName -eq 'InstallPath' }
            foreach ($key in $keys) {
                $value = $key.GetValue('')
                if ($value) { $folders += [string]$value }
            }
        }
    }
    $commonRoots = @()
    if ($env:LOCALAPPDATA) { $commonRoots += (Join-Path $env:LOCALAPPDATA 'Programs\Python') }
    if ($env:ProgramFiles) { $commonRoots += $env:ProgramFiles }
    if ($env:SystemDrive) { $commonRoots += ($env:SystemDrive + '\') }
    foreach ($root in $commonRoots) {
        if (Test-Path -LiteralPath $root) {
            $folders += @(Get-ChildItem -LiteralPath $root -Directory -Filter 'Python*' -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending | Select-Object -ExpandProperty FullName)
        }
    }
    return Find-PythonInFolders $folders
}
