from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from engine import lineup, tactics
from ui.components.board import BoardView
from ui.components.charts import Gauge
from ui.components.panel import Panel, page_header
from ui.context import GameContext


class ReserveList(QListWidget):
    """Players outside the XI; drag one onto a marker to bring him in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)

    def mimeData(self, items):
        m = QMimeData()
        if items:
            m.setData("application/x-player", str(items[0].data(Qt.UserRole)).encode())
        return m


class TacticsScreen(QWidget):
    """Tactical board: drag-and-drop XI, roles, familiarity rings, pressing/passing arrows, TER."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self._sel = 0
        self._loading = False
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        left = QVBoxLayout()
        left.addWidget(page_header("Tactics", "Drag players to swap them, or drag a reserve onto a marker."))
        self.board = BoardView()
        self.board.swapped.connect(self._swap)
        self.board.replaced.connect(self._replace)
        self.board.marker_clicked.connect(self._select)
        left.addWidget(self.board, 1)
        root.addLayout(left, 5)

        right = QVBoxLayout()
        right.setSpacing(12)
        p = Panel("Style")
        self.formation = QComboBox()
        self.formation.addItems(list(lineup.FORMATIONS))
        self.mentality = QComboBox()
        self.mentality.addItems(tactics.MENTALITIES)
        self.pressing = QComboBox()
        self.pressing.addItems(tactics.PRESSING)
        self.passing = QComboBox()
        self.passing.addItems(tactics.PASSING)
        for label, w in (("FORMATION", self.formation), ("MENTALITY", self.mentality),
                         ("PRESSING INTENSITY", self.pressing), ("PASSING STYLE", self.passing)):
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setObjectName("muted")
            row.addWidget(lab, 1)
            row.addWidget(w, 1)
            p.body.addLayout(row)
        self.warn = QLabel("")
        self.warn.setObjectName("muted")
        self.warn.setWordWrap(True)
        p.body.addWidget(self.warn)
        right.addWidget(p)

        r = Panel("Selected player")
        self.sel_label = QLabel("-")
        self.sel_label.setObjectName("accent")
        self.role = QComboBox()
        self.role_info = QLabel("")
        self.role_info.setObjectName("muted")
        self.role_info.setWordWrap(True)
        r.body.addWidget(self.sel_label)
        r.body.addWidget(self.role)
        r.body.addWidget(self.role_info)
        right.addWidget(r)

        t = Panel("Tactical effectiveness")
        row = QHBoxLayout()
        self.gauge = Gauge("TER")
        row.addWidget(self.gauge)
        bars = QVBoxLayout()
        self.bars = {}
        for key, label in (("understanding", "Tactical understanding"), ("ability", "Player ability"), ("buy_in", "Player buy-in")):
            lab = QLabel(label)
            lab.setObjectName("muted")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bars.addWidget(lab)
            bars.addWidget(bar)
            self.bars[key] = bar
        row.addLayout(bars, 1)
        t.body.addLayout(row)
        right.addWidget(t)

        res = Panel("Reserves")
        self.reserves = ReserveList()
        self.reserves.setMinimumHeight(140)
        res.body.addWidget(self.reserves, 1)
        self.auto_btn = QPushButton("Auto assign best XI")
        self.auto_btn.clicked.connect(self._auto)
        res.body.addWidget(self.auto_btn)
        right.addWidget(res, 1)
        root.addLayout(right, 3)

        self.formation.currentTextChanged.connect(self._formation)
        self.mentality.currentTextChanged.connect(lambda v: self._style("mentality", v))
        self.pressing.currentTextChanged.connect(lambda v: self._style("pressing", v))
        self.passing.currentTextChanged.connect(lambda v: self._style("passing", v))
        self.role.currentTextChanged.connect(self._role)

    @property
    def eng(self):
        return self.ctx.engine

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        self._loading = True
        uc = self.ctx.session.club_id
        t = self.eng.tactics_of(uc)
        for box, v in ((self.formation, t["formation"]), (self.mentality, t["mentality"]),
                       (self.pressing, t["pressing"]), (self.passing, t["passing"])):
            box.setCurrentText(v)
        setup = self.eng.team_setup(uc)
        if len(self.board.markers) != 11 or self.board.markers[0].slot is not setup.slots[0]:
            self.board.build(setup.slots)
        for i, (m, p) in enumerate(zip(self.board.markers, setup.xi)):
            role = setup.role_name(i)
            m.set_player(p, role, setup.familiarity.get((p.id, role), 60.0) if p else 0.0)
        self.board.set_arrows(t["pressing"], t["passing"])
        used = {p.id for p in setup.xi if p}
        self.reserves.clear()
        for p in self.eng.get_squad(uc):
            if p.id in used:
                continue
            tag = "  (injured)" if p.injured_weeks else "  (suspended)" if p.suspended_games else ""
            it = QListWidgetItem(f"{p.position:<4} {p.name}  ·  {p.overall}{tag}")
            it.setData(Qt.UserRole, p.id)
            if tag:
                it.setForeground(Qt.red)
            self.reserves.addItem(it)
        rep = self.eng.tactical_report(uc)
        self.gauge.set_value(rep["ter"])
        self.bars["understanding"].setValue(int(rep["understanding"]))
        self.bars["ability"].setValue(int(max(0, min(100, (rep["ability"] - 50) * 2.2))))
        self.bars["buy_in"].setValue(int(rep["buy_in"]))
        self._loading = False
        self._select(min(self._sel, 10))

    # ---- interactions ----
    def _formation(self, f: str) -> None:
        if self._loading or f == self.eng.tactics_of(self.ctx.session.club_id)["formation"]:
            return
        self.eng.set_tactics(formation=f)
        self.warn.setText("New shape: players need time to learn it, so tactical understanding dropped.")
        self.refresh()

    def _style(self, key: str, value: str) -> None:
        if self._loading:
            return
        self.eng.set_tactics(**{key: value})
        self.refresh()

    def _ids(self):
        return [p.id if p else None for p in self.eng.team_setup(self.ctx.session.club_id).xi]

    def _swap(self, i: int, j: int) -> None:
        ids = self._ids()
        ids[i], ids[j] = ids[j], ids[i]
        self.eng.set_xi(ids)
        self.refresh()

    def _replace(self, slot_index: int, pid: int) -> None:
        ids = self._ids()
        if pid in ids:
            ids[ids.index(pid)] = ids[slot_index]
        ids[slot_index] = pid
        self.eng.set_xi(ids)
        self.refresh()

    def _auto(self) -> None:
        self.eng.auto_assign()
        self.refresh()

    def _select(self, i: int) -> None:
        self._sel = i
        self.board.select(i)
        setup = self.eng.team_setup(self.ctx.session.club_id)
        slot, p = setup.slots[i], setup.xi[i]
        self._loading = True
        self.role.clear()
        self.role.addItems([r.name for r in tactics.roles_for(slot.label)])
        self.role.setCurrentText(setup.role_name(i))
        self._loading = False
        if p:
            fam = setup.familiarity.get((p.id, setup.role_name(i)), 60.0)
            self.sel_label.setText(f"{p.name} · {slot.label} · {p.overall} OVR")
            self.role_info.setText(f"Role familiarity {fam:.0f}% · fitness {p.fitness}% · form {p.form:.1f}. "
                                   "Familiarity grows with training and playing the role.")
        else:
            self.sel_label.setText(f"Empty {slot.label} slot")
            self.role_info.setText("")

    def _role(self, name: str) -> None:
        if self._loading or not name:
            return
        self.eng.set_role(self._sel, name)
        self.refresh()
