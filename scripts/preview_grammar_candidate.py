"""Backward-compatible launcher. Prefer `uv run maze-preview-grammar-candidate`."""
from maze.cli.preview_grammar_candidate import main

if __name__ == "__main__":
    raise SystemExit(main())
