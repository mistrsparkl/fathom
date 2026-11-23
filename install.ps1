# Installs Fathom for this user. Run in PowerShell:
#   irm https://raw.githubusercontent.com/mistrsparkl/fathom/main/install.ps1 | iex
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$place = Join-Path $env:LOCALAPPDATA 'Programs\Fathom'
$zip = if ($env:FATHOM_ZIP) { $env:FATHOM_ZIP } else { 'https://github.com/mistrsparkl/fathom/releases/latest/download/fathom-windows.zip' }

function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $launcher = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher'
    if (Test-Path $launcher) { $env:Path += ";$launcher" }
}
function Test-Python { [bool](Get-Command py -ErrorAction SilentlyContinue) }

Write-Host 'Installing Fathom...'
if (-not (Test-Python)) {
    Write-Host 'Getting Python 3 first (Fathom needs it)...'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
        Update-Path
    }
    if (-not (Test-Python)) {
        $setup = Join-Path $env:TEMP 'python-setup.exe'
        Invoke-WebRequest 'https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe' -OutFile $setup
        Start-Process $setup -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1', 'InstallLauncherAllUsers=0' -Wait
        Remove-Item $setup -ErrorAction SilentlyContinue
        Update-Path
    }
    if (-not (Test-Python)) { throw "Python couldn't be installed. Get it from https://www.python.org/downloads/ and run this again." }
}

# Fast runs build programs into machine code. That needs LLVM and Microsoft's C++ tools.
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$haveLlvm = (Test-Path "$env:ProgramFiles\LLVM\bin\clang++.exe") -or [bool](Get-Command clang++ -ErrorAction SilentlyContinue)
$haveCpp = (Test-Path $vswhere) -and [bool](& $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
if ((-not ($haveLlvm -and $haveCpp)) -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    $answer = $env:FATHOM_FAST
    if (-not $answer) {
        Write-Host ''
        Write-Host 'Programs run a lot faster with LLVM and Microsoft''s C++ tools (a few GB, and Windows will ask to allow them).'
        $answer = Read-Host 'Get them now? [Y/n]'
    }
    if ($answer -notmatch '^[nN0]') {
        if (-not $haveLlvm) {
            Write-Host 'Getting LLVM...'
            winget install -e --id LLVM.LLVM --silent --accept-package-agreements --accept-source-agreements | Out-Null
        }
        if (-not $haveCpp) {
            Write-Host 'Getting Microsoft''s C++ tools (this one takes a while)...'
            winget install -e --id Microsoft.VisualStudio.2022.BuildTools --silent --accept-package-agreements --accept-source-agreements `
                --override '--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended' | Out-Null
        }
    }
    else { Write-Host 'Skipped. Programs still run, just slower. Run this again any time to get them.' }
}

$work = Join-Path $env:TEMP ('fathom-' + [guid]::NewGuid())
New-Item -ItemType Directory $work | Out-Null
try {
    Write-Host 'Downloading Fathom...'
    if (Test-Path $zip) { Copy-Item $zip "$work\s.zip" } else { Invoke-WebRequest $zip -OutFile "$work\s.zip" }
    Expand-Archive "$work\s.zip" "$work\s"
    if (Test-Path $place) {
        try { Remove-Item $place -Recurse -Force }
        catch { throw 'Fathom is open (or Fathom Studio is): close it, then run this again.' }
    }
    New-Item -ItemType Directory (Split-Path $place) -Force | Out-Null
    Move-Item "$work\s" $place
}
finally { Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue }

# the fathom command, in new terminals
$user = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $user) { $user = '' }
if (($user -split ';') -notcontains $place) {
    [Environment]::SetEnvironmentVariable('Path', (($user.TrimEnd(';') + ";$place").TrimStart(';')), 'User')
}

$shell = New-Object -ComObject WScript.Shell
foreach ($folder in [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) {
    $link = $shell.CreateShortcut((Join-Path $folder 'Fathom Studio.lnk'))
    $link.TargetPath = "$place\studio-window\electron.exe"
    $link.Arguments = "`"$place\editor\studio`""
    $link.WorkingDirectory = "$place\editor\studio"
    $link.Description = 'Write and run Fathom programs'
    $link.IconLocation = "$place\editor\studio\icon.ico"
    $link.Save()
}

# Apps & features
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Fathom'
New-Item $key -Force | Out-Null
Set-ItemProperty $key DisplayName 'Fathom'
Set-ItemProperty $key DisplayIcon "$place\editor\studio\icon.ico"
Set-ItemProperty $key Publisher 'mistrsparkl'
Set-ItemProperty $key DisplayVersion (Get-Content "$place\VERSION" -ErrorAction SilentlyContinue)
Set-ItemProperty $key InstallLocation $place
Set-ItemProperty $key UninstallString "powershell -NoProfile -ExecutionPolicy Bypass -File `"$place\uninstall.ps1`""
Set-ItemProperty $key NoModify 1
Set-ItemProperty $key NoRepair 1

Write-Host ''
Write-Host 'Fathom is installed.'
Write-Host '  Open Fathom Studio from the Start menu or desktop, and press Learn to start the course.'
Write-Host '  Or, in a new terminal:  fathom hello.fathom'
