"""Entry point: python -m maze.controller.acquisition.radial_arm."""

from ..__main__ import main as acquisition_main


def main() -> int:
    return acquisition_main(["--ram"])


if __name__ == "__main__":
    raise SystemExit(main())
