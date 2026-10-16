from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from engine import tactics
from ui.components.panel import Panel, page_header
from ui.context import GameContext


class TrainingScreen(QWidget):
    """Weekly training matrix: one session per weekday, with fatigue and injury-risk feedback."""

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Training", "Plan the week. Hard sessions build the squad but raise fatigue and injury risk."))

        grid_panel = Panel("Weekly matrix")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        self.boxes: list[QComboBox] = []
        self.descs: list[QLabel] = []
        for i, day in enumerate(tactics.PLAN_DAYS):
            d = QLabel(day.upper())
            d.setObjectName("cardTitle")
            box = QComboBox()
            for key, b in tactics.TRAINING_BLOCKS.items():
                box.addItem(b.name, key)
            box.currentIndexChanged.connect(self._changed)
            desc = QLabel("")
            desc.setObjectName("muted")
            desc.setWordWrap(True)
            grid.addWidget(d, 0, i)
            grid.addWidget(box, 1, i)
            grid.addWidget(desc, 2, i)
            self.boxes.append(box)
            self.descs.append(desc)
        grid_panel.body.addLayout(grid)
        lay.addWidget(grid_panel)

        row = QHBoxLayout()
        fat = Panel("Fatigue & injury risk")
        self.load_bar = QProgressBar()
        self.load_bar.setRange(0, 16)
        self.load_label = QLabel("")
        self.load_label.setObjectName("accent")
        self.risk = QLabel("")
        self.risk.setWordWrap(True)
        fat.body.addWidget(self.load_label)
        fat.body.addWidget(self.load_bar)
        fat.body.addWidget(self.risk)
        fat.setMinimumHeight(170)
        row.addWidget(fat, 1)
        eff = Panel("Expected weekly effect")
        self.effect = QLabel("")
        self.effect.setWordWrap(True)
        eff.body.addWidget(self.effect)
        self.tip = QLabel("")
        self.tip.setObjectName("muted")
        self.tip.setWordWrap(True)
        eff.body.addWidget(self.tip)
        eff.setMinimumHeight(170)
        row.addWidget(eff, 1)
        lay.addLayout(row)

        btns = QHBoxLayout()
        self.balanced = QPushButton("Balanced week")
        self.match_week = QPushButton("Match-week taper")
        self.heavy = QPushButton("Pre-season block")
        self.balanced.clicked.connect(lambda: self._preset(tactics.DEFAULT_PLAN))
        self.match_week.clicked.connect(lambda: self._preset(["cohesion", "defensive_shape", "set_pieces", "recovery", "recovery"]))
        self.heavy.clicked.connect(lambda: self._preset(["fitness", "pressing", "transitions", "final_third", "recovery"]))
        for b in (self.balanced, self.match_week, self.heavy):
            btns.addWidget(b)
        btns.addStretch(1)
        lay.addLayout(btns)
        lay.addStretch(1)

    def refresh(self) -> None:
        if not self.ctx.in_game:
            return
        plan = self.ctx.engine.tactics_of(self.ctx.session.club_id)["training"]
        self._loading = True
        for box, key in zip(self.boxes, plan):
            box.setCurrentIndex(max(0, box.findData(key)))
        self._loading = False
        self._update()

    def _plan(self) -> list[str]:
        return [b.currentData() for b in self.boxes]

    def _preset(self, plan) -> None:
        self._loading = True
        for box, key in zip(self.boxes, plan):
            box.setCurrentIndex(box.findData(key))
        self._loading = False
        self._changed()

    def _changed(self) -> None:
        if self._loading:
            return
        self.ctx.engine.set_training_plan(self._plan())
        self._update()

    def _update(self) -> None:
        plan = self._plan()
        for d, k in zip(self.descs, plan):
            d.setText(tactics.TRAINING_BLOCKS[k].description)
        load = tactics.plan_load(plan)
        self.load_bar.setValue(min(16, load))
        self.load_label.setText(f"Weekly load {load}")
        mult = tactics.injury_risk_multiplier(plan)
        level = "Low" if mult <= 1.0 else "Moderate" if mult < 1.3 else "High"
        self.risk.setText(f"Injury risk: {level} (x{mult:.2f}). Loads above 9 raise the chance of match injuries.")
        fit = tactics.weekly_fitness_change(plan)
        gain = sum(tactics.TRAINING_BLOCKS[k].understanding for k in plan)
        bi = sum(tactics.TRAINING_BLOCKS[k].buy_in for k in plan)
        self.effect.setText(f"Fitness recovery: {fit:+.0f}% per week\nTactical understanding: +{gain:.1f}\nBuy-in: {bi:+.1f}")
        md = self.ctx.matchday
        self.tip.setText("Periodisation: run heavy blocks early in the season, then taper before key fixtures. "
                         + ("It is pre-season: a good time for fitness work." if md == 0 else
                            "Mid-season: keep load moderate so the squad stays fresh."))
