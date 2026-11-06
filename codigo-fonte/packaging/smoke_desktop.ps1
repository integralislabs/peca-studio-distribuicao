param([Parameter(Mandatory=$true)][string]$Installer,[Parameter(Mandatory=$true)][string]$InstallDir,[Parameter(Mandatory=$true)][string]$EvidenceDir)
$ErrorActionPreference='Stop'
$installerPath=(Resolve-Path -LiteralPath $Installer).Path
$qaInstall=[System.IO.Path]::GetFullPath($InstallDir)
$qaEvidence=[System.IO.Path]::GetFullPath($EvidenceDir)
New-Item -ItemType Directory -Path $qaEvidence -Force | Out-Null
$log=Join-Path $qaEvidence 'installation.log'
$arguments=@('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',('/DIR="'+$qaInstall+'"'),('/LOG="'+$log+'"'))
$process=Start-Process -FilePath $installerPath -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
if($process.ExitCode -ne 0){throw "Installer returned $($process.ExitCode)"}
$exe=Join-Path $qaInstall 'PecaStudio.exe'
$output=Join-Path $qaEvidence 'installed-self-test.json'
$previousDataRoot=$env:PECA_STUDIO_DATA_ROOT
try {
 $env:PECA_STUDIO_DATA_ROOT=Join-Path $qaEvidence 'data'
 $process=Start-Process -FilePath $exe -ArgumentList @('--self-test','--output',('"'+$output+'"')) -WindowStyle Hidden -PassThru -Wait
} finally {$env:PECA_STUDIO_DATA_ROOT=$previousDataRoot}
if($process.ExitCode -ne 0){throw "Installed executable returned $($process.ExitCode)"}
$report=Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
if(-not $report.frozen -or -not $report.http -or -not $report.webview -or -not $report.ffmpeg -or -not $report.tesseract){throw 'Runtime check failed'}
Get-Item -LiteralPath $exe | Select-Object FullName,Length,@{Name='Version';Expression={$_.VersionInfo.FileVersion}}
$report
