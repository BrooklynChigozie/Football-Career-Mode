import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from engine import tactics
from ui.components.charts import MomentumBar
from ui.components.livepitch import LivePitch
from ui.components.panel import Panel, page_header
from ui.context import GameContext
from ui.workers import AdvanceWorker

SPEEDS = {"Slow": 2600, "Normal": 1400, "Fast": 550}
STAT_ROWS = [("Possession %", "poss", "{:.0f}"), ("Pass accuracy %", "acc", "{:.0f}"), ("Shots", "shots", "{:d}"),
             ("On target", "sot", "{:d}"), ("xG", "xg", "{:.2f}"), ("Fouls", "fouls", "{:d}")]
KIND_COLOR = {"goal": "#3ddc84", "red": "#ff7a7a", "yellow": "#f2c94c", "injury": "#ff9db3", "sub": "#7fd6ff",
              "halftime": "#a68bff", "fulltime": "#a68bff", "kickoff": "#a68bff"}


class MatchDayScreen(QWidget):
    """Touchline hub: live pitch + commentary on the left, analytics HUD and managerial controls on the right."""

    finished = Signal()          # the whole matchday (all your fixtures and the rest of the league) is done

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self.live = None
        self.fixture = None
        self._worker = None
        self._done_committed = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.anim = QTimer(self)
        self.anim.setInterval(33)
        self.anim.timeout.connect(self._animate)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        self.header_box = QVBoxLayout()
        root.addLayout(self.header_box)

        # lobby (before kick-off)
        self.lobby = Panel("Match day")
        self.lobby_text = QLabel("")
        self.lobby_text.setWordWrap(True)
        self.kickoff_btn = QPushButton("Go to the touchline")
        self.kickoff_btn.setObjectName("primary")
        self.kickoff_btn.clicked.connect(self._kickoff)
        self.lobby.body.addWidget(self.lobby_text)
        self.lobby.body.addWidget(self.kickoff_btn)
        self.lobby.body.addStretch(1)
        root.addWidget(self.lobby)

        # live view
        self.live_view = QWidget()
        lv = QHBoxLayout(self.live_view)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(12)
        left = QVBoxLayout()
        self.scoreboard = QLabel("")
        self.scoreboard.setObjectName("pageTitle")
        self.scoreboard.setAlignment(Qt.AlignCenter)
        left.addWidget(self.scoreboard)
        self.pitch = LivePitch()
        left.addWidget(self.pitch, 3)
        ctl = QHBoxLayout()
        self.play_btn = QPushButton("Pause")
        self.play_btn.clicked.connect(self._toggle)
        self.speed = QComboBox()
        self.speed.addItems(list(SPEEDS))
        self.speed.setCurrentText("Normal")
        self.speed.currentTextChanged.connect(self._speed)
        self.skip_btn = QPushButton("Skip to end")
        self.skip_btn.clicked.connect(self._skip)
        self.finish_btn = QPushButton("Full-time: continue")
        self.finish_btn.setObjectName("primary")
        self.finish_btn.clicked.connect(self._finish)
        self.finish_btn.setVisible(False)
        ctl.addWidget(self.play_btn)
        ctl.addWidget(QLabel("Speed"))
        ctl.addWidget(self.speed)
        ctl.addWidget(self.skip_btn)
        ctl.addStretch(1)
        ctl.addWidget(self.finish_btn)
        left.addLayout(ctl)
        feed = Panel("Commentary")
        self.feed = QListWidget()
        self.feed.setMinimumHeight(120)
        feed.body.addWidget(self.feed)
        left.addWidget(feed, 2)
        lv.addLayout(left, 5)

        right = QVBoxLayout()
        right.setSpacing(10)
        hud = Panel("Live analytics")
        self.momentum = MomentumBar()
        hud.body.addWidget(self.momentum)
        grid = QGridLayout()
        self.stat_labels = {}
        for r, (title, key, _fmt) in enumerate(STAT_ROWS):
            h, t, a = QLabel("-"), QLabel(title), QLabel("-")
            h.setAlignment(Qt.AlignRight)
            t.setAlignment(Qt.AlignCenter)
            t.setObjectName("muted")
            h.setStyleSheet("font-weight:700;color:#7fb4ff")
            a.setStyleSheet("font-weight:700;color:#ff9a9a")
            grid.addWidget(h, r, 0)
            grid.addWidget(t, r, 1)
            grid.addWidget(a, r, 2)
            self.stat_labels[key] = (h, a)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        hud.body.addLayout(grid)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0d1729")
        self.plot.setMinimumHeight(120)
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.getAxis("left").enableAutoSIPrefix(False)
        self.plot.setLabel("left", "xG")
        self.plot.setXRange(0, 90)
        self.home_line = self.plot.plot(pen=pg.mkPen("#3d8bff", width=2))
        self.away_line = self.plot.plot(pen=pg.mkPen("#ff6b6b", width=2))
        hud.body.addWidget(self.plot)
        right.addWidget(hud, 3)

        tl = Panel("Touchline")
        mrow = QHBoxLayout()
        self.ment_btns = {}
        for m in tactics.MENTALITIES:
            b = QPushButton(m)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, v=m: self._mentality(v))
            mrow.addWidget(b)
            self.ment_btns[m] = b
        tl.body.addLayout(mrow)
        srow = QHBoxLayout()
        for name, tip in tactics.SHOUTS.items():
            b = QPushButton(name)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, n=name: self._shout(n))
            srow.addWidget(b)
        tl.body.addLayout(srow)
        subrow = QHBoxLayout()
        self.out_box, self.in_box = QComboBox(), QComboBox()
        self.sub_btn = QPushButton("Substitute")
        self.sub_btn.clicked.connect(self._sub)
        self.subs_left = QLabel("")
        self.subs_left.setObjectName("muted")
        subrow.addWidget(self.out_box, 1)
        subrow.addWidget(QLabel("→"))
        subrow.addWidget(self.in_box, 1)
        subrow.addWidget(self.sub_btn)
        tl.body.addLayout(subrow)
        tl.body.addWidget(self.subs_left)
        self.msg = QLabel("")
        self.msg.setObjectName("muted")
        self.msg.setWordWrap(True)
        tl.body.addWidget(self.msg)
        right.addWidget(tl, 2)
        lv.addLayout(right, 4)
        self.live_view.setVisible(False)
        root.addWidget(self.live_view, 1)
        self._header = None

    @property
    def eng(self):
        return self.ctx.engine

    # ---- lobby ----
    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        if self._header is not None:
            self._header.setParent(None)
        self._header = page_header("Match Day", "Manage from the touchline: shouts, mentality and substitutions.")
        self.header_box.addWidget(self._header)
        if self.live is not None:
            return
        pending = self.eng.pending_user_fixtures()
        self.live_view.setVisible(False)
        self.lobby.setVisible(True)
        if self.ctx.career_over:
            self.lobby_text.setText("Your 7-season career is complete.")
            self.kickoff_btn.setVisible(False)
        elif pending:
            f = pending[0]
            self.fixture = f
            self.lobby_text.setText(
                f"{self.eng.comp_name(f.competition_id)} · {f.stage}\n\n"
                f"{self.ctx.club_name_of(f.home_id)}  vs  {self.ctx.club_name_of(f.away_id)}\n\n"
                f"Check your Tactics and Training first, then walk to the touchline.")
            self.kickoff_btn.setText("Kick off")
            self.kickoff_btn.setVisible(True)
        else:
            self.lobby_text.setText("No fixture for your club in the next round.\nAdvance the matchday from the Dashboard.")
            self.kickoff_btn.setVisible(False)

    def _kickoff(self) -> None:
        if self.fixture is None:
            return
        self.eng.begin_match_day()
        self.live = self.eng.start_live_match(self.fixture.id)
        self._done_committed = False
        side = self.live.user_side
        self.lobby.setVisible(False)
        self.live_view.setVisible(True)
        self.finish_btn.setVisible(False)
        self.skip_btn.setVisible(True)
        self.play_btn.setVisible(True)
        self.play_btn.setText("Pause")
        self.feed.clear()
        self.pitch.set_teams(self.live)
        self.momentum.set_value(0, animate=False)
        for m, b in self.ment_btns.items():
            b.setChecked(m == self.live.mentality[side])
        self._fill_sub_boxes()
        self._update_hud()
        self._write(self.live.events)
        self.msg.setText(f"You are managing {self.live.teams[side].name}. Use shouts and mentality to swing momentum.")
        self.anim.start()
        self.timer.start(SPEEDS[self.speed.currentText()])

    # ---- loop ----
    def _step(self) -> None:
        if self.live is None or self.live.finished:
            self.timer.stop()
            return
        events = self.live.step()
        self._write(events)
        self._update_hud()
        for e in events:
            if e.kind == "goal":
                self.pitch.goal(e.side)
        pause = any(e.kind in ("halftime",) or (e.kind in ("red", "injury") and e.side == self.live.user_side) for e in events)
        if self.live.finished:
            self._full_time()
        elif pause:
            self.timer.stop()
            self.play_btn.setText("Resume")
            self.msg.setText("Paused: make changes, then resume.")
            self._fill_sub_boxes()

    def _animate(self) -> None:
        self.momentum.tick()
        self.pitch.advance()

    def _toggle(self) -> None:
        if self.live is None or self.live.finished:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("Resume")
        else:
            self.timer.start(SPEEDS[self.speed.currentText()])
            self.play_btn.setText("Pause")

    def _speed(self, name: str) -> None:
        if self.timer.isActive():
            self.timer.start(SPEEDS[name])

    def _skip(self) -> None:
        if self.live is None:
            return
        self.timer.stop()
        while not self.live.finished:
            self._write(self.live.step())
        self._update_hud()
        self._full_time()

    def _full_time(self) -> None:
        self.timer.stop()
        self.play_btn.setVisible(False)
        self.skip_btn.setVisible(False)
        self.finish_btn.setVisible(True)
        self.msg.setText("Full-time. Continue to record the result.")

    # ---- HUD ----
    def _write(self, events) -> None:
        for e in reversed(events):
            if not e.text:
                continue
            it = QListWidgetItem(e.text)
            col = KIND_COLOR.get(e.kind)
            if col:
                it.setForeground(QColor(col))
            self.feed.insertItem(0, it)

    def _update_hud(self) -> None:
        lv = self.live
        h, a = lv.teams["home"].name, lv.teams["away"].name
        self.scoreboard.setText(f"{h}  {lv.score['home']} - {lv.score['away']}  {a}     ·     {lv.minute}'")
        self.momentum.set_value(lv.momentum)
        self.pitch.set_momentum(lv.momentum)
        self.pitch.update_lineups(lv)
        s = lv.stats
        n = max(lv.chunk, 1)
        for key, (hl, al) in self.stat_labels.items():
            fmt = next(f for _t, k, f in STAT_ROWS if k == key)
            if key == "poss":
                hv, av = s["home"]["poss"] / n, s["away"]["poss"] / n
            elif key == "acc":
                hv = 100 * s["home"]["pass_ok"] / s["home"]["passes"] if s["home"]["passes"] else 0
                av = 100 * s["away"]["pass_ok"] / s["away"]["passes"] if s["away"]["passes"] else 0
            else:
                hv, av = s["home"][key], s["away"][key]
            hl.setText(fmt.format(int(hv) if "d" in fmt else hv))
            al.setText(fmt.format(int(av) if "d" in fmt else av))
        xs = [0] + [r["minute"] for r in lv.history]
        self.home_line.setData(xs, [0.0] + [r["xg_home"] for r in lv.history])
        self.away_line.setData(xs, [0.0] + [r["xg_away"] for r in lv.history])
        side = lv.user_side
        self.subs_left.setText(f"Substitutions left: {5 - lv.subs_used[side]}")

    def _fill_sub_boxes(self) -> None:
        lv, side = self.live, self.live.user_side
        self.out_box.clear()
        self.in_box.clear()
        for slot, p in lv.lineup(side):
            if p:
                self.out_box.addItem(f"{slot.label} {p.name} ({p.fitness}%)", p.id)
        for p in lv.bench[side]:
            self.in_box.addItem(f"{p.position} {p.name} · {p.overall}", p.id)

    # ---- touchline actions ----
    def _mentality(self, m: str) -> None:
        if self.live is None:
            return
        self.live.set_mentality(self.live.user_side, m)
        for k, b in self.ment_btns.items():
            b.setChecked(k == m)
        self._write(self.live.events[-1:])

    def _shout(self, name: str) -> None:
        if self.live is None or self.live.finished:
            return
        self.msg.setText(self.live.shout(self.live.user_side, name))
        self._write(self.live.events[-1:])
        self._update_hud()

    def _sub(self) -> None:
        if self.live is None or self.live.finished or self.out_box.currentData() is None or self.in_box.currentData() is None:
            return
        ok, text = self.live.substitute(self.live.user_side, self.out_box.currentData(), self.in_box.currentData())
        self.msg.setText(text)
        self._write(self.live.events[-1:] if ok else [])
        self._fill_sub_boxes()
        self._update_hud()

    # ---- finishing ----
    def _finish(self) -> None:
        if self.live is None or self._done_committed:
            return
        self._done_committed = True
        out = self.eng.commit_live_match(self.fixture.id, self.live)
        self.anim.stop()
        self.live = None
        remaining = self.eng.pending_user_fixtures()
        if remaining:
            self.fixture = remaining[0]
            self.refresh()
            return
        self.finish_btn.setEnabled(False)
        self.msg.setText("Simulating the rest of the matchday...")
        self._worker = AdvanceWorker("day", self)
        self._worker.done.connect(self._day_done)
        self._worker.failed.connect(lambda m: self.msg.setText(f"Engine error: {m}"))
        self._worker.start()

    def _day_done(self) -> None:
        self._worker.wait()
        self.finish_btn.setEnabled(True)
        self.ctx.after_day_advanced()
        self.live_view.setVisible(False)
        self.lobby.setVisible(True)
        self.finished.emit()
