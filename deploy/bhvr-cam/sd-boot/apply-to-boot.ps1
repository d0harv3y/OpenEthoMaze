#Requires -Version 5.1
<#
.SYNOPSIS
  After Raspberry Pi Imager finishes, copy bhvr-cam onto the boot (FAT) partition
  and arm a one-shot firstrun so first boot installs without USB/SSH.

.EXAMPLE
  .\apply-to-boot.ps1 -BootDrive E:
#>
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z]:\\?$|^[A-Za-z]:$')]
  [string]$BootDrive
)

$ErrorActionPreference = "Stop"
$boot = $BootDrive.TrimEnd('\') + '\'
if (-not (Test-Path (Join-Path $boot 'cmdline.txt'))) {
  throw "cmdline.txt not found on $boot - is this the Pi boot partition?"
}

$here = $PSScriptRoot
$payloadSrc = Split-Path $here -Parent  # deploy/bhvr-cam
$destPayload = Join-Path $boot 'bhvr-cam'
$destFirstrun = Join-Path $boot 'bhvr-firstrun.sh'
$nvrKeysSrc = Join-Path $payloadSrc 'ssh\nvr_authorized_keys'

Write-Host "Payload: $payloadSrc -> $destPayload"
if (-not (Test-Path $nvrKeysSrc)) {
  Write-Warning "Missing $nvrKeysSrc - focus/record SSH will fail until NVR pubkey is baked."
} else {
  $pubLine = @(Get-Content -LiteralPath $nvrKeysSrc | Where-Object {
      $_.Trim() -and ($_ -notmatch '^\s*#')
    } | Select-Object -First 1)
  if (-not $pubLine) {
    Write-Warning "nvr_authorized_keys is empty"
  } else {
    $preview = $pubLine[0].Substring(0, [Math]::Min(40, $pubLine[0].Length))
    Write-Host "NVR pubkey: $preview..."
  }
}

if (Test-Path $destPayload) { Remove-Item -Recurse -Force $destPayload }
New-Item -ItemType Directory -Path $destPayload | Out-Null

# Copy install tree (exclude sd-boot to avoid nesting noise)
Get-ChildItem $payloadSrc -Force | Where-Object { $_.Name -ne 'sd-boot' } | ForEach-Object {
  Copy-Item $_.FullName -Destination $destPayload -Recurse -Force
}

# Firstrun script as LF
$firstrun = Join-Path $here 'bhvr-firstrun.sh'
$raw = [IO.File]::ReadAllText($firstrun) -replace "`r`n", "`n" -replace "`r", "`n"
[IO.File]::WriteAllBytes($destFirstrun, [Text.UTF8Encoding]::new($false).GetBytes($raw))

# Merge NVR pubkey into Imager cloud-init user-data when present.
# firstboot also installs authorized_keys from bhvr-cam/ssh/.
$userDataPath = Join-Path $boot 'user-data'
if ((Test-Path $nvrKeysSrc) -and (Test-Path $userDataPath)) {
  $pubLine = @(Get-Content -LiteralPath $nvrKeysSrc | Where-Object {
      $_.Trim() -and ($_ -notmatch '^\s*#')
    } | Select-Object -First 1)
  if ($pubLine) {
    $key = $pubLine[0].Trim()
    $ud = [IO.File]::ReadAllText($userDataPath)
    if ($ud.IndexOf($key) -lt 0) {
      $nl = [char]10
      $block = (
        $nl +
        '# bhvr-cam apply-to-boot - NVR session-control key' + $nl +
        'ssh_authorized_keys:' + $nl +
        '  - ' + $key + $nl
      )
      $ud2 = $ud.TrimEnd() + $nl + $block
      $ud2 = $ud2 -replace "`r`n", "`n" -replace "`r", "`n"
      [IO.File]::WriteAllBytes(
        $userDataPath,
        [Text.UTF8Encoding]::new($false).GetBytes($ud2)
      )
      Write-Host 'Merged NVR pubkey into user-data'
    } else {
      Write-Host 'user-data already contains NVR pubkey'
    }
  }
}

# Clear prior firstrun marker so a re-arm is obvious on the FAT volume
foreach ($stale in @('bhvr-firstrun.done', 'bhvr-firstrun.log', 'bhvr-net-status.txt')) {
  $p = Join-Path $boot $stale
  if (Test-Path $p) { Remove-Item -Force $p }
}

$cmdlinePath = Join-Path $boot 'cmdline.txt'
$cmd = ([IO.File]::ReadAllText($cmdlinePath) -replace "`r`n", "`n" -replace "`r", "`n").Trim()
$cmd = [regex]::Replace($cmd, '\s*systemd\.run=\S+', '')
$cmd = [regex]::Replace($cmd, '\s*systemd\.run_success_action=\S+', '')
$cmd = [regex]::Replace($cmd, '\s*systemd\.unit=kernel-command-line\.target', '')
$hook = ' systemd.run=/boot/firmware/bhvr-firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target'
if ($cmd -notmatch 'systemd\.run=') {
  $cmd = $cmd + $hook
}
[IO.File]::WriteAllBytes($cmdlinePath, [Text.UTF8Encoding]::new($false).GetBytes($cmd + "`n"))

Write-Host ''
Write-Host "Armed first-boot install on $boot"
Write-Host '  bhvr-cam/ payload includes ssh/nvr_authorized_keys'
Write-Host '  bhvr-firstrun.sh'
Write-Host '  cmdline.txt systemd.run hook'
Write-Host '  user-data NVR pubkey merge when present'
Write-Host ''
Write-Host 'Eject the card, boot the Zero on wsu-iot or USB power.'
Write-Host 'First boot installs NVR SSH trust + units + avahi off, then reboots once.'
Write-Host 'Log: /boot/firmware/bhvr-firstrun.log'
Write-Host ''
