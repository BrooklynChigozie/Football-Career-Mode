from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from ui.components.stat_card import StatCard


class DashboardScreen(QWidget):
    """Placeholder dashboard. Shows stub numbers until the engine and finance services are wired in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        self.subtitle = QLabel("Placeholder data until the engine is connected.")
        self.subtitle.setObjectName("pageSubtitle")
        lay.addWidget(title)
        lay.addWidget(self.subtitle)

        grid = QGridLayout()
        grid.setSpacing(16)
        self.cards = {
            "club": StatCard("Club", "-", "No career started yet"),
            "season": StatCard("Season", "1 / 7"),
            "position": StatCard("League position", "-"),
            "balance": StatCard("Balance", "-"),
            "budget": StatCard("Transfer budget", "-"),
            "next": StatCard("Next fixture", "-"),
        }
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, i // 3, i % 3)
        lay.addLayout(grid)
        lay.addStretch(1)

    def set_username(self, name: str) -> None:
        self.subtitle.setText(f"Welcome, {name}. Placeholder data until the engine is connected.")
