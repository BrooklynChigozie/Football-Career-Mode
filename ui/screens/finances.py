import pyqtgraph as pg
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from services import finance
from ui.components.panel import Panel, fmt_money, page_header
from ui.components.stat_card import StatCard
from ui.context import GameContext

pg.setConfigOptions(antialias=True)


class FinancesScreen(QWidget):
    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Finances & sponsors"))

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.cards = {k: StatCard(t, "-") for k, t in [
            ("balance", "Balance"), ("budget", "Transfer budget"), ("income", "Income (season)"),
            ("expenses", "Expenses (season)"), ("net", "Net")]}
        for c in self.cards.values():
            cards.addWidget(c)
        lay.addLayout(cards)

        row = QHBoxLayout()
        row.setSpacing(14)
        chart_panel = Panel("Income and expenses")
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#101b30")
        self.plot.setMinimumHeight(260)
        self.plot.showGrid(y=True, alpha=0.15)
        for ax in ("left", "bottom"):
            self.plot.getAxis(ax).setPen("#2a3d63")
            self.plot.getAxis(ax).setTextPen("#8fa3c7")
        self.plot.setMouseEnabled(False, False)
        self.plot.hideButtons()
        chart_panel.body.addWidget(self.plot)
        row.addWidget(chart_panel, 3)

        spons = Panel("Sponsors")
        self.active_box = QVBoxLayout()
        self.offers_box = QVBoxLayout()
        spons.body.addLayout(self.active_box)
        t = QLabel("Offers")
        t.setObjectName("sectionTitle")
        spons.body.addWidget(t)
        spons.body.addLayout(self.offers_box)
        self.msg = QLabel("")
        self.msg.setObjectName("error")
        self.msg.setWordWrap(True)
        spons.body.addWidget(self.msg)
        spons.body.addStretch(1)
        row.addWidget(spons, 2)
        lay.addLayout(row, 1)

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        s = self.ctx.finance_summary()
        c = self.cards
        c["balance"].set_value(fmt_money(s.balance))
        c["budget"].set_value(fmt_money(s.transfer_budget))
        c["income"].set_value(fmt_money(s.income))
        c["expenses"].set_value(fmt_money(s.expenses), f"Wages {fmt_money(s.wage_bill)}")
        net = s.income - s.expenses
        c["net"].set_value(fmt_money(net), "Profit" if net >= 0 else "Loss")
        self._chart(s)
        self._sponsors()

    def _chart(self, s) -> None:
        self.plot.clear()
        labels = [("Matchday", s.income_breakdown.get("matchday", 0), "inc"), ("TV", s.income_breakdown.get("tv", 0), "inc"),
                  ("Sponsors", s.income_breakdown.get("sponsors", 0), "inc"),
                  ("Wages", s.expense_breakdown.get("wages", 0), "exp"), ("Stadium", s.expense_breakdown.get("stadium", 0), "exp")]
        for i, (_, v, kind) in enumerate(labels):
            self.plot.addItem(pg.BarGraphItem(x=[i], height=[v / 1e6], width=0.6,
                                              brush="#3ddc84" if kind == "inc" else "#ff7a7a", pen=None))
        self.plot.getAxis("bottom").setTicks([[(i, l) for i, (l, _, _) in enumerate(labels)]])
        self.plot.setLabel("left", "Millions per season", color="#8fa3c7")

    def _sponsors(self) -> None:
        for box in (self.active_box, self.offers_box):
            while box.count():
                w = box.takeAt(0).widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
        g, cid, season = self.ctx.game, self.ctx.session.club_id, self.ctx.season
        active = finance.active_sponsorships(g, cid, season)
        head = QLabel(f"Active ({len(active)}/{finance.MAX_ACTIVE_SPONSORS})")
        head.setObjectName("sectionTitle")
        self.active_box.addWidget(head)
        if not active:
            m = QLabel("No sponsors yet. Accept an offer below.")
            m.setObjectName("muted")
            self.active_box.addWidget(m)
        for sp in active:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(f"<b>{sp.sponsor}</b> · {fmt_money(sp.annual_value)}/yr until season {sp.end_season}<br>"
                         f"<span style='color:#8fa3c7'>Bonus: {sp.bonus_condition} (+{fmt_money(sp.bonus_amount)})</span>")
            btn = QPushButton("End")
            btn.setObjectName("danger")
            btn.clicked.connect(lambda _=False, i=sp.id: self._end(i))
            h.addWidget(lbl, 1)
            h.addWidget(btn)
            self.active_box.addWidget(row)
        for offer in finance.offers(g, cid, season):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(f"<b>{offer['tier']}</b> · {offer['sponsor']}: {fmt_money(offer['annual_value'])}/yr for "
                         f"{offer['years']} yr<br><span style='color:#8fa3c7'>Bonus: {offer['bonus_condition']} "
                         f"(+{fmt_money(offer['bonus_amount'])})</span>")
            btn = QPushButton("Accept")
            btn.setObjectName("primary")
            btn.clicked.connect(lambda _=False, o=offer: self._accept(o))
            h.addWidget(lbl, 1)
            h.addWidget(btn)
            self.offers_box.addWidget(row)

    def _accept(self, offer) -> None:
        try:
            finance.accept_offer(self.ctx.game, self.ctx.session.club_id, self.ctx.season, offer)
            self.msg.setText("")
        except finance.SponsorError as e:
            self.msg.setText(str(e))
        self.refresh()
        self.ctx.changed.emit()

    def _end(self, sponsorship_id: int) -> None:
        finance.end_sponsorship(self.ctx.game, sponsorship_id)
        self.msg.setText("")
        self.refresh()
        self.ctx.changed.emit()
