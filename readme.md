placeholder for Open Rodent Maze

things to install  
vimba sdk (camera dependent)  
cuda (gpu dependent)  
python manager (3.12 for other dependencies... torchvision?)  

uv  
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

enable jumbo frames (camera dependent)

cd to repo root  
uv sync --extra gui --extra sleap --reinstall-package torch --reinstall-package torchvision  
verify  
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda,  torch.cuda.device_count())"  


to run — cd to/your/repo/root  
uv run vast-daq  

