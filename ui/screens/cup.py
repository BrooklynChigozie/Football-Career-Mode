"""Domestic cup: results by round and who is still alive."""
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout

from ui.components.data_table import DataTable
from ui.components.format import result_note, score_text
from ui.screens.base_screen import BaseScreen


class CupScreen(BaseScreen):
    title = "Cup"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Cup:"))
        self.combo = QComboBox()
        top.addWidget(self.combo)
        top.addStretch(1)
        layout.addLayout(top)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.table = DataTable(["Round", "Home", "Score", "Away", "Note"])
        layout.addWidget(self.table, 1)
        self.alive = QLabel()
        self.alive.setWordWrap(True)
        layout.addWidget(self.alive)
        self._keys = []
        self.combo.currentIndexChanged.connect(lambda _: self._fill())
        self.refresh()

    def refresh(self):
        keys = [k for k, (_, kind) in self.world.get_competitions().items() if kind == "cup"]
        if keys != self._keys:
            self._keys = keys
            self.combo.blockSignals(True)
            self.combo.clear()
            for k in keys:
                self.combo.addItem(self.world.get_competitions()[k][0], k.split(":", 1)[1])
            mine = self.world.user_club.league
            idx = self.combo.findData(mine)
            self.combo.setCurrentIndex(max(idx, 0))
            self.combo.blockSignals(False)
        self._fill()

    def _fill(self):
        league = self.combo.currentData()
        if league is None:
            return
        w = self.world
        status = w.get_cup_status(league)
        names = lambda ids: ", ".join(w.clubs[i].name for i in ids)
        if status["winner"] is not None:
            self.status.setText(f"{status['name']}: winner - {w.clubs[status['winner']].name}")
        else:
            self.status.setText(f"{status['name']}: {len(status['alive'])} teams in the next round")
        self.alive.setText("Still in the draw: " + names(status["alive"]) if status["alive"] else "")
        fixtures = [f for f in w.fixtures if f.competition == status["name"]]
        fixtures.sort(key=lambda f: f.week)
        rows = [[f.round_label, w.clubs[f.home_id].name, score_text(f.result), w.clubs[f.away_id].name,
                 result_note(f.result)] for f in fixtures]
        mine = {i for i, f in enumerate(fixtures) if w.user_club_id in (f.home_id, f.away_id)}
        self.table.set_rows(rows, highlight=mine)