"""Regression: pipeline menu flags must be importable when GUI extra is present."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")

from maze.controller.acquisition.gui import pipeline_dialogs


def test_has_pipeline_dialogs_exported_when_qt_available() -> None:
    assert pipeline_dialogs.HAS_QT is True
    assert pipeline_dialogs.HAS_PIPELINE_DIALOGS is True
