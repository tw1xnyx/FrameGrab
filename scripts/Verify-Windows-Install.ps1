# CI-only installation verification in an isolated hosted Windows runner.
$ErrorActionPreference='Stop'
$project=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dest=Join-Path $env:RUNNER_TEMP 'FrameGrab Installation Test'
if(!$env:RUNNER_TEMP){throw 'This test is restricted to the CI runner'}
$setup=Get-ChildItem (Join-Path $project 'dist') -Filter 'FrameGrab_Setup_*.exe' | Select-Object -First 1
$p=Start-Process $setup.FullName -ArgumentList @('/S','/currentuser',"/D=$dest") -WindowStyle Hidden -PassThru -Wait
if($p.ExitCode -ne 0){throw "Installer exit $($p.ExitCode)"}
$exe=Join-Path $dest 'FrameGrab.exe'
if(!(Test-Path $exe)){throw 'Installed executable missing'}
foreach($name in @('yt-dlp.exe','ffmpeg.exe','ffprobe.exe','deno.exe')){
  if(!(Test-Path (Join-Path $dest "resources/tools/$name"))){throw "Installed tool missing: $name"}
}
if(!(Test-Path (Join-Path $dest 'resources/runtime/pythonw.exe'))){throw 'Embedded runtime missing'}
$data=Join-Path $env:APPDATA 'FrameGrab'
New-Item -ItemType Directory -Force $data | Out-Null
$marker=Join-Path $data 'release-test-marker.txt'
Set-Content $marker 'preserve-through-in-place-install'
$app=Start-Process $exe -WindowStyle Hidden -PassThru
$ready=$false
try {
  for($i=0;$i -lt 90;$i++){
    Start-Sleep -Milliseconds 500
    $log=Join-Path $data 'logs/framegrab.log'
    if((Test-Path $log) -and (Get-Content $log -Raw).Contains('engine ready on loopback port')){$ready=$true;break}
    if($app.HasExited){throw 'Installed application exited before engine readiness'}
  }
  if(!$ready){throw 'Installed backend did not become ready'}
} finally {
  if(!$app.HasExited){Start-Process taskkill.exe -ArgumentList @('/PID',"$($app.Id)",'/T','/F') -WindowStyle Hidden -Wait | Out-Null}
}
$update=Get-ChildItem (Join-Path $project 'dist') -Filter 'FrameGrab_Update_*.exe' | Select-Object -First 1
$p=Start-Process $update.FullName -ArgumentList @('/S','/currentuser') -WindowStyle Hidden -Wait -PassThru
if($p.ExitCode -ne 0 -or !(Test-Path $exe)){throw 'In-place package installation failed'}
if((Get-Content $marker -Raw).Trim() -ne 'preserve-through-in-place-install'){throw 'Application data lost'}
Write-Host 'PASS silent custom-directory install, bundled tools, installed engine readiness, same-version in-place reinstall and app-data preservation'
Write-Host 'Interactive wizard, new-version migration and in-app update flow still require separate verification.'
