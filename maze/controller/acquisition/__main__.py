"""Entry point: python -m maze.controller.acquisition (after install)."""

import argparse
import os
from typing import Sequence

from .app_shell import run_mode_gui


def _preload_sleap_stack_before_qt() -> None:
    """
    Import ``sleap_nn`` (Lightning/torchmetrics/matplotlib/…) before ``QApplication``.

    If ``sleap_nn`` is first imported after PySide/shiboken is active, some stacks
    hit ``dateutil`` → ``six.moves`` while shiboken hooks ``inspect``; combined
    with torch's ``inspect.getfile`` patch this can raise
    ``AttributeError: '_SixMetaPathImporter' object has no attribute '_path'``.
    Preloading avoids that ordering bug for both VAST and RAM.

    Set ``MAZE_ACQ_SKIP_SLEAP_PRELOAD=1`` to skip (e.g. broken torch/lightning import).
    """
    if os.environ.get("MAZE_ACQ_SKIP_SLEAP_PRELOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        import sleap_nn.inference.predictors  # noqa: F401
    except Exception:
        # SLEAP will be unavailable in the GUI, but the controller can still run.
        pass


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

    _preload_sleap_stack_before_qt()

    return run_mode_gui(args.mode, debug_log=args.debug_log, dev=args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
