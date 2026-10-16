import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from services import catalog, database  # noqa: E402
from ui.main_window import MainWindow, load_theme  # noqa: E402


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    return catalog.ensure_template(tmp_path_factory.mktemp("tpl") / "template.db")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    load_theme(app)
    return app


@pytest.fixture
def window(qapp, tmp_path, template):
    w = MainWindow(database.init_app_db(tmp_path / "app.db"), tmp_path / "saves", template)
    yield w
    w.ctx.session.close_game()
    w.close()


def signup(w, name="tester_1"):
    lg = w.login
    lg.set_register_mode(True)
    lg.username.setText(name)
    lg.password.setText("password123")
    lg.confirm.setText("password123")
    lg.submit.click()


def start_career(w, slot=1):
    st = w.start
    st._pick_slot(slot)
    st.table.selectRow(0)
    assert st.start_btn.isEnabled()
    st.start_btn.click()


def test_signup_goes_to_career_select(window):
    signup(window)
    assert window.ctx.user.username == "tester_1"
    assert window._root.currentIndex() == 1
    assert window.start.table.rowCount() == 96


def test_bad_login_and_mismatch(window):
    lg = window.login
    lg.username.setText("nobody")
    lg.password.setText("whatever123")
    lg.submit.click()
    assert "Invalid" in lg.message.text()
    lg.set_register_mode(True)
    lg.username.setText("tester_2")
    lg.password.setText("password123")
    lg.confirm.setText("different123")
    lg.submit.click()
    assert "do not match" in lg.message.text()


def test_league_filter(window):
    signup(window)
    combo = window.start.league_combo
    combo.setCurrentIndex(1)
    assert window.start.table.rowCount() == 20
    combo.setCurrentIndex(3)       # Bundesliga
    assert window.start.table.rowCount() == 18


def test_start_career_and_dashboard(window):
    signup(window)
    start_career(window)
    assert window._root.currentIndex() == 2
    d = window.screens["dashboard"]
    assert d.cards["squad"]._value.text() == "24"
    assert window.top_club.text() == window.ctx.session.club_name
    assert window.ctx.season == 1 and window.ctx.matchday == 0


def test_advance_matchday_runs_in_worker(window, qapp):
    signup(window)
    start_career(window)
    d = window.screens["dashboard"]
    d.advance_btn.click()
    d._worker.wait()
    qapp.processEvents()
    assert window.ctx.matchday == 1 and d.status.text() == "Matchday played."
    assert window.ctx.date_str == "2026-08-08"


def test_team_toggle_and_formation(window):
    signup(window)
    start_career(window)
    window.menu.select("team")
    team = window.screens["team"]
    assert len(team.active_ids) == 11 and "11 / 11" in team.count_label.text()
    gk_before = team.active_ids[0]
    team.toggle(team.active_ids[-1])
    assert len(team.active_ids) == 10
    team.toggle(gk_before)
    assert len(team.active_ids) == 9
    team.auto_assign()
    assert len(team.active_ids) == 11
    team.formation.setCurrentText("4-4-2")
    assert len(team.active_ids) == 11
    assert sum(p is not None for _, p in team.pitch._assignment) == 11


def test_sponsors_accept_limit_and_finance_update(window):
    signup(window)
    start_career(window)
    window.menu.select("finances")
    fin = window.screens["finances"]
    before = window.ctx.finance_summary().income
    fin._accept(fin_offer(window, 0))
    assert window.ctx.finance_summary().income > before
    fin._accept(fin_offer(window, 1))
    fin._accept(fin_offer(window, 2))
    assert fin.msg.text() == ""
    from services import finance
    assert len(finance.active_sponsorships(window.ctx.game, window.ctx.session.club_id, 1)) == 3


def fin_offer(w, i):
    from services import finance
    return finance.offers(w.ctx.game, w.ctx.session.club_id, w.ctx.season)[i]


def test_save_load_roundtrip_and_delete(window):
    signup(window)
    start_career(window, slot=2)
    club = window.ctx.session.club_name
    window.ctx.engine.advance_day(); window.ctx.after_day_advanced()
    window._action("save")
    window._action("load")
    assert window._root.currentIndex() == 1
    window.start._load(2)
    assert window.ctx.session.club_name == club and window.ctx.matchday == 1
    window._action("load")
    window.start._delete(2)                      # first click arms
    assert window.ctx.list_saves()
    window.start._delete(2)                      # second click deletes
    assert not window.ctx.list_saves()


def test_every_page_renders(window):
    signup(window)
    start_career(window)
    for key in window._index:
        window.menu.select(key)
        window.pages.currentWidget().grab()


def test_logout_returns_to_login(window):
    signup(window)
    start_career(window)
    window.logout()
    assert window._root.currentIndex() == 0 and window.ctx.user is None and not window.ctx.in_game


def test_new_screens_and_live_match(window, qapp):
    signup(window)
    start_career(window, slot=3)
    for key in ("tactics", "training", "transfers", "statistics", "competitions", "calendar", "dashboard", "matchday"):
        window.menu.select(key)
        qapp.processEvents()
    tac = window.screens["tactics"]
    ids = tac._ids()
    tac._swap(1, 2)
    assert tac._ids()[1] == ids[2]
    md = window.screens["matchday"]
    md._kickoff()
    assert md.live is not None
    md._skip()
    assert md.finish_btn.isVisible() or md.live.finished
    md._finish()
    md._worker.wait()
    qapp.processEvents()
    assert window.ctx.matchday == 1
