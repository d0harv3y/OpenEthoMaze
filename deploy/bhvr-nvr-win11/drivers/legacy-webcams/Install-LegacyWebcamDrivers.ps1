#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Stage offline Class_FF webcam drivers (Vimicro / Pixart) into the Win11 driver store.

.DESCRIPTION
  Run elevated on the target NVR after copying this legacy-webcams folder.
  Does not launch vendor helper EXEs — only pnputil /add-driver on the INF.

.PARAMETER Pack
  all | vimicro | pixart

.EXAMPLE
  .\Install-LegacyWebcamDrivers.ps1
  .\Install-LegacyWebcamDrivers.ps1 -Pack pixart
#>
[CmdletBinding()]
param(
  [ValidateSet('all', 'vimicro', 'pixart')]
  [string] $Pack = 'all'
)

$ErrorActionPreference = 'Stop'
$Here = $PSScriptRoot

$Packs = @(
  [pscustomobject]@{
    Name = 'vimicro'
    Id   = 'USB\VID_0AC8&PID_301B'
    Inf  = Join-Path $Here 'vimicro_0ac8_301b\usbvm31b.inf'
  }
  [pscustomobject]@{
    Name = 'pixart'
    Id   = 'USB\VID_093A&PID_2468'
    Inf  = Join-Path $Here 'pixart_093a_2468\pkg\PFC027.inf'
  }
)

function Test-IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
  throw 'Run elevated (Administrator). Right-click PowerShell → Run as administrator.'
}

$selected = if ($Pack -eq 'all') { $Packs } else { $Packs | Where-Object Name -eq $Pack }
if (-not $selected) { throw "unknown pack: $Pack" }

Write-Host "Machine: $env:COMPUTERNAME  User: $env:USERNAME"
Write-Host "Kit root: $Here"
Write-Host ""

foreach ($p in $selected) {
  if (-not (Test-Path -LiteralPath $p.Inf)) {
    Write-Warning "SKIP $($p.Name): missing INF $($p.Inf)"
    continue
  }
  Write-Host "=== $($p.Name)  $($p.Id) ==="
  Write-Host "INF: $($p.Inf)"
  $out = & pnputil.exe /add-driver $p.Inf /install 2>&1
  $out | ForEach-Object { Write-Host $_ }
  Write-Host ""
}

Write-Host "=== matching PnP nodes (present) ==="
Get-PnpDevice -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Present -and (
      $_.InstanceId -match 'VID_0AC8&PID_301B|VID_093A&PID_2468' -or
      $_.FriendlyName -match 'Vimicro|CIF Single|Eye 110|PAC207|ZC0301'
    )
  } |
  Format-Table Status, Class, FriendlyName, InstanceId -AutoSize

Write-Host @"

Next:
  1) Device Manager — confirm no yellow bang on the stick(s).
  2) ffmpeg -hide_banner -list_devices true -f dshow -i dummy
  3) Prefer MJPEG UVC sticks for multi-cam; these Class_FF packs are last resort.

"@
