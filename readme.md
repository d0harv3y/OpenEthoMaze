placeholder for Open Rodent Maze
its sloppy

mostly optional things to install  
vimba sdk (camera dependent)  
enable jumbo frames in device properties if that is something your camera does
~~cuda (gpu dependent)~~  
python manager (3.12 for other dependencies... torchvision?)  
avrdude for firmware flashing

uv  
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"



cd to/your/repo/root  
uv sync --extra gui --extra sleap --extra kpms --reinstall-package torch --reinstall-package torchvision  
verify  
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda,  torch.cuda.device_count())"  


run from root:
uv run maze-daq

explicit modes:
uv run maze-daq --vast
uv run maze-daq --ram

legacy RAM alias:
uv run maze-ram-daq

