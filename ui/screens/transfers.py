"""Transfer market: search and bid, offers inbox, and your own squad's contracts."""
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from ui.components.data_table import DataTable
from ui.screens.base_screen import BaseScreen


class TransfersScreen(BaseScreen):
    title = "Transfers"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        self.header = QLabel()
        layout.addWidget(self.header)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        tabs.addTab(self._build_search(), "Search & bid")
        tabs.addTab(self._build_offers(), "Offers received")
        tabs.addTab(self._build_squad(), "My squad")
        self._results = {}
        self.refresh()

    # ------------------------------------------------------------------ search tab
    def _build_search(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        filters = QHBoxLayout()
        self.pos = QComboBox()
        self.pos.addItem("Any position", None)
        for p in ("GK", "DEF", "MID", "FWD"):
            self.pos.addItem(p, p)
        self.min_ovr = QSpinBox(); self.min_ovr.setRange(0, 99); self.min_ovr.setValue(65)
        self.max_age = QSpinBox(); self.max_age.setRange(16, 45); self.max_age.setValue(35)
        self.max_price = QDoubleSpinBox(); self.max_price.setRange(0, 500); self.max_price.setSpecialValueText("Any")
        self.fa_only = QCheckBox("Free agents only")
        btn = QPushButton("Search")
        btn.clicked.connect(self.search)
        for label, widget in (("Position", self.pos), ("Min OVR", self.min_ovr), ("Max age", self.max_age),
                              ("Max price (m)", self.max_price)):
            filters.addWidget(QLabel(label))
            filters.addWidget(widget)
        filters.addWidget(self.fa_only)
        filters.addWidget(btn)
        lay.addLayout(filters)
        self.results = DataTable(["Name", "Pos", "Age", "OVR", "POT", "Club", "Value", "Ask", "Wage ask"])
        self.results.itemSelectionChanged.connect(self._selected)
        lay.addWidget(self.results, 1)
        bid = QFormLayout()
        self.fee = QDoubleSpinBox(); self.fee.setRange(0, 1000); self.fee.setDecimals(1)
        self.wage = QDoubleSpinBox(); self.wage.setRange(0, 100); self.wage.setDecimals(2)
        self.years = QSpinBox(); self.years.setRange(1, 5); self.years.setValue(3)
        bid.addRow("Fee (m)", self.fee)
        bid.addRow("Wage per year (m)", self.wage)
        bid.addRow("Contract (years)", self.years)
        lay.addLayout(bid)
        make = QPushButton("Make offer")
        make.clicked.connect(self.make_offer)
        lay.addWidget(make)
        return page

    def search(self):
        found = self.world.search_players(
            position=self.pos.currentData(), min_overall=self.min_ovr.value(), max_age=self.max_age.value(),
            max_price=self.max_price.value() or None, free_agents_only=self.fa_only.isChecked(), limit=100)
        self._results = {d["player"].id: d for d in found}
        self.results.set_rows(
            [[d["player"].name, d["player"].position, d["player"].age, d["player"].overall, d["player"].potential,
              d["club"], d["value"], d["ask_price"], d["wage_demand"]] for d in found],
            row_ids=[d["player"].id for d in found])

    def _selected(self):
        d = self._results.get(self.results.selected_id())
        if d:
            self.fee.setValue(round(d["ask_price"] * 1.05, 1))
            self.wage.setValue(round(d["wage_demand"] * 1.05, 2))

    def make_offer(self):
        pid = self.results.selected_id()
        if pid is None:
            QMessageBox.information(self, "Transfers", "Select a player first.")
            return
        ok, msg = self.world.buy_player(pid, self.fee.value(), self.wage.value(), self.years.value())
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Transfer", msg)
        if ok:
            self.refresh()
            self.search()
            self.changed.emit()

    # ------------------------------------------------------------------ offers tab
    def _build_offers(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.offers = DataTable(["Player", "OVR", "Age", "Bidder", "Fee (m)", "Value (m)"])
        lay.addWidget(self.offers, 1)
        row = QHBoxLayout()
        accept, reject = QPushButton("Accept offer"), QPushButton("Reject offer")
        accept.clicked.connect(self.accept_offer)
        reject.clicked.connect(self.reject_offer)
        row.addWidget(accept)
        row.addWidget(reject)
        lay.addLayout(row)
        return page

    def accept_offer(self):
        oid = self.offers.selected_id()
        if oid is None:
            return
        ok, msg = self.world.accept_offer(oid)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Offer", msg)
        self.refresh()
        self.changed.emit()

    def reject_offer(self):
        oid = self.offers.selected_id()
        if oid is not None:
            self.world.reject_offer(oid)
            self.refresh()

    # ------------------------------------------------------------------ squad tab
    def _build_squad(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        self.squad = DataTable(["Name", "Pos", "Age", "OVR", "Value (m)", "Wage (m)", "Contract to", "Listed"])
        lay.addWidget(self.squad, 1)
        row = QHBoxLayout()
        for text, fn in (("List / unlist for sale", self.toggle_listing), ("Renew contract", self.renew),
                         ("Release player", self.release)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        return page

    def toggle_listing(self):
        pid = self.squad.selected_id()
        if pid is not None:
            p = self.world.players[pid]
            self.world.list_player(pid, not p.listed)
            self.refresh()

    def renew(self):
        pid = self.squad.selected_id()
        if pid is None:
            return
        from engine.transfers import estimate_wage, market_value
        p = self.world.players[pid]
        suggested = estimate_wage(market_value(p)) * 1.05
        wage, ok = QInputDialog.getDouble(self, "Renew contract", f"Yearly wage for {p.name} (m):",
                                          suggested, 0, 100, 2)
        if not ok:
            return
        years, ok = QInputDialog.getInt(self, "Renew contract", "Years:", 3, 1, 5)
        if ok:
            ok, msg = self.world.renew_contract(pid, wage, years)
            (QMessageBox.information if ok else QMessageBox.warning)(self, "Contract", msg)
            self.refresh()

    def release(self):
        pid = self.squad.selected_id()
        if pid is None:
            return
        p = self.world.players[pid]
        if QMessageBox.question(self, "Release", f"Release {p.name}? He will become a free agent.") == \
                QMessageBox.StandardButton.Yes:
            if not self.world.release_player(pid):
                QMessageBox.warning(self, "Release", "Your squad would be too small.")
            self.refresh()
            self.changed.emit()

    # ------------------------------------------------------------------ refresh
    def refresh(self):
        w = self.world
        window = "OPEN" if w.can_transfer else "closed (free agents can still be signed)"
        self.header.setText(f"Transfer window: {window}   |   Budget: "
                            f"{w.finance.available_budget(w.user_club):.1f}m")
        from engine.transfers import market_value
        offers = w.offers
        rows, ids = [], []
        for o in offers:
            p = w.players.get(o.player_id)
            if p:
                rows.append([p.name, p.overall, p.age, w.clubs[o.from_club_id].name, o.fee, market_value(p)])
                ids.append(o.id)
        self.offers.set_rows(rows, row_ids=ids)
        squad = w.get_squad()
        self.squad.set_rows(
            [[p.name, p.position, p.age, p.overall, market_value(p), p.wage, p.contract_until,
              "Yes" if p.listed else ""] for p in squad], row_ids=[p.id for p in squad])