from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from services import database
from ui.components.sidebar import Sidebar
from ui.screens.dashboard import DashboardScreen
from ui.screens.login import LoginScreen
from ui.screens.placeholder import PlaceholderScreen

THEME = Path(__file__).with_name("theme.qss")

NAV = [
    ("dashboard", "Dashboard"),
    ("clubs", "Club selection"),
    ("squad", "Squad"),
    ("finances", "Finances && sponsors"),
    ("settings", "Settings"),
]


class MainWindow(QMainWindow):
    """Login screen first; after login, sidebar + content pages."""

    def __init__(self, app_conn=None):
        super().__init__()
        self.setWindowTitle("Football Career Mode")
        self.resize(1100, 700)
        self.app_conn = app_conn or database.init_app_db()
        self.user = None

        self._root = QStackedWidget()
        self.setCentralWidget(self._root)

        self.login = LoginScreen(self.app_conn)
        self.login.logged_in.connect(self._on_login)
        self._root.addWidget(self.login)

        shell = QWidget()
        shell.setObjectName("root")
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.sidebar = Sidebar(NAV)
        self.sidebar.page_selected.connect(self.show_page)
        self.sidebar.logout_requested.connect(self.logout)
        self.pages = QStackedWidget()
        self.pages.setObjectName("content")
        self._page_index: dict[str, int] = {}
        self.dashboard = DashboardScreen()
        screens = {
            "dashboard": self.dashboard,
            "clubs": PlaceholderScreen("Club selection", "Pick a club from the top five leagues (Week 2)."),
            "squad": PlaceholderScreen("Squad", "Your players and lineup (Week 2)."),
            "finances": PlaceholderScreen("Finances & sponsors", "Income, expenses and sponsors (Weeks 2-3)."),
            "settings": PlaceholderScreen("Settings", "Save slots and preferences."),
        }
        for key, widget in screens.items():
            self._page_index[key] = self.pages.addWidget(widget)
        row.addWidget(self.sidebar)
        row.addWidget(self.pages, 1)
        self._root.addWidget(shell)

    def show_page(self, key: str) -> None:
        self.pages.setCurrentIndex(self._page_index[key])

    def _on_login(self, user) -> None:
        self.user = user
        self.sidebar.set_user(user.username)
        self.dashboard.set_username(user.username)
        self.sidebar.select("dashboard")
        self._root.setCurrentIndex(1)

    def logout(self) -> None:
        self.user = None
        self.login.reset()
        self._root.setCurrentIndex(0)


def load_theme(app) -> None:
    app.setStyleSheet(THEME.read_text(encoding="utf-8"))
