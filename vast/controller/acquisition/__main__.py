"""Entry point: python -m vast.controller.acquisition (after install)."""

import argparse

from .gui.main_window import run_gui


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VAST Controller — circular open field behavior controller")
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
    # Leave argv for Qt; only parse known args so Qt doesn't see unknown ones
    return p.parse_known_args()[0]


def main() -> int:
    """Run the GUI. Returns exit code (0 = success)."""
    args = _parse_args()
    return run_gui(debug_log=args.debug_log, dev=args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
