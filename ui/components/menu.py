from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout


class MenuPanel(QFrame):
    """Left menu: page buttons (exclusive) plus action buttons below a divider."""

    page_selected = Signal(str)
    action_triggered = Signal(str)

    def __init__(self, pages: list[tuple[str, str]], actions: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(170)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(6)
        head = QLabel("MENU")
        head.setObjectName("menuHeader")
        head.setStyleSheet("qproperty-alignment: AlignCenter;")
        lay.addWidget(head)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in pages:
            b = QPushButton(label)
            b.setObjectName("menuButton")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.select(k))
            self._group.addButton(b)
            self._buttons[key] = b
            lay.addWidget(b)
        lay.addSpacing(8)
        for key, label in actions:
            b = QPushButton(label)
            b.setObjectName("menuButton")
            b.clicked.connect(lambda _=False, k=key: self.action_triggered.emit(k))
            lay.addWidget(b)
        lay.addStretch(1)

    def select(self, key: str) -> None:
        self._buttons[key].setChecked(True)
        self.page_selected.emit(key)
