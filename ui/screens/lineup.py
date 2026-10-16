"""Formation and starting XI picker."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from engine.match_sim import team_strength
from engine.models import FORMATIONS
from ui.screens.base_screen import BaseScreen

HEADERS = ["Start", "Pos", "Name", "Age", "Ovr", "Fitness", "Morale", "Status"]


class LineupScreen(BaseScreen):
    title = "Lineup"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Formation:"))
        self.formation = QComboBox()
        self.formation.addItems(list(FORMATIONS))
        self.formation.currentTextChanged.connect(self._formation_changed)
        top.addWidget(self.formation)
        self.btn_auto = QPushButton("Auto pick XI")
        self.btn_save = QPushButton("Save my XI")
        self.btn_auto.clicked.connect(self.auto_pick)
        self.btn_save.clicked.connect(self.save_xi)
        top.addWidget(self.btn_auto)
        top.addWidget(self.btn_save)
        top.addStretch(1)
        layout.addLayout(top)
        self.info = QLabel()
        layout.addWidget(self.info)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(lambda _: self._update_info())
        layout.addWidget(self.table, 1)
        self._ids = []
        self.refresh()

    def refresh(self):
        w = self.world
        self.formation.blockSignals(True)
        self.formation.setCurrentText(w.user_club.formation)
        self.formation.blockSignals(False)
        starting = {p.id for p in w.get_lineup()}
        squad = w.get_squad()
        self._ids = [p.id for p in squad]
        self.table.blockSignals(True)
        self.table.setRowCount(len(squad))
        for r, p in enumerate(squad):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Checked if p.id in starting else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, check)
            status = "Injured" if p.injured_days else ("Suspended" if p.suspended_matches else "Fit")
            for c, text in enumerate([p.position, p.name, p.age, p.overall, f"{p.fitness:.0f}%",
                                      f"{p.morale:.0f}", status], 1):
                item = QTableWidgetItem(str(text))
                if not p.available:
                    item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(r, c, item)
        self.table.blockSignals(False)
        self._update_info()

    def _checked_ids(self):
        return [self._ids[r] for r in range(self.table.rowCount())
                if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _update_info(self):
        ids = self._checked_ids()
        players = [self.world.players[i] for i in ids]
        text = f"Selected {len(ids)}/11"
        if len(players) == 11:
            s = team_strength(players)
            text += f"   |   Attack {s['attack']:.0f}  Midfield {s['mid']:.0f}  Defence {s['defence']:.0f}"
        if self.world.user_club.custom_lineup:
            text += "   |   custom XI active"
        self.info.setText(text)

    def _formation_changed(self, name):
        if name:
            self.world.set_formation(name)   # also returns to automatic selection
            self.refresh()
            self.changed.emit()

    def auto_pick(self):
        self.world.set_lineup(None)
        self.refresh()
        self.changed.emit()

    def save_xi(self):
        ok, msg = self.world.set_lineup(self._checked_ids())
        QMessageBox.information(self, "Lineup", msg) if ok else QMessageBox.warning(self, "Lineup", msg)
        self._update_info()
        self.changed.emit()