from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    """Navigation sidebar. Emits page_selected(key) when a nav button is clicked."""

    page_selected = Signal(str)
    logout_requested = Signal()

    def __init__(self, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(4)
        brand = QLabel("Career Mode")
        brand.setObjectName("brand")
        lay.addWidget(brand)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in items:
            b = QPushButton(label)
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.select(k))
            self._group.addButton(b)
            self._buttons[key] = b
            lay.addWidget(b)

        lay.addStretch(1)
        self._user = QLabel("")
        self._user.setObjectName("userLabel")
        lay.addWidget(self._user)
        out = QPushButton("Log out")
        out.clicked.connect(self.logout_requested)
        lay.addWidget(out)

    def set_user(self, username: str) -> None:
        self._user.setText(f"Signed in as {username}")

    def select(self, key: str) -> None:
        self._buttons[key].setChecked(True)
        self.page_selected.emit(key)
