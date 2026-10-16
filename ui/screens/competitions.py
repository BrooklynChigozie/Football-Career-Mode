from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.components.panel import Panel, page_header
from ui.components.table import SortItem, make_table
from ui.context import GameContext


class CompetitionsScreen(QWidget):
    """Leagues, the Champions League group stage and knockout ties, and the domestic cups."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Competitions", "Standings, groups and knockout brackets."))
        p = Panel()
        row = QHBoxLayout()
        self.combo = QComboBox()
        row.addWidget(QLabel("Competition"))
        row.addWidget(self.combo)
        row.addStretch(1)
        p.body.addLayout(row)
        self.table = make_table(["#", "CLUB", "P", "W", "D", "L", "GF", "GA", "GD", "PTS"], sortable=False, stretch_col=1)
        p.body.addWidget(self.table, 1)
        self.ties = make_table(["STAGE", "HOME", "SCORE", "AWAY", "NOTE"], sortable=False, stretch_col=1)
        p.body.addWidget(self.ties, 1)
        lay.addWidget(p, 1)
        self.combo.currentIndexChanged.connect(self._fill)

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        self.combo.blockSignals(True)
        self.combo.clear()
        mine = self.ctx.engine.league_of(self.ctx.session.club_id)
        for r in self.ctx.game.execute("SELECT id, name, kind, league_id FROM competitions ORDER BY id"):
            self.combo.addItem(r["name"], (r["id"], r["kind"]))
        # open on the user's own league first
        for i in range(self.combo.count()):
            cid, kind = self.combo.itemData(i)
            if kind == "league" and self.ctx.engine._comps[cid]["league_id"] == mine:
                self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)
        self._fill()

    def _fill(self) -> None:
        data = self.combo.currentData()
        if not data:
            return
        cid, kind = data
        eng = self.ctx.engine
        rows = eng.get_table(cid) if kind in ("league", "champions_league") else []
        self.table.setVisible(bool(rows) or kind != "cup")
        self.table.setRowCount(len(rows))
        pos, last = 0, None
        for r, t in enumerate(rows):
            if t.group != last:
                pos, last = 0, t.group
            pos += 1
            name = f"{t.club_name}" + (f"   [{t.group}]" if t.group and pos == 1 else "")
            for c, v in enumerate([pos, name, t.played, t.won, t.drawn, t.lost, t.goals_for, t.goals_against,
                                   t.goal_difference, t.points]):
                it = SortItem(str(v))
                self.table.setItem(r, c, it)
        ties = []
        for stage, fxs in eng.cup_rounds(cid):
            for f in fxs:
                score = f"{f.home_goals} - {f.away_goals}" if f.played else "v"
                note = ""
                if f.played and f.pens_home is not None:
                    note = f"pens {f.pens_home}-{f.pens_away}"
                elif f.played and f.extra_time:
                    note = "after extra time"
                if f.leg:
                    note = (f"leg {f.leg}  " + note).strip() if kind == "champions_league" else note
                ties.append((stage, self.ctx.club_name_of(f.home_id), score, self.ctx.club_name_of(f.away_id), note))
        self.ties.setVisible(bool(ties))
        self.ties.setRowCount(len(ties))
        for r, row in enumerate(ties):
            for c, v in enumerate(row):
                self.ties.setItem(r, c, SortItem(v))
