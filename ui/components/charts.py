"""Small custom-painted widgets: radar (hexagon) chart, ring gauge, glowing momentum bar."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget


class RadarChart(QWidget):
    """Hexagon/radar chart for six attributes; supports comparing two series."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels: list[str] = []
        self.series: list[tuple[str, list[float], str]] = []
        self.setMinimumSize(240, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, labels, series) -> None:
        self.labels, self.series = list(labels), list(series)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(self.labels) or 6
        c = QPointF(self.width() / 2, self.height() / 2 + 4)
        rad = min(self.width(), self.height()) / 2 - 34
        if rad <= 10:
            return

        def pt(i, frac):
            a = -math.pi / 2 + 2 * math.pi * i / n
            return QPointF(c.x() + math.cos(a) * rad * frac, c.y() + math.sin(a) * rad * frac)

        p.setPen(QPen(QColor("#2a3d63"), 1))
        for ring in (0.25, 0.5, 0.75, 1.0):
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(QPolygonF([pt(i, ring) for i in range(n)]))
        for i in range(n):
            p.drawLine(c, pt(i, 1.0))
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        p.setPen(QColor("#8fa3c7"))
        for i, lab in enumerate(self.labels):
            q = pt(i, 1.17)
            p.drawText(QRectF(q.x() - 38, q.y() - 9, 76, 18), Qt.AlignCenter, lab)
        for name, vals, color in self.series:
            poly = QPolygonF([pt(i, max(0.02, min(1.0, v / 100))) for i, v in enumerate(vals)])
            col = QColor(color)
            fill = QColor(col)
            fill.setAlpha(70)
            p.setPen(QPen(col, 2))
            p.setBrush(QBrush(fill))
            p.drawPolygon(poly)
            p.setBrush(col)
            for i, v in enumerate(vals):
                p.drawEllipse(pt(i, max(0.02, min(1.0, v / 100))), 3, 3)


class Gauge(QWidget):
    """Ring gauge 0-100 with a big number in the middle."""

    def __init__(self, caption: str = "", parent=None):
        super().__init__(parent)
        self.value, self.caption = 0.0, caption
        self.setMinimumSize(130, 130)

    def set_value(self, v: float) -> None:
        self.value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 16
        r = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        p.setPen(QPen(QColor("#1b2c4d"), 11, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 225 * 16, -270 * 16)
        col = QColor("#3ddc84") if self.value >= 65 else QColor("#f2c94c") if self.value >= 45 else QColor("#ff7a7a")
        p.setPen(QPen(col, 11, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 225 * 16, int(-270 * 16 * self.value / 100))
        p.setPen(QColor("#ffffff"))
        f = QFont(self.font())
        f.setPointSize(22)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r.adjusted(0, -6, 0, -6), Qt.AlignCenter, f"{self.value:.0f}")
        f.setPointSize(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#8fa3c7"))
        p.drawText(r.adjusted(0, 26, 0, 26), Qt.AlignCenter, self.caption)


class MomentumBar(QWidget):
    """Glowing tug-of-war bar. value -1 (away dominates) .. +1 (home dominates)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value, self.target = 0.0, 0.0
        self.home_color, self.away_color = QColor("#3ddc84"), QColor("#ff6b6b")
        self.setFixedHeight(46)

    def set_value(self, v: float, animate: bool = True) -> None:
        self.target = max(-1.0, min(1.0, v))
        if not animate:
            self.value = self.target
        self.update()

    def tick(self) -> bool:
        """Ease towards the target; returns True while still moving."""
        d = self.target - self.value
        if abs(d) < 0.004:
            self.value = self.target
            return False
        self.value += d * 0.18
        self.update()
        return True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(4, 14, self.width() - 8, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0d1729"))
        p.drawRoundedRect(r, 9, 9)
        split = r.left() + r.width() * (0.5 + self.value / 2)
        for color, a, b in ((self.home_color, r.left(), split), (self.away_color, split, r.right())):
            g = QLinearGradient(a, 0, b, 0)
            g.setColorAt(0, color.darker(150))
            g.setColorAt(1, color)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(a, r.top(), max(0.0, b - a), r.height()), 9, 9)
        # glow at the tug point
        glow = QRadialGradient(QPointF(split, r.center().y()), 26)
        lead = self.home_color if self.value >= 0 else self.away_color
        c0 = QColor(lead)
        c0.setAlpha(170)
        c1 = QColor(lead)
        c1.setAlpha(0)
        glow.setColorAt(0, c0)
        glow.setColorAt(1, c1)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(split, r.center().y()), 26, 22)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(split - 2, r.top() - 4, 4, r.height() + 8), 2, 2)
        f = QFont(self.font())
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#8fa3c7"))
        p.drawText(QRectF(4, 0, 160, 13), Qt.AlignLeft | Qt.AlignVCenter, "MOMENTUM")
