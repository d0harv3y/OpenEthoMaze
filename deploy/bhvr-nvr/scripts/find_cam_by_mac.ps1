#Requires -Version 5.1
# Thin launcher — real work is find_cam_by_mac_win.py (PS 5.1 has no ForEach -Parallel).
param(
  [string]$Mac = "b8-27-eb-e1-a4-bb"#"d8:3a:dd:47:71:55"#
)
$py = Join-Path $PSScriptRoot "find_cam_by_mac_win.py"
python $py --mac $Mac
if ($LASTEXITCODE -ne 0) {
  Write-Host "python failed; try: py $py --mac $Mac"
  exit $LASTEXITCODE
}
