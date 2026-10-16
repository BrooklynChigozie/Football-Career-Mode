from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Panel(QFrame):
    """Rounded framed container. Add widgets via .body (a QVBoxLayout)."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setObjectName("sectionTitle")
            outer.addWidget(t)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body, 1)


def page_header(title: str, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("pageSubtitle")
        lay.addWidget(s)
    return w


def fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e9:
        return f"{sign}{v / 1e9:.2f}B"
    if v >= 1e6:
        return f"{sign}{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{sign}{v / 1e3:.0f}K"
    return f"{sign}{v:.0f}"
