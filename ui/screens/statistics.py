from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.components.panel import Panel, page_header
from ui.components.table import SortItem, make_table
from ui.context import GameContext


class StatisticsScreen(QWidget):
    """Top scorers / assists / cards for the season, and season history."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Statistics", "Player stats across every competition this season."))
        row = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItems(["Whole world", "My club"])
        self.scope.currentIndexChanged.connect(self._fill)
        row.addWidget(QLabel("Show"))
        row.addWidget(self.scope)
        row.addStretch(1)
        p = Panel()
        p.body.addLayout(row)
        self.table = make_table(["#", "PLAYER", "CLUB", "POS", "APPS", "GOALS", "ASSISTS", "YELLOW", "RED"], stretch_col=1)
        p.body.addWidget(self.table, 1)
        lay.addWidget(p, 1)
        h = Panel("Past seasons")
        self.history = QLabel("")
        self.history.setWordWrap(True)
        h.body.addWidget(self.history)
        lay.addWidget(h)

    def refresh(self) -> None:
        if self.ctx.in_game:
            self._fill()

    def _fill(self) -> None:
        eng = self.ctx.engine
        q = ("SELECT p.name, c.name club, p.position, ps.* FROM player_stats ps JOIN players p ON p.id=ps.player_id "
             "LEFT JOIN clubs c ON c.id=ps.club_id WHERE ps.season=?")
        args = [self.ctx.season]
        if self.scope.currentIndex() == 1:
            q += " AND ps.club_id=?"
            args.append(self.ctx.session.club_id)
        rows = self.ctx.game.execute(q + " ORDER BY ps.goals DESC, ps.assists DESC, ps.apps DESC LIMIT 50", args).fetchall()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            for c, v in enumerate([r + 1, x["name"], x["club"] or "", x["position"], x["apps"], x["goals"], x["assists"], x["yellows"], x["reds"]]):
                self.table.setItem(r, c, SortItem(str(v), v if isinstance(v, int) else str(v)))
        self.table.setSortingEnabled(True)
        lines = []
        for s in range(1, self.ctx.season):
            h = eng.history(s)
            if not h:
                continue
            lg = str(eng._clubs[self.ctx.session.club_id]["league_id"])
            champ = eng.club_name(h["champions"][lg])
            cl = eng.club_name(h["cl_winner"]) if h.get("cl_winner") else "-"
            lines.append(f"Season {s}: you finished {h.get('user_position', '?')} · league champions {champ} · "
                         f"Champions League winners {cl} · top scorer {h['top_scorer'][0] if h.get('top_scorer') else '-'}")
        self.history.setText("\n".join(lines) or "No completed seasons yet.")
