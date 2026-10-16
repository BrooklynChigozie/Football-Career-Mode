from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.components.panel import Panel, page_header
from ui.components.table import SortItem, make_table
from ui.context import GameContext


class CalendarScreen(QWidget):
    """Your fixtures across every competition, with results."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Calendar", "Every match for your club this season."))
        p = Panel()
        self.table = make_table(["MD", "COMPETITION", "HOME", "", "AWAY", "RESULT"], sortable=False, stretch_col=2)
        p.body.addWidget(self.table)
        lay.addWidget(p, 1)

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        eng, uc = self.ctx.engine, self.ctx.session.club_id
        fx = eng.get_fixtures(uc)
        self.table.setRowCount(len(fx))
        for r, f in enumerate(fx):
            if f.played:
                res = f"{f.home_goals} - {f.away_goals}"
                if f.pens_home is not None:
                    res += f" (p {f.pens_home}-{f.pens_away})"
                elif f.extra_time:
                    res += " (aet)"
                won = (f.home_goals > f.away_goals) == (f.home_id == uc)
                res += "  W" if f.home_goals != f.away_goals and won else "  L" if f.home_goals != f.away_goals else "  D"
            else:
                res = "Upcoming"
            comp = f"{eng.comp_name(f.competition_id)} · {f.stage}"
            for c, text in enumerate([str(f.matchday), comp, self.ctx.club_name_of(f.home_id), "vs",
                                      self.ctx.club_name_of(f.away_id), res]):
                self.table.setItem(r, c, SortItem(text))
