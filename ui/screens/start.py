from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from services import gamedata
from ui.components.panel import Panel, fmt_money, page_header
from ui.components.table import SortItem, make_table
from ui.context import SLOTS, GameContext


class StartScreen(QWidget):
    """After login: load or delete a save, or start a new career by picking a slot and a club."""

    entered = Signal()
    logout_requested = Signal()

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self._target_slot: int | None = None
        self._confirm_delete: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        top = QHBoxLayout()
        hdr = page_header("Your careers", "Load a save or start a new career.")
        hdr.setMinimumHeight(60)
        top.addWidget(hdr)
        top.addStretch(1)
        self.user_label = QLabel("")
        self.user_label.setObjectName("muted")
        out = QPushButton("Log out")
        out.clicked.connect(self.logout_requested)
        top.addWidget(self.user_label)
        top.addWidget(out)
        root.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(14)
        self.slots_panel = Panel("Save slots")
        self.slots_panel.setFixedWidth(360)
        self.slots_box = QVBoxLayout()
        self.slots_panel.body.addLayout(self.slots_box)
        self.slots_panel.body.addStretch(1)
        row.addWidget(self.slots_panel)

        self.club_panel = Panel("New career: pick a club")
        filt = QHBoxLayout()
        self.league_combo = QComboBox()
        self.league_combo.setMinimumWidth(200)
        self.league_combo.currentIndexChanged.connect(self._fill_clubs)
        filt.addWidget(QLabel("League"))
        filt.addWidget(self.league_combo)
        filt.addStretch(1)
        self.club_panel.body.addLayout(filt)
        self.table = make_table(["CLUB", "LEAGUE", "RATING", "STADIUM", "BUDGET"], stretch_col=0)
        self.table.itemSelectionChanged.connect(self._update_start)
        self.club_panel.body.addWidget(self.table, 1)
        bottom = QHBoxLayout()
        self.hint = QLabel("Choose an empty slot on the left, then a club.")
        self.hint.setObjectName("muted")
        self.start_btn = QPushButton("Start career")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        bottom.addWidget(self.hint, 1)
        bottom.addWidget(self.start_btn)
        self.club_panel.body.addLayout(bottom)
        row.addWidget(self.club_panel, 1)
        root.addLayout(row, 1)

        self._clubs = []

    # ---- lifecycle ----
    def refresh(self) -> None:
        self.user_label.setText(f"Signed in as {self.ctx.user.username}" if self.ctx.user else "")
        if self.league_combo.count() == 0:
            self.league_combo.blockSignals(True)
            self.league_combo.addItem("All leagues", None)
            for lg in gamedata.list_leagues(self.ctx.template):
                self.league_combo.addItem(lg["name"], lg["id"])
            self.league_combo.blockSignals(False)
        self._fill_clubs()
        self._fill_slots()

    def _fill_slots(self) -> None:
        while self.slots_box.count():
            w = self.slots_box.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        saves = {s["slot"]: s for s in self.ctx.list_saves()}
        for n in range(1, SLOTS + 1):
            self.slots_box.addWidget(self._slot_row(n, saves.get(n)))

    def _slot_row(self, n: int, save) -> QWidget:
        w = Panel()
        w.setObjectName("card")
        lay = QHBoxLayout()
        lay.setSpacing(8)
        text = QLabel()
        text.setWordWrap(True)
        lay.addWidget(text, 1)
        if save:
            text.setText(f"<b>Slot {n}</b> · {save['club_name']}<br>"
                         f"<span style='color:#8fa3c7'>Season {save['season']} · {save['last_played'][:16]}</span>")
            load = QPushButton("Load")
            load.setObjectName("primary")
            load.clicked.connect(lambda _=False, s=n: self._load(s))
            dele = QPushButton("Confirm delete" if self._confirm_delete == n else "Delete")
            dele.setObjectName("danger")
            dele.clicked.connect(lambda _=False, s=n: self._delete(s))
            lay.addWidget(load)
            lay.addWidget(dele)
        else:
            chosen = self._target_slot == n
            text.setText(f"<b>Slot {n}</b> · empty" + (" <span style='color:#3ddc84'>(selected)</span>" if chosen else ""))
            pick = QPushButton("Selected" if chosen else "New career")
            pick.clicked.connect(lambda _=False, s=n: self._pick_slot(s))
            lay.addWidget(pick)
        w.body.addLayout(lay)
        return w

    def _fill_clubs(self) -> None:
        self._clubs = gamedata.list_clubs(self.ctx.template, self.league_combo.currentData())
        leagues = {lg["id"]: lg["name"] for lg in gamedata.list_leagues(self.ctx.template)}
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._clubs))
        for r, c in enumerate(self._clubs):
            self.table.setItem(r, 0, SortItem(c.name))
            self.table.setItem(r, 1, SortItem(leagues[c.league_id]))
            self.table.setItem(r, 2, SortItem(str(c.reputation), c.reputation, True))
            self.table.setItem(r, 3, SortItem(f"{c.stadium_capacity:,}", c.stadium_capacity, True))
            self.table.setItem(r, 4, SortItem(fmt_money(c.transfer_budget), c.transfer_budget, True))
            self.table.item(r, 0).setData(0x0100, c.id)       # Qt.UserRole
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.DescendingOrder)
        self._update_start()

    # ---- actions ----
    def _pick_slot(self, n: int) -> None:
        self._target_slot = n
        self._fill_slots()
        self._update_start()

    def selected_club(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        cid = self.table.item(rows[0].row(), 0).data(0x0100)
        return next((c for c in self._clubs if c.id == cid), None)

    def _update_start(self) -> None:
        club = self.selected_club()
        ok = club is not None and self._target_slot is not None
        self.start_btn.setEnabled(ok)
        if ok:
            self.hint.setText(f"Slot {self._target_slot}: manage {club.name} for up to 7 seasons.")
        elif self._target_slot is None:
            self.hint.setText("Choose an empty slot on the left, then a club.")
        else:
            self.hint.setText(f"Slot {self._target_slot} selected. Now pick a club.")

    def _start(self) -> None:
        club = self.selected_club()
        if club is None or self._target_slot is None:
            return
        try:
            self.ctx.start_new(self._target_slot, club.id, club.name)
        except Exception as e:
            self.hint.setText(f"Could not start the career: {e}")
            return
        self._target_slot = None
        self.entered.emit()

    def _load(self, n: int) -> None:
        try:
            self.ctx.load(n)
        except Exception as e:                      # e.g. a save from an older version
            self.hint.setText(str(e))
            return
        self.entered.emit()

    def _delete(self, n: int) -> None:
        if self._confirm_delete != n:
            self._confirm_delete = n          # first click arms it, second click deletes
            self._fill_slots()
            return
        self._confirm_delete = None
        self.ctx.delete_save(n)
        self._fill_slots()
