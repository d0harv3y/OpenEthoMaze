"""Entry point: python -m maze.controller.acquisition (after install)."""

import argparse
from typing import Sequence

from .app_shell import run_mode_gui


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Maze acquisition GUI (VAST default, optional RAM mode)"
    )
    p.add_argument(
        "--debug-log",
        action="store_true",
        default=False,
        help="Write DEBUG-level messages to the log file (default: off, only INFO/WARNING/ERROR)",
    )
    p.add_argument(
        "-d", "--dev",
        action="store_true",
        default=False,
        help="Enable dev features (e.g. Flash firmware button in MC panel).",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--vast",
        dest="mode",
        action="store_const",
        const="vast",
        help="Run the circular VAST acquisition mode (default).",
    )
    mode.add_argument(
        "--ram",
        dest="mode",
        action="store_const",
        const="ram",
        help="Run the radial-arm acquisition mode.",
    )
    p.set_defaults(mode="vast")
    # Leave argv for Qt; only parse known args so Qt doesn't see unknown ones
    return p.parse_known_args(argv)[0]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GUI. Returns exit code (0 = success)."""
    args = _parse_args(argv)

    # Import-order workaround:
    # Some environments crash when importing `sleap_nn` (via lightning/torchmetrics/
    # matplotlib) after PySide has initialized shiboken signature machinery.
    # Preloading here keeps the later lazy SLEAP load path from triggering that bug.
    if args.mode == "vast":
        try:
            import sleap_nn.inference.predictors  # noqa: F401
        except Exception:
            # SLEAP will be unavailable in the GUI, but the controller can still run.
            pass

    return run_mode_gui(args.mode, debug_log=args.debug_log, dev=args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
