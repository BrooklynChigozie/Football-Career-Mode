from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderScreen(QWidget):
    """Stand-in for screens that are not built yet (club selection, squad, finances, settings)."""

    def __init__(self, title: str, note: str = "Coming soon.", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        n = QLabel(note)
        n.setObjectName("pageSubtitle")
        lay.addWidget(t)
        lay.addWidget(n)
        lay.addStretch(1)
