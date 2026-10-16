from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from services import lineup


class PitchWidget(QWidget):
    """Draws the pitch and the starting XI in the chosen formation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assignment: list[tuple[lineup.Slot, object | None]] = []
        self.setMinimumSize(260, 420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_lineup(self, assignment) -> None:
        self._assignment = assignment
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.setBrush(QColor("#1c5a37"))
        p.setPen(QPen(QColor("#4fa974"), 2))
        p.drawRoundedRect(r, 10, 10)
        line = QPen(QColor(255, 255, 255, 90), 2)
        p.setPen(line)
        p.setBrush(Qt.NoBrush)
        p.drawLine(r.left(), r.center().y(), r.right(), r.center().y())
        p.drawEllipse(r.center(), r.width() * 0.13, r.width() * 0.13)
        bw, bh = r.width() * 0.5, r.height() * 0.13
        p.drawRect(QRectF(r.center().x() - bw / 2, r.top(), bw, bh))
        p.drawRect(QRectF(r.center().x() - bw / 2, r.bottom() - bh, bw, bh))
        gw, gh = r.width() * 0.24, r.height() * 0.05
        p.drawRect(QRectF(r.center().x() - gw / 2, r.top(), gw, gh))
        p.drawRect(QRectF(r.center().x() - gw / 2, r.bottom() - gh, gw, gh))

        name_font = QFont(self.font())
        name_font.setPointSize(8)
        name_font.setBold(True)
        for slot, player in self._assignment:
            cx, cy = r.left() + slot.x * r.width(), r.top() + slot.y * r.height()
            card = QRectF(cx - 33, cy - 22, 66, 44)
            p.setPen(QPen(QColor("#6fd49a"), 1.5))
            p.setBrush(QColor("#143e29") if player else QColor(20, 62, 41, 90))
            p.drawRoundedRect(card, 5, 5)
            p.setFont(name_font)
            p.setPen(QColor("#ffffff"))
            if player:
                last = player.name.split(". ", 1)[-1]
                p.drawText(card.adjusted(2, 2, -2, -16), Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextWordWrap, last)
                p.setPen(QColor("#9be3b9"))
                p.drawText(card.adjusted(2, 26, -2, -2), Qt.AlignCenter, f"{player.position} · {player.overall}")
            else:
                p.setPen(QColor("#9be3b9"))
                p.drawText(card, Qt.AlignCenter, slot.label)
