placeholder for Open Rodent Maze

things to install
vimba sdk (camera dependent)
cuda (gpu dependent)
python manager (3.12 for other dependencies... torchvision?)

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

enable jumbo frames (camera dependent)

cd to repo root
uv sync --extra gui --extra sleap --reinstall-package torch --reinstall-package torchvision
verify
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda, torch.cuda.device_count())"


then to run
uv run vast-daq



//————— check gpu cuda version compatabilites ——— codec says:

cd "your\repo\root"

# 1) First, ensure sleap deps are present
uv sync --extra sleap

# 2) Then force-install the best torch wheel available for this machine
# Try CUDA 13 first
uv pip install --force-reinstall --index-url https://download.pytorch.org/whl/cu130 `
  "torch==2.10.0+cu130" "torchvision==0.25.0+cu130"

$ok = (uv run python -c "import torch; print(torch.cuda.is_available())")
if ($ok -ne "True") {
  # Fallback: CUDA 12.1
  uv pip install --force-reinstall --index-url https://download.pytorch.org/whl/cu121 `
    "torch==2.10.0+cu121" "torchvision==0.25.0+cu121"

  $ok2 = (uv run python -c "import torch; print(torch.cuda.is_available())")
  if ($ok2 -ne "True") {
    # Final fallback: CPU
    uv pip install --force-reinstall "torch==2.10.0" "torchvision==0.25.0"
  }
}

# Final verification
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda, torch.cuda.device_count())"