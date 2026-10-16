from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from services import database
from ui.components.menu import MenuPanel
from ui.context import GameContext
from ui.screens.calendar import CalendarScreen
from ui.screens.competitions import CompetitionsScreen
from ui.screens.dashboard import DashboardScreen
from ui.screens.finances import FinancesScreen
from ui.screens.login import LoginScreen
from ui.screens.matchday import MatchDayScreen
from ui.screens.scouting import ScoutingScreen
from ui.screens.statistics import StatisticsScreen
from ui.screens.tactics import TacticsScreen
from ui.screens.training import TrainingScreen
from ui.screens.settings import SettingsScreen
from ui.screens.start import StartScreen
from ui.screens.team import TeamScreen

THEME = Path(__file__).with_name("theme.qss")
PAGES = [("dashboard", "Dashboard"), ("matchday", "Match Day"), ("tactics", "Tactics"), ("training", "Training"),
         ("team", "Squad"), ("transfers", "Scouting"), ("calendar", "Calendar"), ("competitions", "Competitions"),
         ("statistics", "Statistics"), ("finances", "Finances"), ("settings", "Settings")]
ACTIONS = [("save", "Save Game"), ("load", "Load Game"), ("exit", "Exit")]


class MainWindow(QMainWindow):
    """Flow: login -> career select -> game shell (top bar, menu, pages)."""

    def __init__(self, app_conn=None, saves_dir=None, template=None):
        super().__init__()
        self.setWindowTitle("Football Career Mode")
        self.resize(1200, 760)
        self.app_conn = app_conn or database.init_app_db()
        self.ctx = GameContext(self.app_conn, saves_dir, template)

        self._root = QStackedWidget()
        self.setCentralWidget(self._root)
        self.login = LoginScreen(self.app_conn)
        self.login.logged_in.connect(self._on_login)
        self.start = StartScreen(self.ctx)
        self.start.entered.connect(self._enter_game)
        self.start.logout_requested.connect(self.logout)
        self._root.addWidget(self.login)       # 0
        self._root.addWidget(self.start)       # 1
        self._root.addWidget(self._build_shell())  # 2

    # ---- shell ----
    def _build_shell(self) -> QWidget:
        shell = QWidget()
        shell.setObjectName("root")
        col = QVBoxLayout(shell)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(12)

        top = QFrame()
        top.setObjectName("topbar")
        t = QHBoxLayout(top)
        t.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("FOOTBALL CAREER MODE")
        brand.setObjectName("sectionTitle")
        self.top_message = QLabel("")
        self.top_message.setObjectName("topMessage")
        self.top_date = QLabel("")
        self.top_date.setObjectName("topDate")
        self.top_club = QLabel("")
        self.top_club.setObjectName("topClub")
        t.addWidget(brand)
        t.addWidget(self.top_message, 1)
        t.addWidget(self.top_date)
        t.addSpacing(16)
        t.addWidget(self.top_club)
        col.addWidget(top)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.menu = MenuPanel(PAGES, ACTIONS)
        self.menu.page_selected.connect(self.show_page)
        self.menu.action_triggered.connect(self._action)
        self.pages = QStackedWidget()
        self.pages.setObjectName("content")
        self.screens = {
            "dashboard": DashboardScreen(self.ctx),
            "team": TeamScreen(self.ctx),
            "calendar": CalendarScreen(self.ctx),
            "matchday": MatchDayScreen(self.ctx),
            "tactics": TacticsScreen(self.ctx),
            "training": TrainingScreen(self.ctx),
            "transfers": ScoutingScreen(self.ctx),
            "statistics": StatisticsScreen(self.ctx),
            "competitions": CompetitionsScreen(self.ctx),
            "finances": FinancesScreen(self.ctx),
            "settings": SettingsScreen(self.ctx),
        }
        self.screens["settings"].logout_requested.connect(self.logout)
        self.screens["dashboard"].play_requested.connect(lambda: self.menu.select("matchday"))
        self.screens["matchday"].finished.connect(lambda: self.menu.select("dashboard"))
        self._index = {k: self.pages.addWidget(w) for k, w in self.screens.items()}
        row.addWidget(self.menu)
        row.addWidget(self.pages, 1)
        col.addLayout(row, 1)
        self.ctx.changed.connect(self._update_top_bar)
        return shell

    def show_page(self, key: str) -> None:
        self.pages.setCurrentIndex(self._index[key])
        self.screens[key].refresh()

    def _update_top_bar(self) -> None:
        if not self.ctx.in_game:
            return
        self.top_message.setText(f"{self.ctx.league_name()} · Season {min(self.ctx.season, 7)} · Matchday {self.ctx.matchday}")
        self.top_date.setText(self.ctx.date_str)
        self.top_club.setText(self.ctx.session.club_name)

    # ---- flow ----
    def _on_login(self, user) -> None:
        self.ctx.login(user)
        self.start.refresh()
        self._root.setCurrentIndex(1)

    def _enter_game(self) -> None:
        self._update_top_bar()
        self._root.setCurrentIndex(2)
        self.menu.select("dashboard")

    def _action(self, key: str) -> None:
        if key == "save":
            self.ctx.save()
            self.top_message.setText("Game saved.")
        elif key == "load":
            self.start.refresh()
            self._root.setCurrentIndex(1)
        elif key == "exit":
            self.close()

    def logout(self) -> None:
        self.ctx.logout()
        self.login.reset()
        self._root.setCurrentIndex(0)

    def closeEvent(self, e) -> None:
        if self.ctx.in_game and self.ctx.user:
            try:
                self.ctx.save()
            except Exception:
                pass
        super().closeEvent(e)


def load_theme(app) -> None:
    app.setStyleSheet(THEME.read_text(encoding="utf-8"))
