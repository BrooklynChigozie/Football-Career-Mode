"""News feed, big transfers and season history."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QVBoxLayout

from ui.components.data_table import DataTable
from ui.screens.base_screen import BaseScreen


class NewsScreen(BaseScreen):
    title = "News"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(QLabel("Latest news"))
        self.news = QListWidget()
        left.addWidget(self.news)
        right.addWidget(QLabel("Biggest transfers (this career)"))
        self.transfers = DataTable(["Season", "Player", "From", "To", "Fee (m)"])
        right.addWidget(self.transfers)
        row.addLayout(left, 1)
        row.addLayout(right, 1)
        layout.addLayout(row, 3)
        layout.addWidget(QLabel("Season history"))
        self.history = DataTable(["Season"])
        layout.addWidget(self.history, 2)
        self.refresh()

    def refresh(self):
        w = self.world
        self.news.clear()
        for year, week, text in w.get_news(60):
            self.news.addItem(f"[{year}, wk {week}]  {text}")

        big = sorted(w.transfers, key=lambda t: -t.fee)[:12]
        name = lambda cid: w.clubs[cid].name if cid in w.clubs else "Free agency"
        self.transfers.set_rows([[t.season, t.player_name, name(t.from_club_id), name(t.to_club_id), t.fee]
                                 for t in big])

        hist = w.get_history()
        leagues = list(hist[0]["champions"]) if hist else []
        headers = ["Season"] + leagues + ["Champions League", "Your finish"]
        self.history.setColumnCount(len(headers))
        self.history.setHorizontalHeaderLabels(headers)
        rows = []
        for s in hist:
            cl = w.clubs[s["cl_winner"]].name if s["cl_winner"] is not None else "-"
            mine = s["league_positions"].get(w.user_club_id, "-")
            rows.append([f"{s['season']}/{str(s['season'] + 1)[-2:]}"]
                        + [w.clubs[s["champions"][lg]].name for lg in leagues] + [cl, mine])
        self.history.set_rows(rows)