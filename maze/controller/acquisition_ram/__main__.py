"""Entry point: python -m maze.controller.acquisition_ram."""

from .gui.main_window import run_gui


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
