"""Tactical board: drag-and-drop player markers (avatars, role labels, familiarity rings) and tactic arrows."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsScene, QGraphicsView)

W, H = 560.0, 760.0
SKIN = ["#f1c9a5", "#e0ac86", "#c68a64", "#a06a47", "#7a4a31", "#5c3624"]
HAIR = ["#1b1410", "#3a2417", "#6b4a2b", "#b88a4a", "#222"]
GROUP_COLOR = {"GK": "#f2c94c", "DEF": "#4fb4e8", "MID": "#3ddc84", "ATT": "#ff7a7a"}
DEF, MID = {"CB", "LB", "RB"}, {"CDM", "CM", "CAM", "LM", "RM"}


def group_color(label: str) -> QColor:
    g = "GK" if label == "GK" else "DEF" if label in DEF else "MID" if label in MID else "ATT"
    return QColor(GROUP_COLOR[g])


def slot_pos(slot) -> QPointF:
    return QPointF(40 + slot.x * (W - 80), 46 + slot.y * (H - 110))


class PlayerMarker(QGraphicsObject):
    """A draggable avatar. Colour ring = position line; outer arc = familiarity with the chosen role."""
    R = 27

    def __init__(self, index: int, slot):
        super().__init__()
        self.index, self.slot = index, slot
        self.player, self.role, self.familiarity = None, "", 60.0
        self.home = slot_pos(slot)
        self.selected_mark = False
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(self.home)
        self.setZValue(5)
        self.setCursor(Qt.OpenHandCursor)

    def set_player(self, player, role: str, fam: float) -> None:
        self.player, self.role, self.familiarity = player, role, fam
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-70, -self.R - 8, 140, self.R * 2 + 52)

    def paint(self, p: QPainter, *_):
        p.setRenderHint(QPainter.Antialiasing)
        R = self.R
        col = group_color(self.slot.label)
        pl = self.player
        # familiarity ring
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#1b2c4d"), 4))
        p.drawEllipse(QPointF(0, 0), R + 5, R + 5)
        if pl:
            f = self.familiarity
            fc = QColor("#3ddc84") if f >= 70 else QColor("#f2c94c") if f >= 45 else QColor("#ff7a7a")
            p.setPen(QPen(fc, 4, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(-R - 5, -R - 5, 2 * R + 10, 2 * R + 10), 90 * 16, int(-360 * 16 * f / 100))
        # avatar
        p.setPen(QPen(col, 2))
        p.setBrush(QColor("#143e29") if pl else QColor(20, 62, 41, 120))
        p.drawEllipse(QPointF(0, 0), R, R)
        if pl:
            clip = QPainterPath()
            clip.addEllipse(QPointF(0, 0), R - 1, R - 1)
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.NoPen)
            p.setBrush(col.darker(130))                      # kit
            p.drawEllipse(QPointF(0, R + 4), R * 0.85, R * 0.7)
            p.setBrush(QColor(SKIN[pl.id % len(SKIN)]))       # head
            p.drawEllipse(QPointF(0, -4), R * 0.42, R * 0.48)
            p.setBrush(QColor(HAIR[(pl.id // 7) % len(HAIR)]))  # hair
            hair = QPainterPath()
            hair.addEllipse(QPointF(0, -9), R * 0.44, R * 0.36)
            p.drawPath(hair)
            p.setBrush(QColor("#10161f"))                     # eyes
            p.drawEllipse(QPointF(-5, -3), 1.6, 1.6)
            p.drawEllipse(QPointF(5, -3), 1.6, 1.6)
            p.restore()
            # rating chip
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(R - 14, -R - 4, 24, 15), 6, 6)
            f2 = QFont(p.font())
            f2.setPointSize(8)
            f2.setBold(True)
            p.setFont(f2)
            p.setPen(QColor("#07101c"))
            p.drawText(QRectF(R - 14, -R - 4, 24, 15), Qt.AlignCenter, str(pl.overall))
        else:
            p.setPen(QColor("#9be3b9"))
            p.drawText(QRectF(-R, -9, 2 * R, 18), Qt.AlignCenter, self.slot.label)
        if self.selected_mark:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#8fb8ff"), 2, Qt.DashLine))
            p.drawEllipse(QPointF(0, 0), R + 10, R + 10)
        f3 = QFont(p.font())
        f3.setPointSize(9)
        f3.setBold(True)
        p.setFont(f3)
        p.setPen(QColor("#ffffff"))
        name = pl.name.split(" ", 1)[-1] if pl else ""
        p.drawText(QRectF(-52, R + 8, 104, 14), Qt.AlignCenter, name)
        f3.setPointSize(7)
        f3.setBold(False)
        p.setFont(f3)
        p.setPen(QColor("#9be3b9"))
        p.drawText(QRectF(-70, R + 22, 140, 13), Qt.AlignCenter, self.role if pl else "")

    def mousePressEvent(self, e):
        self.setCursor(Qt.ClosedHandCursor)
        self.setZValue(20)
        self.scene().views()[0].marker_clicked.emit(self.index)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(5)
        self.scene().views()[0].marker_dropped(self)


class BoardView(QGraphicsView):
    """The pitch. Emits swapped(i, j) when a marker is dropped on another, replaced(slot, player_id) for list drops."""
    swapped = Signal(int, int)
    replaced = Signal(int, int)
    marker_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_ = QGraphicsScene(0, 0, W, H, self)
        self.setScene(self.scene_)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QColor("#0d1729"))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.markers: list[PlayerMarker] = []
        self.arrows: list = []
        self._selected = -1
        self._draw_pitch()

    def _draw_pitch(self) -> None:
        s = self.scene_
        r = QRectF(14, 14, W - 28, H - 28)
        pitch = s.addRect(r, QPen(QColor("#4fa974"), 2), QBrush(QColor("#1c5a37")))
        pitch.setZValue(0)
        for i in range(8):                                   # mowing stripes
            if i % 2 == 0:
                st = s.addRect(QRectF(14, 14 + i * (H - 28) / 8, W - 28, (H - 28) / 8), QPen(Qt.NoPen), QBrush(QColor(255, 255, 255, 10)))
                st.setZValue(0.1)
        line = QPen(QColor(255, 255, 255, 110), 2)
        s.addLine(14, H / 2, W - 14, H / 2, line)
        s.addEllipse(QRectF(W / 2 - 62, H / 2 - 62, 124, 124), line)
        for top in (True, False):
            y = 14 if top else H - 14 - 120
            s.addRect(QRectF(W / 2 - 140, y, 280, 120), line)
            y2 = 14 if top else H - 14 - 46
            s.addRect(QRectF(W / 2 - 66, y2, 132, 46), line)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fitInView(self.scene_.sceneRect(), Qt.KeepAspectRatio)

    def build(self, slots) -> None:
        for m in self.markers:
            self.scene_.removeItem(m)
        self.markers = [PlayerMarker(i, s) for i, s in enumerate(slots)]
        for m in self.markers:
            self.scene_.addItem(m)

    def select(self, index: int) -> None:
        self._selected = index
        for m in self.markers:
            m.selected_mark = m.index == index
            m.update()

    def marker_dropped(self, marker: PlayerMarker) -> None:
        target = self._nearest(marker.pos(), exclude=marker.index, radius=70)
        marker.setPos(marker.home)
        if target is not None:
            self.swapped.emit(marker.index, target)

    def _nearest(self, pos: QPointF, exclude: int = -1, radius: float = 80) -> int | None:
        best, bd = None, radius
        for m in self.markers:
            if m.index == exclude:
                continue
            d = math.hypot(m.pos().x() - pos.x(), m.pos().y() - pos.y())
            if d < bd:
                best, bd = m.index, d
        return best

    # drops from the reserves list
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-player"):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat("application/x-player"):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not e.mimeData().hasFormat("application/x-player"):
            return
        pid = int(bytes(e.mimeData().data("application/x-player")).decode())
        idx = self._nearest(self.mapToScene(e.position().toPoint()), radius=90)
        if idx is not None:
            self.replaced.emit(idx, pid)
            e.acceptProposedAction()

    # ---- tactic arrows ----
    def set_arrows(self, pressing: str, passing: str) -> None:
        for a in self.arrows:
            self.scene_.removeItem(a)
        self.arrows = []
        by_y = sorted(self.markers, key=lambda m: m.home.y())
        press = {"Low": 1, "Medium": 2, "High": 3}[pressing]
        press_col = QColor("#ffae42")
        press_col.setAlpha(190)
        for m in by_y[:4 + press]:               # most advanced players press upwards
            if m.slot.label == "GK":
                continue
            self._arrow(m.home + QPointF(0, -34), m.home + QPointF(0, -34 - 22 * press), press_col, 2 + press, 3)
        pass_col = QColor("#7fd6ff")
        pass_col.setAlpha(170)
        ms = [m for m in self.markers]
        if passing in ("Short", "Mixed"):
            for m in ms:
                near = sorted((o for o in ms if o is not m and o.home.y() <= m.home.y() + 1),
                              key=lambda o: math.hypot(o.home.x() - m.home.x(), o.home.y() - m.home.y()))
                if near and math.hypot(near[0].home.x() - m.home.x(), near[0].home.y() - m.home.y()) < 190 and m.slot.label != "ST":
                    self._arrow(m.home + (near[0].home - m.home) * 0.3, m.home + (near[0].home - m.home) * 0.7, pass_col, 2, 2)
        if passing in ("Direct", "Mixed"):
            gk = next((m for m in ms if m.slot.label == "GK"), None)
            fwd = [m for m in by_y[:3]]
            if gk and fwd:
                tgt = fwd[len(fwd) // 2]
                self._arrow(gk.home + QPointF(0, -34), tgt.home + QPointF(0, 40), pass_col, 3, 4, dash=True)
            for m in [x for x in ms if x.slot.label in ("CB",)][:2]:
                tgt = fwd[0 if m.home.x() < W / 2 else -1]
                self._arrow(m.home + QPointF(0, -34), tgt.home + QPointF(0, 40), pass_col, 2, 3, dash=True)

    def _arrow(self, a: QPointF, b: QPointF, color: QColor, width: float, z: float, dash: bool = False) -> None:
        path = QPainterPath(a)
        path.lineTo(b)
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        for d in (math.pi * 0.84, -math.pi * 0.84):
            path.moveTo(b)
            path.lineTo(b + QPointF(math.cos(ang + d) * 11, math.sin(ang + d) * 11))
        item = QGraphicsPathItem(path)
        pen = QPen(color, width, Qt.DashLine if dash else Qt.SolidLine, Qt.RoundCap)
        item.setPen(pen)
        item.setZValue(z)
        self.scene_.addItem(item)
        self.arrows.append(item)
