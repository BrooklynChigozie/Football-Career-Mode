"""Champions League: group tables and knockout results."""
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from ui.components.data_table import DataTable
from ui.components.format import result_note, score_text
from ui.screens.base_screen import BaseScreen

COLS = ["#", "Club", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]


class ChampionsLeagueScreen(BaseScreen):
    title = "Champions League"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        self.status = QLabel()
        layout.addWidget(self.status)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        self.groups_widget = QWidget()
        self.grid = QGridLayout(self.groups_widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.groups_widget)
        tabs.addTab(scroll, "Group stage")

        self.knockout = DataTable(["Round", "Home", "Score", "Away", "Note"])
        tabs.addTab(self.knockout, "Knockouts")
        self._tables = {}
        self.refresh()

    def refresh(self):
        w = self.world
        comp = w.competitions.get("cl")
        if comp is None:
            self.status.setText("The Champions League is not part of this world.")
            return
        uid = w.user_club_id
        if comp.winner is not None:
            self.status.setText(f"Champions of Europe: {w.clubs[comp.winner].name}")
        elif any(uid in g for g in comp.groups):
            self.status.setText("Your club is playing in the Champions League this season.")
        else:
            self.status.setText("Your club did not qualify for the Champions League this season.")

        groups = w.get_table("cl")                       # {"A": rows, "B": rows, ...}
        if set(self._tables) != set(groups):             # build one table per group the first time
            while self.grid.count():
                self.grid.takeAt(0).widget().deleteLater()
            self._tables = {}
            for i, letter in enumerate(sorted(groups)):
                box = QGroupBox(f"Group {letter}")
                inner = QVBoxLayout(box)
                table = DataTable(COLS)
                table.setMinimumHeight(170)
                inner.addWidget(table)
                self.grid.addWidget(box, i // 2, i % 2)
                self._tables[letter] = table
        for letter, rows in groups.items():
            self._tables[letter].set_rows(
                [[r["pos"], r["club"], r["played"], r["won"], r["drawn"], r["lost"], r["gf"], r["ga"], r["gd"],
                  r["points"]] for r in rows],
                highlight={i for i, r in enumerate(rows) if r["club_id"] == uid})

        ko = [f for f in w.fixtures if f.competition == comp.name and not f.round_label.startswith("Group")]
        ko.sort(key=lambda f: f.week)
        self.knockout.set_rows(
            [[f.round_label, w.clubs[f.home_id].name, score_text(f.result), w.clubs[f.away_id].name,
              result_note(f.result)] for f in ko],
            highlight={i for i, f in enumerate(ko) if uid in (f.home_id, f.away_id)})