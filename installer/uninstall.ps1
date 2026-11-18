# Removes Stellanova (your programs, the course copy in Documents and Studia's settings stay).
$place = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($folder in [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) {
    Remove-Item (Join-Path $folder 'Stellanova Studia.lnk') -ErrorAction SilentlyContinue
}
$user = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($user) {
    [Environment]::SetEnvironmentVariable('Path', ((($user -split ';') | Where-Object { $_ -and $_ -ne $place }) -join ';'), 'User')
}
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Stellanova' -Recurse -ErrorAction SilentlyContinue
# (the folder holds this script, so it goes once the script has finished)
Start-Process cmd -ArgumentList '/c', "timeout /t 2 /nobreak >nul & rmdir /s /q `"$place`"" -WindowStyle Hidden
Write-Host 'Stellanova is uninstalled.'
