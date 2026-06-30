"""Shim: ``uv run maze-mine-syllable-grammar-candidates``."""
from maze.cli.mine_syllable_grammar_candidates import main

if __name__ == "__main__":
    raise SystemExit(main())
