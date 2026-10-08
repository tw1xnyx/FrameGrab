# FrameGrab Windows build. Run in Windows PowerShell 5.1+ with Node.js 22 LTS and npm.
# This is a RELEASE BUILD step, not an end-user setup step.
param([switch]$SkipDownload)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$Project=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Project
$Tools=Join-Path $Project 'tools'
$Runtime=Join-Path $Project 'runtime'
$Staging=Join-Path $Project '.staging'
New-Item -ItemType Directory -Force -Path $Tools,$Runtime,$Staging | Out-Null

function Get-Package([string]$Url,[string]$Target){
  Write-Host "Getting build dependency from: $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Target -UseBasicParsing -MaximumRedirection 8
  if(!(Test-Path $Target) -or (Get-Item $Target).Length -lt 1000){throw "Download failed: $Target"}
}
function Verify-Tool([string]$Executable,[string]$Arg){
  if(!(Test-Path $Executable)){throw "Required tool missing: $Executable"}
  $p=Start-Process -FilePath $Executable -ArgumentList $Arg -PassThru -NoNewWindow -Wait
  if($p.ExitCode -ne 0){throw "Tool verification failed: $Executable"}
}
if(-not $SkipDownload){
  # Python embeddable runtime is bundled with the installer; users NEVER install Python or run a console.
  if(!(Test-Path (Join-Path $Runtime 'pythonw.exe'))){
    $Archive=Join-Path $Staging 'python-embed.zip'
    Get-Package 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' $Archive
    Expand-Archive -Path $Archive -DestinationPath $Runtime -Force
    Set-Content (Join-Path $Runtime 'python312._pth') -Encoding Ascii -Value @('python312.zip','.','..','import site')
  }
  if(!(Test-Path (Join-Path $Tools 'yt-dlp.exe'))){
    Get-Package 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' (Join-Path $Tools 'yt-dlp.exe')
  }
  if(!(Test-Path (Join-Path $Tools 'deno.exe'))){
    $Archive=Join-Path $Staging 'deno.zip'
    Get-Package 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' $Archive
    Expand-Archive -Force $Archive (Join-Path $Staging 'deno')
    Copy-Item (Join-Path $Staging 'deno/deno.exe') (Join-Path $Tools 'deno.exe') -Force
  }
  if(!(Test-Path (Join-Path $Tools 'ffmpeg.exe')) -or !(Test-Path (Join-Path $Tools 'ffprobe.exe'))){
    $Archive=Join-Path $Staging 'ffmpeg.zip'
    Get-Package 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $Archive
    Expand-Archive -Force $Archive (Join-Path $Staging 'ffmpeg')
    $ffmpeg=Get-ChildItem (Join-Path $Staging 'ffmpeg') -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    $ffprobe=Get-ChildItem (Join-Path $Staging 'ffmpeg') -Recurse -Filter ffprobe.exe | Select-Object -First 1
    if(!$ffmpeg -or !$ffprobe){throw 'FFmpeg archive missing executables'}
    Copy-Item $ffmpeg.FullName (Join-Path $Tools 'ffmpeg.exe') -Force
    Copy-Item $ffprobe.FullName (Join-Path $Tools 'ffprobe.exe') -Force
  }
}
foreach($f in @((Join-Path $Runtime 'pythonw.exe'),(Join-Path $Tools 'yt-dlp.exe'),(Join-Path $Tools 'ffmpeg.exe'),(Join-Path $Tools 'ffprobe.exe'),(Join-Path $Tools 'deno.exe'))){
  if(!(Test-Path $f)){throw "Missing required runtime: $f"}
}
$Required=@('pythonw.exe','yt-dlp.exe','ffmpeg.exe','ffprobe.exe','deno.exe')
$manifest=@{}
foreach($name in $Required){
  $p=if($name -eq 'pythonw.exe'){Join-Path $Runtime $name}else{Join-Path $Tools $name}
  $manifest[$name]=@{sha256=(Get-FileHash -Algorithm SHA256 $p).Hash;bytes=(Get-Item $p).Length}
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $Project 'build-dependency-hashes.json')
if(!(Get-Command npm -ErrorAction SilentlyContinue)){throw 'Build machine needs Node.js 22 and npm. End users do not.'}
Write-Host 'Installing build dependencies (not installed on end-user machines)...'
npm ci --no-fund --no-audit
if($LASTEXITCODE -ne 0){throw 'npm install failed'}
Write-Host 'Building Windows NSIS installer...'
npm run build:win
if($LASTEXITCODE -ne 0){throw 'Windows builder failed'}
$Setup=Get-ChildItem (Join-Path $Project 'dist') -Filter 'FrameGrab_Setup_*.exe' | Select-Object -First 1
if(!$Setup){throw 'NSIS installer was not created'}
$ver=(Get-Content (Join-Path $Project 'package.json') -Raw | ConvertFrom-Json).version
$Alias=Join-Path $Project ("dist/FrameGrab_Update_$ver.exe")
# NSIS detects existing application via stable appId and installer registry state.
# This separate update installer is the same signed package, not a fake binary patch.
Copy-Item $Setup.FullName $Alias -Force
Write-Host 'Installer:' $Setup.FullName
Write-Host 'Standalone update installer:' $Alias
Write-Host 'The dist/latest.yml and .blockmap files are for verified in-app updates.'
Write-Host 'Code-sign publicly distributed releases and publish dist/ securely over HTTPS.'
