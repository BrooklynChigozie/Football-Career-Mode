from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    """Small card: title, big value, optional note. Reused on dashboard and finance screens."""

    def __init__(self, title: str, value: str, note: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(4)
        self._title = QLabel(title.upper())
        self._title.setObjectName("cardTitle")
        self._value = QLabel(value)
        self._value.setObjectName("cardValue")
        self._note = QLabel(note)
        self._note.setObjectName("cardNote")
        for w in (self._title, self._value, self._note):
            lay.addWidget(w)
        self._note.setVisible(bool(note))

    def set_value(self, value: str, note: str | None = None) -> None:
        self._value.setText(value)
        if note is not None:
            self._note.setText(note)
            self._note.setVisible(bool(note))
