"""Animated 2D pitch for the match-day view: 22 moving dots and a ball driven by the live momentum."""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

HOME_COL, AWAY_COL = QColor("#3d8bff"), QColor("#ff6b6b")


class LivePitch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.slots = {"home": [], "away": []}     # list of (slot, player or None)
        self.momentum = 0.0
        self.phase = 0.0
        self.user_side = "home"
        self.flash = 0.0                          # goal flash 0..1
        self.flash_side = "home"
        self.rng = random.Random(5)
        self.ball = QPointF(0.5, 0.5)           # in pitch fractions (0..1) so it survives resizing
        self.ball_from = QPointF(0.5, 0.5)
        self.ball_to = QPointF(0.5, 0.5)
        self.ball_t, self.ball_dur, self.hold = 1.0, 0.6, 0.2
        self.carrier = None                      # (side, index) of the player holding the ball
        self.shot = False

    def set_teams(self, live) -> None:
        self.user_side = live.user_side or "home"
        self.update_lineups(live)

    def update_lineups(self, live) -> None:
        self.slots = {s: live.lineup(s) for s in ("home", "away")}

    def set_momentum(self, m: float) -> None:
        self.momentum = m

    def goal(self, side: str) -> None:
        self.flash, self.flash_side = 1.0, side
        self._shoot(side)

    def _shoot(self, side: str) -> None:
        """Ball flies into the goal the given side is attacking."""
        self.ball_from = QPointF(self.ball)
        self.ball_to = QPointF(1.0 if side == "home" else 0.0, 0.5 + self.rng.uniform(-0.05, 0.05))
        self.ball_t, self.ball_dur, self.hold, self.shot, self.carrier = 0.0, 0.7, 0.9, True, None

    def _frac(self, side: str, slot, i: int) -> QPointF:
        r = QRectF(0, 0, 1, 1)
        return self._pos(side, slot, i, r)

    def _next_pass(self) -> None:
        p_home = max(0.15, min(0.85, 0.5 + 0.3 * self.momentum))
        side = "home" if self.rng.random() < p_home else "away"
        att = abs(self.momentum) + 0.2 if (self.momentum >= 0) == (side == "home") else 0.2
        cands, weights = [], []
        for i, (slot, pl) in enumerate(self.slots[side]):
            if pl is None or slot.label == "GK" and self.rng.random() < 0.8:
                continue
            cands.append(i)
            weights.append(0.4 + (1 - slot.y) * 2.2 * att)
        if not cands:
            return
        i = self.rng.choices(cands, weights)[0]
        self.carrier = (side, i)
        self.ball_from = QPointF(self.ball)
        self.ball_to = self._frac(side, self.slots[side][i][0], i)
        d = math.hypot(self.ball_to.x() - self.ball_from.x(), self.ball_to.y() - self.ball_from.y())
        self.ball_t, self.ball_dur, self.shot = 0.0, 0.25 + d * 1.1, False
        self.hold = self.rng.uniform(0.2, 0.55)

    def _move_ball(self, dt: float) -> None:
        if self.ball_t < 1.0:
            self.ball_t = min(1.0, self.ball_t + dt / self.ball_dur)
            e = self.ball_t * self.ball_t * (3 - 2 * self.ball_t)
            if self.carrier and not self.shot:                      # track the receiver as he moves
                side, i = self.carrier
                self.ball_to = self._frac(side, self.slots[side][i][0], i)
            self.ball = QPointF(self.ball_from.x() + (self.ball_to.x() - self.ball_from.x()) * e,
                                self.ball_from.y() + (self.ball_to.y() - self.ball_from.y()) * e)
            return
        self.hold -= dt
        if self.carrier and not self.shot:                          # dribbles with the carrier
            side, i = self.carrier
            self.ball = self._frac(side, self.slots[side][i][0], i) + QPointF(0.012, 0.0)
        if self.hold <= 0:
            self.shot = False
            if self.ball.x() in (0.0, 1.0) or self.ball.x() > 0.99 or self.ball.x() < 0.01:
                self.ball = QPointF(0.5, 0.5)                       # kick-off after a goal
            self._next_pass()

    def advance(self, dt: float = 0.033) -> None:
        self.phase += dt
        self._move_ball(dt)
        self.flash = max(0.0, self.flash - dt * 0.8)
        self.update()

    def _pos(self, side: str, slot, i: int, r: QRectF) -> QPointF:
        depth = 1 - slot.y                          # 0 own goal .. 1 striker
        lateral = slot.x
        push = self.momentum if side == "home" else -self.momentum
        x_frac = 0.06 + depth * 0.46 + push * 0.12 * (0.4 + depth)
        y_frac = lateral if side == "home" else 1 - lateral
        x_frac = x_frac if side == "home" else 1 - x_frac
        wob = 0.012
        x_frac += math.sin(self.phase * 1.3 + i * 1.7 + (0 if side == "home" else 9)) * wob
        y_frac += math.cos(self.phase * 1.1 + i * 2.3) * wob * 1.6
        return QPointF(r.left() + x_frac * r.width(), r.top() + max(0.04, min(0.96, y_frac)) * r.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        p.setBrush(QColor("#1c5a37"))
        p.setPen(QPen(QColor("#4fa974"), 2))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(Qt.NoPen)
        for i in range(10):
            if i % 2 == 0:
                p.setBrush(QColor(255, 255, 255, 9))
                p.drawRect(QRectF(r.left() + i * r.width() / 10, r.top(), r.width() / 10, r.height()))
        if self.flash > 0:
            c = QColor(HOME_COL if self.flash_side == "home" else AWAY_COL)
            c.setAlpha(int(70 * self.flash))
            p.setBrush(c)
            p.drawRoundedRect(r, 10, 10)
        p.setPen(QPen(QColor(255, 255, 255, 100), 2))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
        p.drawEllipse(r.center(), r.height() * 0.15, r.height() * 0.15)
        bw, bh = r.width() * 0.15, r.height() * 0.55
        p.drawRect(QRectF(r.left(), r.center().y() - bh / 2, bw, bh))
        p.drawRect(QRectF(r.right() - bw, r.center().y() - bh / 2, bw, bh))
        gw, gh = r.width() * 0.05, r.height() * 0.26
        p.drawRect(QRectF(r.left(), r.center().y() - gh / 2, gw, gh))
        p.drawRect(QRectF(r.right() - gw, r.center().y() - gh / 2, gw, gh))
        f = QFont(self.font())
        f.setPointSize(7)
        f.setBold(True)
        p.setFont(f)
        pts = {}
        for side, col in (("home", HOME_COL), ("away", AWAY_COL)):
            for i, (slot, pl) in enumerate(self.slots[side]):
                if pl is None:
                    continue
                pt = self._pos(side, slot, i, r)
                pts[(side, i)] = pt
                if side == self.user_side:
                    p.setPen(QPen(QColor("#ffffff"), 2))
                else:
                    p.setPen(QPen(col.lighter(150), 1))
                p.setBrush(col)
                p.drawEllipse(pt, 9, 9)
                p.setPen(QColor("#ffffff"))
                p.drawText(QRectF(pt.x() - 14, pt.y() - 7, 28, 14), Qt.AlignCenter, str(pl.overall))
        # ball drifts with the momentum between the two attacks
        bx = r.left() + self.ball.x() * r.width()
        by = r.top() + self.ball.y() * r.height()
        p.setPen(QPen(QColor("#10161f"), 1.5))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(bx, by), 5.5, 5.5)
