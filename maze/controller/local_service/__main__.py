"""CLI entry for the unified local HTTP service (Phase B)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_HOST, DEFAULT_PORT, LocalServiceConfig, build_config


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="maze-local-service",
        description=(
            "Long-lived localhost Flask service: h5web + h5grove and /orm/* "
            "(discover, detect, health)."
        ),
    )
    p.add_argument(
        "--data-root",
        metavar="DIR",
        required=True,
        help="Sandbox root for HDF5 paths (?file= relative to this directory).",
    )
    p.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind address (default: {DEFAULT_HOST}).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Listen port (default: {DEFAULT_PORT}).",
    )
    p.add_argument(
        "--llm-model",
        metavar="PATH",
        help="GGUF path for llama-cpp-python (overrides MAZE_LLM_GGUF; requires local-service extra).",
    )
    return p


def _missing_dependency_messages() -> list[str]:
    missing: list[str] = []
    try:
        import flask  # noqa: F401
    except ImportError:
        missing.append("flask (core dependency; run: uv sync)")

    try:
        import h5grove  # noqa: F401
    except ImportError:
        missing.append("h5grove (core dependency; run: uv sync)")

    try:
        import waitress  # noqa: F401
    except ImportError:
        missing.append("waitress (install with: uv sync --extra local-service)")

    return missing


def _require_runtime_dependencies() -> None:
    missing = _missing_dependency_messages()
    if not missing:
        return
    print("error: maze-local-service is missing required dependencies:", file=sys.stderr)
    for line in missing:
        print(f"  - {line}", file=sys.stderr)
    print(
        "\nInstall with: uv sync --extra local-service",
        file=sys.stderr,
    )
    sys.exit(1)


def run_server(config: LocalServiceConfig) -> None:
    """Create the Flask app and block serving with waitress."""
    from waitress import serve

    from .app import create_local_app

    app = create_local_app(config)
    serve(app, host=config.host, port=config.port)


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _require_runtime_dependencies()

    config = build_config(
        Path(args.data_root),
        host=args.host,
        port=args.port,
        llm_model_path=args.llm_model,
    )
    config.sandbox()

    try:
        run_server(config)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
