"""Match Day: play your next match, advance time, read the match report."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QVBoxLayout)

from ui.components.format import event_lines, result_note, score_text
from ui.screens.base_screen import BaseScreen


class MatchDayScreen(BaseScreen):
    title = "Match Day"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.next_label = QLabel()
        layout.addWidget(self.status)
        layout.addWidget(self.next_label)

        row = QHBoxLayout()
        self.btn_match = QPushButton("Play next match")
        self.btn_week = QPushButton("Advance one week")
        self.btn_season = QPushButton("Sim to end of season")
        self.btn_new = QPushButton("Start next season")
        for b in (self.btn_match, self.btn_week, self.btn_season, self.btn_new):
            row.addWidget(b)
        layout.addLayout(row)
        self.btn_match.clicked.connect(self.play_next_match)
        self.btn_week.clicked.connect(self.advance_week)
        self.btn_season.clicked.connect(self.sim_season)
        self.btn_new.clicked.connect(self.start_next_season)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)       # endless "busy" bar
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.score = QLabel("")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.score.setFont(font)
        layout.addWidget(self.score)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setFont(QFont("Consolas", 10))
        layout.addWidget(self.report, 1)
        self.refresh()

    # ------------------------------------------------------------------ state
    def _busy(self, flag):
        self.progress.setVisible(flag)
        for b in (self.btn_match, self.btn_week, self.btn_season, self.btn_new):
            b.setEnabled(not flag)
        if not flag:
            self.refresh()

    def refresh(self):
        w = self.world
        s = w.get_user_summary()
        self.status.setText(
            f"{s['club']}  |  Season {s['season']}  |  Week {s['week']}/{w.total_weeks}  |  "
            f"League position: {s['league_position']}  |  Budget: {s['budget']:.1f}m")
        in_season = w.phase == "season"
        self.btn_match.setEnabled(in_season)
        self.btn_week.setEnabled(in_season)
        self.btn_season.setEnabled(in_season)
        self.btn_new.setEnabled(w.phase == "offseason")
        if w.phase == "offseason":
            self.next_label.setText("Season complete. Manage your squad and transfers, then start the next season.")
        elif w.phase == "finished":
            self.next_label.setText("Your career is complete. See the Season Review and News screens.")
        else:
            upcoming = [f for f in w.get_fixtures() if f.result is None]
            if upcoming:
                f = upcoming[0]
                home = f.home_id == w.user_club_id
                opp = w.clubs[f.away_id if home else f.home_id].name
                self.next_label.setText(f"Next league match: {opp} ({'home' if home else 'away'}), week {f.week}")
            else:
                self.next_label.setText("No more league matches. Cup and European ties may remain.")

    # ------------------------------------------------------------------ actions
    def play_next_match(self):
        self.run_task(self.world.advance_to_next_user_match, self._after_match, busy=self._busy)

    def advance_week(self):
        uid = self.world.user_club_id

        def after(fixtures):
            mine = [f for f in fixtures if uid in (f.home_id, f.away_id)]
            if mine:
                self._after_match(mine[0])
            else:
                self.score.setText("")
                self.report.setPlainText("Your club did not play this week.")
                self.changed.emit()
        self.run_task(self.world.advance_day, after, busy=self._busy)

    def sim_season(self):
        reply = QMessageBox.question(self, "Simulate", "Simulate all remaining matches of this season?")
        if reply == QMessageBox.StandardButton.Yes:
            self.run_task(self.world.advance_season, lambda _: self.changed.emit(), busy=self._busy)

    def start_next_season(self):
        try:
            self.world.start_next_season()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Season", str(exc))
            return
        self.score.setText("")
        self.report.clear()
        self.changed.emit()
        self.refresh()

    def _after_match(self, fixture):
        if fixture is not None:
            self.show_fixture(fixture)
        self.changed.emit()

    def show_fixture(self, f):
        w = self.world
        home, away = w.clubs[f.home_id].name, w.clubs[f.away_id].name
        note = result_note(f.result)
        self.score.setText(f"{home}  {score_text(f.result)}  {away}" + (f"   ({note})" if note else ""))
        lines = [f"{f.competition} - {f.round_label}", ""] + event_lines(w, f.result)
        if len(lines) == 2:
            lines.append("No incidents.")
        self.report.setPlainText("\n".join(lines))