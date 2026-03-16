"""
Panel section widget with a title and optional settings (gear) button.
Used in place of QGroupBox when a quick-link to the Settings dialog is desired.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Signal
    HAS_QT = True
except ImportError:
    HAS_QT = False


class SectionWithSettings(QFrame):
    """
    A frame that looks like a group box: border, header row (bold title + gear button), and content area.
    Emits settings_clicked when the gear is pressed. Call content_layout() to add widgets below the header.
    When collapsible=True, the header shows an arrow to expand/collapse the content.
    """

    settings_clicked = Signal()

    def __init__(
        self,
        title: str,
        settings_tooltip: str = "Open Settings",
        parent: Optional[QWidget] = None,
        *,
        collapsible: bool = False,
        default_collapsed: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        header = QHBoxLayout()
        self._collapsible = collapsible
        self._collapse_btn = None
        if collapsible:
            self._collapse_btn = QToolButton()
            self._collapse_btn.setFixedSize(22, 22)
            self._collapse_btn.setToolTip("Collapse/expand section")
            self._collapse_btn.clicked.connect(self._on_toggle_collapse)
            header.addWidget(self._collapse_btn)
        title_label = QLabel(title)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        header.addWidget(title_label)
        header.addStretch()
        self._settings_btn = QToolButton()
        self._settings_btn.setText("\u2699")  # Unicode gear (U+2699)
        self._settings_btn.setToolTip(settings_tooltip)
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        header.addWidget(self._settings_btn)
        layout.addLayout(header)
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self._content_widget)
        self._content_visible = not default_collapsed
        self._content_widget.setVisible(self._content_visible)
        if collapsible:
            self._update_collapse_arrow()

    def _on_toggle_collapse(self) -> None:
        if not self._collapsible:
            return
        self._content_visible = not self._content_visible
        self._content_widget.setVisible(self._content_visible)
        self._update_collapse_arrow()

    def _update_collapse_arrow(self) -> None:
        if self._collapse_btn is not None:
            self._collapse_btn.setText("\u25bc" if self._content_visible else "\u25b6")  # ▼ / ▶

    def content_layout(self) -> QVBoxLayout:
        """Return the layout to which panel content (widgets) should be added."""
        return self._content_layout
