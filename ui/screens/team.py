from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from services import gamedata, lineup
from ui.components.panel import Panel, fmt_money, page_header
from ui.components.pitch import PitchWidget
from ui.components.table import SortItem, make_table
from ui.context import GameContext

RETIRING_AGE = 35


class TeamScreen(QWidget):
    """Squad table with Active/Reserve toggles, formation and strategy, and a pitch view."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self.squad = []
        self.active_ids: list[int] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        left = Panel()
        self.title = QLabel("Team")
        self.title.setObjectName("pageTitle")
        left.body.addWidget(self.title)
        controls = QHBoxLayout()
        self.formation = QComboBox()
        self.formation.addItems(list(lineup.FORMATIONS))
        self.strategy = QComboBox()
        self.strategy.addItems(lineup.STRATEGIES)
        self.auto_btn = QPushButton("Auto assign")
        controls.addWidget(self._labelled("FORMATION", self.formation))
        controls.addWidget(self._labelled("STRATEGY", self.strategy))
        controls.addWidget(self.auto_btn, 0)
        controls.addStretch(1)
        left.body.addLayout(controls)
        self.count_label = QLabel("")
        self.count_label.setObjectName("accent")
        left.body.addWidget(self.count_label)
        self.pills = QHBoxLayout()
        left.body.addLayout(self.pills)
        self.table = make_table(["POS", "PLAYER", "AGE", "OVR", "POT", "VALUE", "STATUS"], stretch_col=-1)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(6, hh.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 104)
        left.body.addWidget(self.table, 1)
        root.addWidget(left, 6)

        right = Panel()
        self.pitch = PitchWidget()
        right.body.addWidget(self.pitch, 1)
        root.addWidget(right, 4)

        self.formation.currentTextChanged.connect(self._formation_changed)
        self.strategy.currentTextChanged.connect(self._strategy_changed)
        self.auto_btn.clicked.connect(self.auto_assign)

    @staticmethod
    def _labelled(text: str, w: QWidget) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        l = QLabel(text)
        l.setObjectName("muted")
        v.addWidget(l)
        v.addWidget(w)
        return box

    # ---- data ----
    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        g = self.ctx.game
        self.title.setText(f"{self.ctx.session.club_name} Team")
        self.squad = self.ctx.squad()
        self.formation.blockSignals(True)
        self.formation.setCurrentText(gamedata.get_meta(g, "formation", "4-3-3"))
        self.formation.blockSignals(False)
        self.strategy.blockSignals(True)
        self.strategy.setCurrentText(gamedata.get_meta(g, "strategy", "Balanced"))
        self.strategy.blockSignals(False)
        saved = gamedata.get_meta(g, "active_ids")
        ids = {p.id for p in self.squad}
        self.active_ids = [i for i in (saved or []) if i in ids]
        if not self.active_ids:
            self.auto_assign()
        else:
            self._render()

    def auto_assign(self) -> None:
        xi = lineup.best_xi(self.squad, self.formation.currentText())
        self.active_ids = [p.id for p in xi]
        self._persist()
        self._render()

    def _persist(self) -> None:
        gamedata.set_meta(self.ctx.game, "active_ids", self.active_ids)

    def _formation_changed(self, name: str) -> None:
        if not self.ctx.in_game:
            return
        gamedata.set_meta(self.ctx.game, "formation", name)
        self.auto_assign()

    def _strategy_changed(self, name: str) -> None:
        if self.ctx.in_game:
            gamedata.set_meta(self.ctx.game, "strategy", name)

    def toggle(self, player_id: int) -> None:
        if player_id in self.active_ids:
            self.active_ids.remove(player_id)
        elif len(self.active_ids) < 11:
            self.active_ids.append(player_id)
        else:
            self.count_label.setText("Active players: 11 / 11. Move someone to reserve first.")
            return
        self._persist()
        self._render()

    # ---- drawing ----
    def _render(self) -> None:
        active = set(self.active_ids)
        n_active = len(active)
        self.count_label.setText(f"Active players: {n_active} / 11")
        self._fill_pills(n_active, len(self.squad) - n_active)
        t = self.table
        t.setSortingEnabled(False)
        t.setRowCount(len(self.squad))
        for r, p in enumerate(self.squad):
            t.setItem(r, 0, SortItem(p.position))
            t.setItem(r, 1, SortItem(p.name))
            t.setItem(r, 2, SortItem(str(p.age), p.age, True))
            ovr = SortItem(str(p.overall), p.overall, True)
            t.setItem(r, 3, ovr)
            t.setItem(r, 4, SortItem(str(p.potential), p.potential, True))
            t.setItem(r, 5, SortItem(fmt_money(p.value), p.value, True))
            is_active = p.id in active
            t.setItem(r, 6, SortItem("Active" if is_active else "Reserve", 0 if is_active else 1))
            b = QPushButton("Active" if is_active else "Reserve")
            b.setObjectName("pillActive" if is_active else "pillReserve")
            b.setProperty("player_id", p.id)
            b.clicked.connect(lambda _=False, pid=p.id: self.toggle(pid))
            t.setCellWidget(r, 6, b)
        t.setSortingEnabled(True)
        if t.horizontalHeader().sortIndicatorSection() != 3 and not getattr(self, '_sorted', False):
            t.sortByColumn(3, Qt.DescendingOrder)
            self._sorted = True
        by_id = {p.id: p for p in self.squad}
        xi = [by_id[i] for i in self.active_ids if i in by_id]
        self.pitch.set_lineup(lineup.assign(xi, self.formation.currentText()))

    def _fill_pills(self, active: int, reserve: int) -> None:
        while self.pills.count():
            w = self.pills.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        retiring = sum(1 for p in self.squad if p.age >= RETIRING_AGE)
        for name, label in [("pillActive", f"Active {active}"), ("pillReserve", f"Reserve {reserve}"),
                            ("pillInjured", "Injured 0"), ("pillSuspended", "Suspended 0"),
                            ("pillRetiring", f"Retiring {retiring}")]:
            l = QLabel(label)
            l.setObjectName(name)
            self.pills.addWidget(l)
        self.pills.addStretch(1)
