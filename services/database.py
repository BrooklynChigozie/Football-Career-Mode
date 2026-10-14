"""SQLite access: the master app.db (users, save metadata) and per-save game DBs."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from services import paths

APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash BLOB NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login    TEXT
);
CREATE TABLE IF NOT EXISTS saves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slot        INTEGER NOT NULL,
    club_id     INTEGER,
    club_name   TEXT,
    season      INTEGER NOT NULL DEFAULT 1,
    game_date   TEXT,
    file_name   TEXT NOT NULL,
    last_played TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_saves_user ON saves(user_id);
"""

# Game data tables. Draft: models.py (shared with Brooklyn) is the source of truth,
# so column names here must be kept in sync with it once it is agreed.
GAME_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT, num_clubs INTEGER
);
CREATE TABLE IF NOT EXISTS clubs (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, league_id INTEGER REFERENCES leagues(id),
    stadium_capacity INTEGER NOT NULL DEFAULT 30000,
    reputation INTEGER NOT NULL DEFAULT 50,
    balance REAL NOT NULL DEFAULT 0,
    transfer_budget REAL NOT NULL DEFAULT 0,
    wage_budget REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL,
    nationality TEXT, position TEXT NOT NULL,
    overall INTEGER NOT NULL, potential INTEGER NOT NULL,
    value REAL NOT NULL DEFAULT 0,
    club_id INTEGER REFERENCES clubs(id),
    morale INTEGER NOT NULL DEFAULT 70, fitness INTEGER NOT NULL DEFAULT 100,
    retired INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contracts (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    club_id INTEGER NOT NULL REFERENCES clubs(id),
    wage REAL NOT NULL, expires_season INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, league_id INTEGER
);
CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT, competition_id INTEGER NOT NULL REFERENCES competitions(id),
    season INTEGER NOT NULL, matchday INTEGER NOT NULL,
    home_id INTEGER NOT NULL REFERENCES clubs(id), away_id INTEGER NOT NULL REFERENCES clubs(id),
    home_goals INTEGER, away_goals INTEGER, played INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id INTEGER NOT NULL REFERENCES fixtures(id),
    minute INTEGER NOT NULL, kind TEXT NOT NULL,
    player_id INTEGER REFERENCES players(id), club_id INTEGER REFERENCES clubs(id)
);
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, season INTEGER NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(id),
    from_club_id INTEGER, to_club_id INTEGER, fee REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS finances (
    id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL REFERENCES clubs(id),
    season INTEGER NOT NULL, matchday INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL, amount REAL NOT NULL, description TEXT
);
CREATE TABLE IF NOT EXISTS sponsorships (
    id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL REFERENCES clubs(id),
    sponsor TEXT NOT NULL, annual_value REAL NOT NULL,
    start_season INTEGER NOT NULL, end_season INTEGER NOT NULL,
    bonus_condition TEXT, bonus_amount REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_players_club ON players(club_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_comp_season ON fixtures(competition_id, season, matchday);
CREATE INDEX IF NOT EXISTS idx_fixtures_home ON fixtures(home_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_away ON fixtures(away_id);
CREATE INDEX IF NOT EXISTS idx_events_fixture ON match_events(fixture_id);
CREATE INDEX IF NOT EXISTS idx_transfers_season ON transfers(season);
CREATE INDEX IF NOT EXISTS idx_finances_club_season ON finances(club_id, season);
CREATE INDEX IF NOT EXISTS idx_spons_club ON sponsorships(club_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Commit on success, roll back on error. Use for bulk writes."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_app_db(path: Path | None = None) -> sqlite3.Connection:
    conn = connect(path or paths.APP_DB)
    conn.executescript(APP_SCHEMA)
    conn.commit()
    return conn


def init_game_db(path: Path) -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(GAME_SCHEMA)
    conn.commit()
    return conn
