"""GameContext: the one object screens talk to. Wraps session, saves and the engine/services API."""
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from engine import world
from services import catalog, database, finance, gamedata, saves, session as session_mod

MAX_SEASONS = 7
SLOTS = saves.MAX_SLOTS


class GameContext(QObject):
    changed = Signal()          # emitted after any state change (date, finances, lineup...)

    def __init__(self, app_conn, saves_dir: Path | None = None, template: Path | None = None):
        super().__init__()
        self.app_conn = app_conn
        self.saves_dir = saves_dir
        self.session = session_mod.Session()
        self._template_path = template
        self._template_conn = None

    # ---- catalog (club picker) ----
    @property
    def template(self):
        if self._template_conn is None:
            path = catalog.ensure_template(self._template_path)
            self._template_conn = database.connect(path)
        return self._template_conn

    # ---- session ----
    @property
    def user(self):
        return self.session.user

    @property
    def game(self):
        return self.session.game

    @property
    def in_game(self) -> bool:
        return self.session.game is not None

    def login(self, user) -> None:
        self.session.user = user

    def logout(self) -> None:
        world.unbind()
        self.session.close_game()
        self.session.user = None

    def list_saves(self):
        return saves.list_saves(self.app_conn, self.user.id)

    def start_new(self, slot: int, club_id: int, club_name: str) -> None:
        world.unbind()
        self.session.close_game()
        template_path = catalog.ensure_template(self._template_path)
        conn = saves.new_game(self.app_conn, self.user.id, slot, club_id, club_name, self.saves_dir, template_path)
        gamedata.set_meta(conn, "user_club_id", club_id)
        gamedata.set_meta(conn, "season", 1)
        gamedata.set_meta(conn, "matchday", 0)
        gamedata.set_meta(conn, "formation", "4-3-3")
        self._enter(conn, slot, club_id, club_name)

    def load(self, slot: int) -> None:
        world.unbind()
        self.session.close_game()
        conn = saves.load_game(self.app_conn, self.user.id, slot, self.saves_dir)
        club_id = gamedata.get_meta(conn, "user_club_id")
        self._enter(conn, slot, club_id, gamedata.get_club(conn, club_id).name)

    def _enter(self, conn, slot, club_id, club_name) -> None:
        s = self.session
        s.game, s.slot, s.club_id, s.club_name = conn, slot, club_id, club_name
        self.engine = world.bind(conn, club_id)
        self.changed.emit()

    def delete_save(self, slot: int) -> None:
        if self.session.slot == slot:
            self.session.close_game()
        saves.delete_save(self.app_conn, self.user.id, slot, self.saves_dir)

    def save(self) -> None:
        saves.save_game(self.app_conn, self.user.id, self.session.slot, self.season, self.date_str,
                        self.game, self.saves_dir)

    # ---- game state ----
    @property
    def season(self) -> int:
        return gamedata.get_meta(self.game, "season", 1)

    @property
    def matchday(self) -> int:
        return gamedata.get_meta(self.game, "matchday", 0)

    @property
    def date_str(self) -> str:
        start = date.fromisoformat(gamedata.START_DATE) + timedelta(days=365 * (self.season - 1))
        return (start + timedelta(days=7 * self.matchday)).isoformat()

    @property
    def career_over(self) -> bool:
        return self.season > MAX_SEASONS

    def club(self):
        return gamedata.get_club(self.game, self.session.club_id)

    def league_name(self) -> str:
        return gamedata.league_name_for_club(self.game, self.session.club_id)

    def squad(self):
        return gamedata.get_squad(self.game, self.session.club_id)

    def club_name_of(self, club_id: int) -> str:
        r = self.game.execute("SELECT name FROM clubs WHERE id=?", (club_id,)).fetchone()
        return r[0] if r else f"Club {club_id}"

    def finance_summary(self):
        return finance.get_summary(self.session.club_id, self.season, self.game)

    def next_fixture(self):
        for f in world.get_fixtures(self.session.club_id):
            if not f.played:
                return f
        return None

    # ---- time (called after the worker thread has run the engine call) ----
    def after_day_advanced(self) -> None:
        self.changed.emit()      # the engine already moved the calendar

    def after_season_advanced(self) -> None:
        self.changed.emit()
