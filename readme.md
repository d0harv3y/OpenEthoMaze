placeholder for Open Rodent Maze
its sloppy

things to install  
vimba sdk (camera dependent)  
cuda (gpu dependent)  
python manager (3.12 for other dependencies... torchvision?)  

avrdude for firmware flashing

uv  
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

enable jumbo frames (camera dependent)


cd to/your/repo/root  
uv sync --extra gui --extra sleap --extra kpms --reinstall-package torch --reinstall-package torchvision  
verify  
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda,  torch.cuda.device_count())"  


run from root:
uv run vast-daq  

