<#
  Registers the nightly catalog build in Windows Task Scheduler.
  Run once, in an elevated PowerShell, from the folder that holds catalog-builder.exe:

      powershell -ExecutionPolicy Bypass -File .\install-scheduled-task.ps1

  You'll be asked for the Windows service account the task runs as. That account needs:
    - read on the FileMaker Server Documents\catalog folder
    - read on the content share, write on the output share and on \\vm-webserver\www\catalog
    - the "Log on as a batch job" right
#>
param(
  [string]$Time = "2:15AM",
  [string]$TaskName = "IECC Catalog Build"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = if (Test-Path (Join-Path $here "catalog-builder.exe")) { $here } else { Split-Path -Parent $here }
$exe  = Join-Path $root "catalog-builder.exe"
$bat  = Join-Path $root "run-nightly.bat"
$cfg  = Join-Path $root "config.json"

if (-not (Test-Path $exe)) { throw "catalog-builder.exe not found in $root" }
if (-not (Test-Path $bat)) { Copy-Item (Join-Path $here "run-nightly.bat") $bat }
if (-not (Test-Path $cfg)) {
  Copy-Item (Join-Path $here "config.server.json") $cfg
  Write-Warning "Created $cfg from the template. Check its paths, then run this script again."
  notepad $cfg
  exit 1
}

# Sanity checks before scheduling
$c = Get-Content $cfg -Raw | ConvertFrom-Json
foreach ($k in "export", "out", "site") {
  if (-not $c.$k) { throw "config.json is missing '$k'" }
}
if (-not (Test-Path $c.export)) { Write-Warning "Export file not found yet: $($c.export). Run the FileMaker 'Catalog Export' schedule once first." }

$cred = Get-Credential -Message "Windows account the nightly build runs as (DOMAIN\user)"
$action   = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited -Force | Out-Null

Write-Host "Scheduled '$TaskName' daily at $Time as $($cred.UserName)."
Write-Host "Test it now:  Start-ScheduledTask -TaskName '$TaskName'   then check $root\logs\"
