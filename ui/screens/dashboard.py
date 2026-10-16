from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QListWidget, QMessageBox, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from ui.components.panel import Panel, fmt_money, page_header
from ui.components.stat_card import StatCard
from ui.context import MAX_SEASONS, GameContext
from ui.workers import AdvanceWorker


class DashboardScreen(QWidget):
    play_requested = Signal()

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self._worker: AdvanceWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        self.header_box = QVBoxLayout()
        lay.addLayout(self.header_box)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = {k: StatCard(t, "-") for k, t in [
            ("club", "Club"), ("season", "Season"), ("date", "Date"), ("balance", "Balance"),
            ("budget", "Transfer budget"), ("wages", "Wage bill (per year)"), ("squad", "Squad size"),
            ("ovr", "Average overall"), ("next", "Next fixture")]}
        for i, c in enumerate(self.cards.values()):
            grid.addWidget(c, i // 3, i % 3)
        lay.addLayout(grid)

        actions = Panel("Season control")
        row = QHBoxLayout()
        self.play_btn = QPushButton("Play match day")
        self.play_btn.setObjectName("primary")
        self.play_btn.clicked.connect(self.play_requested.emit)
        self.advance_btn = QPushButton("Quick-sim matchday")
        self.advance_btn.clicked.connect(lambda: self._run("day"))
        self.season_btn = QPushButton("Sim to season end")
        self.season_btn.clicked.connect(lambda: self._run("season"))
        self.state_label = QLabel("")
        self.state_label.setObjectName("accent")
        row.addWidget(self.play_btn)
        row.addWidget(self.advance_btn)
        row.addWidget(self.season_btn)
        row.addStretch(1)
        row.addWidget(self.state_label)
        actions.body.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)           # indeterminate while the engine runs
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        actions.body.addWidget(self.progress)
        actions.body.addWidget(self.status)
        lay.addWidget(actions)
        news = Panel("News")
        self.news = QListWidget()
        self.news.setMinimumHeight(140)
        news.body.addWidget(self.news)
        lay.addWidget(news, 1)
        self._header = None

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        if self._header is not None:
            self._header.setParent(None)
            self._header.deleteLater()
        self._header = page_header("Dashboard", f"{self.ctx.session.club_name} · {self.ctx.league_name()}")
        self.header_box.addWidget(self._header)
        club, summary, squad = self.ctx.club(), self.ctx.finance_summary(), self.ctx.squad()
        c = self.cards
        c["club"].set_value(club.name, self.ctx.league_name())
        c["season"].set_value(f"{min(self.ctx.season, MAX_SEASONS)} / {MAX_SEASONS}",
                              "Career complete" if self.ctx.career_over else f"Matchday {self.ctx.matchday}")
        c["date"].set_value(self.ctx.date_str)
        c["balance"].set_value(fmt_money(club.balance))
        c["budget"].set_value(fmt_money(club.transfer_budget))
        c["wages"].set_value(fmt_money(summary.wage_bill), f"{summary.wage_bill / max(1, summary.income):.0%} of income")
        c["squad"].set_value(str(len(squad)))
        c["ovr"].set_value(f"{sum(p.overall for p in squad) / max(1, len(squad)):.1f}")
        f = self.ctx.next_fixture()
        if f:
            home = f.home_id == self.ctx.session.club_id
            opp = self.ctx.club_name_of(f.away_id if home else f.home_id)
            c["next"].set_value(opp, f"{'Home' if home else 'Away'} · {self.ctx.engine.comp_name(f.competition_id)} · {f.stage}")
        else:
            c["next"].set_value("-", "No fixtures yet")
        eng = self.ctx.engine
        self.state_label.setText(f"State: {eng.state().label}")
        self.news.clear()
        for r in self.ctx.game.execute("SELECT text FROM news ORDER BY id DESC LIMIT 25"):
            self.news.addItem(r["text"])
        self.play_btn.setEnabled(bool(eng.pending_user_fixtures()) and not self.ctx.career_over)
        end = eng.state().value == "season_end"
        self.season_btn.setText("Start next season" if end else "Sim to season end")
        busy = self._worker is not None and self._worker.isRunning()
        self.advance_btn.setEnabled(not busy and not self.ctx.career_over and not end)
        self.season_btn.setEnabled(not busy and not self.ctx.career_over)

    def _run(self, kind: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.progress.setVisible(True)
        self.status.setText("Simulating...")
        self.advance_btn.setEnabled(False)
        self.season_btn.setEnabled(False)
        self._kind = kind
        self._worker = AdvanceWorker(kind, self)
        self._worker.done.connect(self._finished)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _finished(self) -> None:
        self._worker.wait()
        self.progress.setVisible(False)
        if self._kind == "season":
            self.ctx.after_season_advanced()
            self.status.setText("Season complete." if not self.ctx.career_over else "Your 7-season career is complete.")
            self._season_summary()
        else:
            self.ctx.after_day_advanced()
            self.status.setText("Matchday played.")
        self.refresh()

    def _failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.status.setText(f"Engine error: {msg}")
        self.refresh()

    def _season_summary(self) -> None:
        eng = self.ctx.engine
        season = min(self.ctx.season, 7) - (0 if self.ctx.career_over else 1)
        h = eng.history(season)
        if not h:
            return
        lg = str(eng._clubs[self.ctx.session.club_id]["league_id"])
        text = (f"Season {season} complete.\n\nYour league position: {h.get('user_position', '?')}\n"
                f"League champions: {eng.club_name(h['champions'][lg])}\n"
                f"Champions League winners: {eng.club_name(h['cl_winner']) if h.get('cl_winner') else '-'}\n"
                f"Top scorer: {h['top_scorer'][0] + ' (' + str(h['top_scorer'][1]) + ')' if h.get('top_scorer') else '-'}")
        if self.ctx.career_over:
            text += "\n\nYour 7-season career is over. Thanks for playing!"
        QMessageBox.information(self, "Season summary", text)
