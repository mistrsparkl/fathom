# Removes Fathom (your programs, the course copy in Documents and Studia's settings stay).
$place = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($folder in [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) {
    Remove-Item (Join-Path $folder 'Fathom Studia.lnk') -ErrorAction SilentlyContinue
}
$user = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($user) {
    [Environment]::SetEnvironmentVariable('Path', ((($user -split ';') | Where-Object { $_ -and $_ -ne $place }) -join ';'), 'User')
}
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Fathom' -Recurse -ErrorAction SilentlyContinue
# (the folder holds this script, so it goes once the script has finished)
Start-Process cmd -ArgumentList '/c', "timeout /t 2 /nobreak >nul & rmdir /s /q `"$place`"" -WindowStyle Hidden
Write-Host 'Fathom is uninstalled.'
