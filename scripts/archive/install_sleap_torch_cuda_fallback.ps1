# SLEAP CUDA torch fallback installer
# Run from repo root OR call with -RepoRoot.
#
# Logic:
#   1) uv sync --extra sleap
#   2) attempt torch/torchvision CUDA wheels in descending order:
#        cu130 -> cu121 -> cu118
#      after each attempt run `uv run python -c "import torch; torch.cuda.is_available()"`.
#   3) if CUDA still not available, fall back to CPU wheels.
#
# Notes:
# - This is intentionally a post-sync step because uv.lock resolution is static
#   and cannot reliably pick a CUDA wheel compatible with *your* driver stack.

param(
    [string]$RepoRoot = "",
    [string]$TorchVersion = "2.10.0",
    [string]$TorchvisionVersion = "0.25.0",
    [switch]$DoSync
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    # Derive repo root from this script location: scripts/archive/*.ps1 -> repo root is ../..
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = Split-Path -Parent $ScriptDir
}

Set-Location $RepoRoot

function Test-CudaAvailable {
    $out = & uv run python -c "import torch; print(int(torch.cuda.is_available())); print(int(torch.cuda.device_count()))"
    # Output is two lines: is_available, device_count
    $lines = $out -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
    if ($lines.Count -lt 2) { return $false }
    $isAvail = [int]$lines[0]
    $devCount = [int]$lines[1]
    return ($isAvail -eq 1 -and $devCount -ge 1)
}

function Install-TorchTvision {
    param(
        [string]$IndexUrl,
        [string]$TorchWheelSuffix,
        [string]$VisionWheelSuffix
    )

    # Example:
    #   torch==2.10.0+cu121
    #   torchvision==0.25.0+cu121
    $torchPkg = "torch==$TorchVersion+$TorchWheelSuffix"
    $visPkg = "torchvision==$TorchvisionVersion+$VisionWheelSuffix"

    Write-Host ""
    Write-Host "Installing: $torchPkg  $visPkg"
    Write-Host "Index: $IndexUrl"

    & uv pip install --force-reinstall --index-url $IndexUrl $torchPkg $visPkg
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

function Install-Cpu {
    Write-Host ""
    Write-Host "Installing CPU torch/torchvision fallback"
    & uv pip install --force-reinstall "torch==$TorchVersion" "torchvision==$TorchvisionVersion"
    if ($LASTEXITCODE -ne 0) { throw "cpu pip install failed" }
}

if ($DoSync) {
    Write-Host "Running: uv sync --extra sleap"
    & uv sync --extra sleap
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
}

Write-Host "Testing CUDA availability after CUDA wheel installs..."

$candidates = @(
    @{ Name = "cu130"; Index = "https://download.pytorch.org/whl/cu130"; Suffix = "cu130" },
    @{ Name = "cu121"; Index = "https://download.pytorch.org/whl/cu121"; Suffix = "cu121" },
    @{ Name = "cu118"; Index = "https://download.pytorch.org/whl/cu118"; Suffix = "cu118" }
)

$installedOk = $false
foreach ($c in $candidates) {
    Write-Host ""
    Write-Host "Trying $($c.Name)..."
    Install-TorchTvision -IndexUrl $c.Index -TorchWheelSuffix $c.Suffix -VisionWheelSuffix $c.Suffix
    $ok = Test-CudaAvailable
    if ($ok) {
        Write-Host ""
        Write-Host "CUDA is AVAILABLE with $($c.Name)."
        $installedOk = $true
        break
    }
    Write-Host "CUDA not available with $($c.Name). Continuing fallback..."
}

if (-not $installedOk) {
    Install-Cpu
    if (Test-CudaAvailable) {
        Write-Host "Unexpected: CUDA reported available after CPU install."
    } else {
        Write-Host ""
        Write-Host "CUDA still not available. Using CPU torch."
    }
}

Write-Host ""
Write-Host "Final verification:"
& uv run python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('device_count', torch.cuda.device_count()); print('torch.version.cuda', torch.version.cuda)"

