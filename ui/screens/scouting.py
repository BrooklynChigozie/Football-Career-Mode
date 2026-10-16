from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from engine import attributes, development
from engine.offseason import MarketError
from ui.components.charts import RadarChart
from ui.components.panel import Panel, fmt_money, page_header
from ui.components.table import SortItem, make_table
from ui.context import GameContext

POSITIONS = ["Any", "GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]
SOURCES = ["Other clubs", "Free agents", "My squad (sell)"]


class ScoutingScreen(QWidget):
    """Scouting & transfer hub: search the market, compare a target on a hexagon chart, buy or sell."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self.rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Scouting & Transfers", "Find targets, compare them against your squad, then make an offer."))
        self.window_label = QLabel("")
        self.window_label.setObjectName("accent")
        lay.addWidget(self.window_label)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = Panel()
        f = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItems(SOURCES)
        self.pos = QComboBox()
        self.pos.addItems(POSITIONS)
        self.min_ovr = QSpinBox()
        self.min_ovr.setRange(0, 95)
        self.min_ovr.setValue(65)
        self.max_age = QSpinBox()
        self.max_age.setRange(16, 45)
        self.max_age.setValue(45)
        self.max_val = QSpinBox()
        self.max_val.setRange(0, 300)
        self.max_val.setValue(300)
        self.max_val.setSuffix("M max")
        for label, w in (("Source", self.source), ("Pos", self.pos), ("Min OVR", self.min_ovr), ("Max age", self.max_age), ("", self.max_val)):
            if label:
                l = QLabel(label)
                l.setObjectName("muted")
                f.addWidget(l)
            f.addWidget(w)
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primary")
        self.search_btn.clicked.connect(self._search)
        f.addWidget(self.search_btn)
        f.addStretch(1)
        left.body.addLayout(f)
        self.table = make_table(["POS", "PLAYER", "CLUB", "AGE", "OVR", "POT", "VALUE", "PRICE"], stretch_col=1)
        self.table.itemSelectionChanged.connect(self._selected)
        left.body.addWidget(self.table, 1)
        body.addWidget(left, 6)

        right = Panel("Player report")
        self.name = QLabel("Select a player")
        self.name.setObjectName("sectionTitle")
        self.info = QLabel("")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        self.radar = RadarChart()
        self.legend = QLabel("")
        self.legend.setWordWrap(True)
        self.act_btn = QPushButton("")
        self.act_btn.setObjectName("primary")
        self.act_btn.setEnabled(False)
        self.act_btn.clicked.connect(self._act)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        for w in (self.name, self.info, self.radar, self.legend, self.act_btn, self.msg):
            right.body.addWidget(w)
        body.addWidget(right, 4)
        lay.addLayout(body, 1)

    @property
    def eng(self):
        return self.ctx.engine

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        club = self.ctx.club()
        open_ = self.eng.window_open()
        self.window_label.setText(
            f"Transfer window {'OPEN' if open_ else 'CLOSED'} · budget {fmt_money(club.transfer_budget)} "
            f"· wage budget {fmt_money(club.wage_budget)}  (windows: early season and matchdays 19-22)")
        if not getattr(self, "_budget_set", False):
            self.max_val.setValue(max(5, min(300, int(club.transfer_budget / 1e6) + 5)))
            self._budget_set = True
        self._search()

    def _search(self) -> None:
        src = self.source.currentIndex()
        pos = None if self.pos.currentText() == "Any" else self.pos.currentText()
        if src == 2:
            players = [p for p in self.eng.get_squad(self.ctx.session.club_id) if not pos or p.position == pos]
        else:
            players = self.eng.market_search(pos, self.max_age.value(), self.min_ovr.value(),
                                             self.max_val.value() * 1e6, free_agents=src == 1, limit=80)
        self.rows = players
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(players))
        for r, p in enumerate(players):
            club = self.ctx.club_name_of(p.club_id) if p.club_id else "Free agent"
            price = self.eng.asking_price(p) if src != 2 else round(p.value * 0.9, -3)
            vals = [(p.position, p.position), (p.name, p.name), (club, club), (str(p.age), p.age), (str(p.overall), p.overall),
                    (str(p.potential), p.potential), (fmt_money(p.value), p.value), (fmt_money(price) if price else "Free", price)]
            for c, (txt, key) in enumerate(vals):
                self.table.setItem(r, c, SortItem(txt, key))
        self.table.setSortingEnabled(True)
        self.act_btn.setEnabled(False)
        self.name.setText("Select a player")
        self.info.setText("")
        self.legend.setText("")
        self.radar.set_data([], [])

    def _current(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        name = self.table.item(rows[0].row(), 1).text()
        age = int(self.table.item(rows[0].row(), 3).text())
        return next((p for p in self.rows if p.name == name and p.age == age), None)

    def _selected(self) -> None:
        p = self._current()
        if p is None:
            return
        labels = attributes.labels_for(p.position)
        vals = [getattr(p, a) for a in attributes.ATTRS]
        mine = [q for q in self.eng.get_squad(self.ctx.session.club_id) if q.position == p.position and q.id != p.id]
        series = [(p.name, vals, "#3ddc84")]
        legend = f'<span style="color:#3ddc84">■ {p.name}</span>'
        if mine:
            best = max(mine, key=lambda q: q.overall)
            series.append((best.name, [getattr(best, a) for a in attributes.ATTRS], "#4fb4e8"))
            legend += f'  <span style="color:#4fb4e8">■ your {best.position}: {best.name} ({best.overall})</span>'
        self.radar.set_data(labels, series)
        self.legend.setText(legend)
        self.name.setText(f"{p.name}  ·  {p.position}  ·  {p.overall} OVR")
        wage = development.wage_for(p.value, p.overall)
        self.info.setText(f"Age {p.age} · potential {p.potential} · value {fmt_money(p.value)} · wage ~{fmt_money(wage)}/yr · "
                          f"{p.nationality or 'n/a'}" + (f" · injured {p.injured_weeks}w" if p.injured_weeks else ""))
        sell = self.source.currentIndex() == 2
        price = round(p.value * 0.9, -3) if sell else self.eng.asking_price(p)
        self.act_btn.setText(f"Sell for {fmt_money(price)}" if sell else f"Sign for {fmt_money(price)}" if price else "Sign free agent")
        self.act_btn.setEnabled(True)
        self.msg.setText("")

    def _act(self) -> None:
        p = self._current()
        if p is None:
            return
        try:
            if self.source.currentIndex() == 2:
                out = self.eng.sell_player(p.id)
                self.msg.setText(f"Sold to {out['club']} for {fmt_money(out['fee'])}.")
            else:
                out = self.eng.buy_player(p.id)
                self.msg.setText(f"Signed {p.name}. Wage {fmt_money(out['wage'])}/yr.")
        except MarketError as e:
            self.msg.setText(str(e))
            return
        self.ctx.changed.emit()
        self.refresh()
