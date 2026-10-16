from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.components.panel import Panel, page_header


class PlaceholderScreen(QWidget):
    """Page for features owned by the simulation engine (transfers, statistics)."""

    def __init__(self, title: str, note: str, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(page_header(title, note))
        lay.addWidget(Panel("Coming with the engine"))
        lay.addStretch(1)

    def refresh(self) -> None:
        pass
