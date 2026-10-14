import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from services import database  # noqa: E402
from ui.main_window import MainWindow, load_theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    load_theme(app)
    return app


@pytest.fixture
def window(qapp, tmp_path):
    w = MainWindow(database.init_app_db(tmp_path / "app.db"))
    yield w
    w.close()


def test_signup_then_dashboard_then_logout(window):
    lg = window.login
    lg.set_register_mode(True)
    lg.username.setText("tester_1")
    lg.password.setText("password123")
    lg.confirm.setText("password123")
    lg.submit.click()
    assert window.user.username == "tester_1"
    assert window._root.currentIndex() == 1
    assert window.pages.currentWidget() is window.dashboard
    window.logout()
    assert window._root.currentIndex() == 0 and window.user is None


def test_bad_login_shows_error(window):
    lg = window.login
    lg.username.setText("nobody")
    lg.password.setText("whatever123")
    lg.submit.click()
    assert "Invalid" in lg.message.text() and window.user is None


def test_password_mismatch(window):
    lg = window.login
    lg.set_register_mode(True)
    lg.username.setText("tester_2")
    lg.password.setText("password123")
    lg.confirm.setText("different123")
    lg.submit.click()
    assert "do not match" in lg.message.text()


def test_navigation(window):
    window._on_login(type("U", (), {"username": "x"})())
    window.sidebar.select("squad")
    assert window.pages.currentIndex() == window._page_index["squad"]
