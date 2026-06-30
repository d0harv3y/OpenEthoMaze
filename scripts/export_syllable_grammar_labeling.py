"""Shim: ``uv run maze-export-syllable-grammar-labeling``."""
from maze.cli.export_syllable_grammar_labeling import main

if __name__ == "__main__":
    raise SystemExit(main())
