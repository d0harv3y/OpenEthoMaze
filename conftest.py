"""Repo-root pytest hooks (pytest 9+ requires ``pytest_plugins`` at rootdir, not nested)."""

pytest_plugins = ["controller.local_service.fixtures"]
