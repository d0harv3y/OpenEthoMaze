"""Backward-compatible launcher. Prefer `uv run maze-preview-grammar-candidate-grid`."""
from maze.cli.preview_grammar_candidate_grid import main

if __name__ == "__main__":
    raise SystemExit(main())
