from __future__ import annotations

from typing import Literal

from .gui.launcher import run_mode_gui

AcquisitionMode = Literal["vast", "ram"]

__all__ = ["AcquisitionMode", "run_mode_gui"]
