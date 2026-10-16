from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components.panel import Panel, page_header
from ui.context import GameContext


class SettingsScreen(QWidget):
    logout_requested = Signal()

    def __init__(self, ctx: GameContext, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Settings"))
        p = Panel("Account and career")
        self.info = QLabel("")
        self.info.setWordWrap(True)
        p.body.addWidget(self.info)
        out = QPushButton("Log out")
        out.clicked.connect(self.logout_requested)
        p.body.addWidget(out)
        lay.addWidget(p)
        lay.addStretch(1)

    def refresh(self) -> None:
        if not self.ctx.user:
            return
        g = self.ctx.in_game
        self.info.setText(
            f"Signed in as <b>{self.ctx.user.username}</b><br>"
            + (f"Career: {self.ctx.session.club_name} · save slot {self.ctx.session.slot} · "
               f"season {self.ctx.season} of 7" if g else "No career loaded."))
