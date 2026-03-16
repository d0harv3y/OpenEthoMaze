# VAST Controller — install/update and optionally create desktop shortcut.
# Run from repo root: .\scripts\install.ps1
# Or with shortcut: .\scripts\install.ps1 -CreateShortcut
#
# Prerequisites (install once per machine):
#   - Python >= 3.12
#   - uv (pip install uv)
#   - Vimba SDK, CUDA (if using SLEAP) — see README

param(
    [switch]$CreateShortcut,
    [switch]$Sleap   # add --extra sleap for SLEAP + CUDA
)

$ErrorActionPreference = "Stop"

# Find repo root (directory containing pyproject.toml)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PyProject = Join-Path $RepoRoot "pyproject.toml"
if (-not (Test-Path $PyProject)) {
    Write-Error "Not found: $PyProject. Run this script from the repo (e.g. .\scripts\install.ps1 from repo root)."
}

Set-Location $RepoRoot
Write-Host "VAST Controller install at: $RepoRoot"

# Sync environment (gui required for the app)
$SyncArgs = @("sync", "--extra", "gui")
if ($Sleap) { $SyncArgs += "--extra", "sleap" }
Write-Host "Running: uv $($SyncArgs -join ' ')"
& uv @SyncArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Sleap) {
    Write-Host ""
    Write-Host "SLEAP extra: if you need CUDA, run after sync:"
    Write-Host "  uv pip install torch torchvision --default-index https://download.pytorch.org/whl/cu130 --reinstall"
    Write-Host ""
}

if (-not $CreateShortcut) {
    Write-Host "Done. Run the app: uv run python -m vast_controller"
    Write-Host "Or after pip/uv install -e . : vast-controller"
    exit 0
}

# Create desktop shortcut
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "VAST Controller.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -Command \"Set-Location '$RepoRoot'; uv run python -m vast_controller\""
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Description = "VAST Controller — circular open field behavior controller"
$Shortcut.Save()
Write-Host "Shortcut created: $ShortcutPath"
Write-Host "Done. Run the app from the shortcut or: uv run python -m vast_controller"
