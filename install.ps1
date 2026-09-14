#requires -Version 5.1
<# Windows installer for the full Nightshift CLI, hosted in WSL.
   Run: powershell -ExecutionPolicy Bypass -File .\install.ps1
   Re-run after a Windows-requested reboot or Ubuntu first-user setup.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$Distribution = 'Ubuntu-24.04',
    [ValidateSet('claude','codex','local','all')][string]$Runtime = 'claude',
    [ValidateSet('subscription','api')][string]$Auth = 'subscription',
    [switch]$SkipDependencies,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$bin = Join-Path $env:USERPROFILE '.local\bin'
if ($Plan) {
    [ordered]@{mode='wsl'; distribution=$Distribution; runtime=$Runtime; auth=$Auth;
        prerequisites=(-not $SkipDependencies); bin=$bin; source=$repo;
        stages=@('WSL and Ubuntu','Linux prerequisites','Nightshift install','CLI smoke check','PowerShell launcher')} | ConvertTo-Json
    exit 0
}
if ($env:OS -ne 'Windows_NT') { throw 'Run install.ps1 on Windows; use install.sh on macOS/Linux.' }
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) { throw 'WSL is unavailable. Install WSL using https://learn.microsoft.com/windows/wsl/install and rerun.' }
$installed = @(& wsl.exe --list --quiet 2>$null | ForEach-Object { ($_ -replace "`0", '').Trim() })
if ($LASTEXITCODE -ne 0 -or $installed -notcontains $Distribution) {
    if ($SkipDependencies) { throw "Missing WSL distribution $Distribution. Rerun without -SkipDependencies to install it." }
    & wsl.exe --install --distribution $Distribution --no-launch
    $installExit = $LASTEXITCODE
    if ($installExit -ne 0) { throw "WSL setup returned $installExit. Complete any Windows elevation/reboot request, then rerun this installer." }
    Write-Host 'Complete Ubuntu first-user setup in the window below, then exit its shell and rerun this installer.'
    & wsl.exe --distribution $Distribution
    exit 2
}
$uid = (& wsl.exe --distribution $Distribution --exec id -u).Trim()
if ($LASTEXITCODE -ne 0 -or $uid -eq '0') { throw 'Finish Ubuntu first-user setup and choose a non-root default user, then rerun.' }
$linuxRepo = (& wsl.exe --distribution $Distribution --exec wslpath -a $repo).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxRepo.StartsWith('/')) { throw 'Cannot translate the checkout path into WSL.' }
$depMode = if ($SkipDependencies) { 'check' } else { 'install' }
& wsl.exe --distribution $Distribution --exec bash "$linuxRepo/scripts/nightshift-windows-bootstrap.sh" $linuxRepo $Runtime $Auth $depMode
if ($LASTEXITCODE -ne 0) { throw 'Linux setup failed. The error above identifies the failed step; fix it and rerun.' }
$linuxHome = (& wsl.exe --distribution $Distribution --exec printenv HOME).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxHome.StartsWith('/')) { throw 'Cannot determine Linux home directory.' }
& wsl.exe --distribution $Distribution --exec bash "$linuxHome/.local/bin/nightshift" --help
if ($LASTEXITCODE -ne 0) { throw 'Nightshift CLI smoke check failed; launcher was not installed.' }
$launcher = Join-Path $bin 'nightshift.cmd'
if ((Test-Path $launcher) -and -not ((Get-Content $launcher -Raw).Contains('nightshift-windows-launcher'))) {
    throw "An unrelated $launcher already exists. Choose a different installation location before proceeding."
}
New-Item -ItemType Directory -Force $bin | Out-Null
$wrapper = Join-Path $bin 'nightshift-windows.ps1'
$config = Join-Path $bin 'nightshift-windows.json'
foreach ($path in @($launcher,$wrapper,$config)) {
    if (Test-Path $path) { Copy-Item $path "$path.backup-$([guid]::NewGuid().ToString('N'))" }
}
Copy-Item (Join-Path $repo 'scripts\nightshift-windows.ps1') $wrapper -Force
[ordered]@{distribution=$Distribution; launcher="$linuxHome/.local/bin/nightshift"} |
    ConvertTo-Json | Set-Content $config -Encoding UTF8
# Fixed wrapper text: no user-controlled path interpolated into command source.
@'
@echo off
rem nightshift-windows-launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0nightshift-windows.ps1" %*
exit /b %errorlevel%
'@ | Set-Content $launcher -Encoding ASCII
$userPath = [string][Environment]::GetEnvironmentVariable('Path','User')
if (@($userPath -split ';') -notcontains $bin) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $bin).TrimStart(';')), 'User')
}
if (@($env:Path -split ';') -notcontains $bin) { $env:Path += ";$bin" }
Write-Host 'Nightshift installed. Open a new terminal, then run nightshift --help.'
Write-Host "Runtime: $Runtime; authentication preference: $Auth. No model request was made."
