# Demos

Non-production examples. Implementations live in **`maze/cli/`**; install via `[project.scripts]` in `pyproject.toml`.

| Demo | Command | Module |
|------|---------|--------|
| Langfuse trace hierarchy | `uv run --with langfuse maze-langfuse-demo` | `maze.cli.langfuse_demo` |

Shim: `uv run python scripts/demos/langfuse_demo.py` delegates to the same entry point.

Requires Langfuse env vars (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`). Not used by acquisition or batch pipelines.
