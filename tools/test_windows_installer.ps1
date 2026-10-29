param([Parameter(Mandatory=$true)][string]$Compiler)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Installer integration test only runs on a disposable GitHub Actions worker.' }
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$version = (Get-Content VERSION -Raw).Trim()
$installDir = Join-Path $env:RUNNER_TEMP 'Yeli installer smoke test'
$dataDir = Join-Path $env:LOCALAPPDATA 'Yeli/data'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{F3549C87-9EB4-4F88-8E66-95527B911C93}_is1'
$report = @{ ok = $false; version = $version }
New-Item -ItemType Directory -Force dist/installer-test | Out-Null
if ((Test-Path $dataDir) -or (Test-Path $installDir) -or (Test-Path $registryPath)) { throw 'Installer test requires a clean worker; existing user data will not be overwritten.' }
New-Item -ItemType Directory -Force $dataDir | Out-Null
# Seed genuine old EXE config, chat, memories, draft and imported skill data.
@'
import json, os, sqlite3
from pathlib import Path
p=Path(os.environ['LOCALAPPDATA'])/'Yeli/data'
c=sqlite3.connect(p/'companion.db')
c.executescript('CREATE TABLE settings(id INTEGER PRIMARY KEY,value TEXT); CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT,content TEXT); CREATE TABLE memories(id INTEGER PRIMARY KEY,content TEXT); CREATE TABLE drafts(id INTEGER PRIMARY KEY,content TEXT); CREATE TABLE skills(id INTEGER PRIMARY KEY,content TEXT);')
c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps({'api_key':'ci-placeholder-not-a-real-secret','scale':1.23}),))
c.execute("INSERT INTO messages VALUES(1,'user','existing chat')")
c.execute("INSERT INTO memories VALUES(1,'existing memory')")
c.execute("INSERT INTO drafts VALUES(1,'existing draft')")
c.execute("INSERT INTO skills VALUES(1,'existing skill')")
c.commit();c.close()
(p/'runtime.json').write_text(json.dumps({'version':1,'voice_choice':'zh-CN-XiaoyiNeural','voice_volume':67}),encoding='utf-8')
(p/'game-watch.json').write_text('{"champion":"existing champion"}',encoding='utf-8')
'@ | python -
if ($LASTEXITCODE -ne 0) { throw 'Could not seed legacy configuration' }
$before = @{}
Get-ChildItem $dataDir -File | ForEach-Object { $before[$_.Name] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
function Assert-DataPreserved {
    foreach ($name in $before.Keys) {
        $file = Join-Path $dataDir $name
        if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash -ne $before[$name]) { throw "User data changed: $name" }
    }
}
function Install-Package([string]$package, [string]$logName) {
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $installDir + '"'),('/LOG="' + (Join-Path $root ('dist/' + $logName)) + '"'))
    $process = Start-Process -FilePath $package -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer returned $($process.ExitCode)" }
}
try {
    & $Compiler '/DAppVersion=0.0.1' '/Odist/installer-test' 'installer/Yeli.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Could not build previous-version test installer' }
    Install-Package (Join-Path $root 'dist/installer-test/Yeli-Setup-0.0.1-x64.exe') 'install-old.log'
    Assert-DataPreserved
    if ((Get-ItemProperty $registryPath).DisplayVersion -ne '0.0.1') { throw 'Old version not registered' }
    Install-Package (Join-Path $root "dist/Yeli-Setup-$version-x64.exe") 'install-upgrade.log'
    Assert-DataPreserved
    if ((Get-ItemProperty $registryPath).DisplayVersion -ne $version) { throw 'Upgrade did not register the new version' }
    if (-not (Test-Path (Join-Path $env:APPDATA 'Microsoft/Windows/Start Menu/Programs/夜璃/夜璃.lnk'))) { throw 'Start Menu shortcut missing' }
    $installedExe = Join-Path $installDir 'Yeli.exe'
    if ((Get-FileHash $installedExe).Hash -ne (Get-FileHash dist/Yeli.exe).Hash) { throw 'Installed executable differs from built executable' }
    $selfTest = Join-Path $root 'dist/installed-self-test.json'
    $process = Start-Process -FilePath $installedExe -ArgumentList @('--self-test', ('"' + $selfTest + '"')) -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Get-Content $selfTest -Raw | ConvertFrom-Json).ok) { throw 'Installed EXE self-test failed' }
    Assert-DataPreserved
    $uninstall = Start-Process -FilePath (Join-Path $installDir 'unins000.exe') -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
    if ($uninstall.ExitCode -ne 0) { throw 'Uninstall failed' }
    Assert-DataPreserved
    if (Test-Path $installedExe) { throw 'Uninstall left the application executable installed' }
    $report.ok = $true
    $report.checks = @('installation','upgrade from 0.0.1','version registration','Start Menu shortcut','installed EXE self-test','settings preserved','uninstall retains data')
} finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 dist/installer-test.json
}
