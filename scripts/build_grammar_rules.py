"""Shim: ``uv run maze-build-grammar-rules``."""
from maze.cli.build_grammar_rules import main

if __name__ == "__main__":
    raise SystemExit(main())
