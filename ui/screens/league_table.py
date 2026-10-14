"""League tables plus top scorers and assists."""
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout

from ui.components.data_table import DataTable
from ui.screens.base_screen import BaseScreen


class LeagueTableScreen(BaseScreen):
    title = "League Table"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("League:"))
        self.combo = QComboBox()
        top.addWidget(self.combo)
        top.addStretch(1)
        layout.addLayout(top)
        self.table = DataTable(["#", "Club", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"])
        layout.addWidget(self.table, 3)
        bottom = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(QLabel("Top scorers"))
        self.scorers = DataTable(["#", "Player", "Club", "Goals", "Apps"])
        left.addWidget(self.scorers)
        right.addWidget(QLabel("Top assists"))
        self.assists = DataTable(["#", "Player", "Club", "Assists", "Goals"])
        right.addWidget(self.assists)
        bottom.addLayout(left)
        bottom.addLayout(right)
        layout.addLayout(bottom, 2)
        self._keys = []
        self.combo.currentIndexChanged.connect(lambda _: self._fill())
        self.refresh()

    def refresh(self):
        keys = [k for k, (_, kind) in self.world.get_competitions().items() if kind == "league"]
        if keys != self._keys:      # first time (or a new world): rebuild the list, select the user's league
            self._keys = keys
            self.combo.blockSignals(True)
            self.combo.clear()
            for k in keys:
                self.combo.addItem(self.world.get_competitions()[k][0], k)
            self.combo.setCurrentIndex(max(0, keys.index(f"league:{self.world.user_club.league}")
                                           if f"league:{self.world.user_club.league}" in keys else 0))
            self.combo.blockSignals(False)
        self._fill()

    def _fill(self):
        key = self.combo.currentData()
        if key is None:
            return
        w = self.world
        league = w.get_competitions()[key][0]
        rows = w.get_table(key)
        self.table.set_rows(
            [[r["pos"], r["club"], r["played"], r["won"], r["drawn"], r["lost"], r["gf"], r["ga"], r["gd"],
              r["points"]] for r in rows],
            highlight={i for i, r in enumerate(rows) if r["club_id"] == w.user_club_id})
        self.scorers.set_rows([[i, p["name"], p["club"], p["goals"], p["apps"]]
                               for i, p in enumerate(w.get_top_scorers(league, 10), 1)])
        self.assists.set_rows([[i, p["name"], p["club"], p["assists"], p["goals"]]
                               for i, p in enumerate(w.get_top_assists(league, 10), 1)])