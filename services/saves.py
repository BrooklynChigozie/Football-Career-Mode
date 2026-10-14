"""Save slots: one SQLite file per save, metadata in app.db.

Contract (agreed with Brooklyn): save_game(slot) / load_game(slot). The UI layer holds
the current user; here they are explicit so the service stays testable.
"""
import shutil
import sqlite3
from pathlib import Path

from services import database, paths

MAX_SLOTS = 5


class SaveError(Exception):
    pass


def _check_slot(slot: int) -> None:
    if not 1 <= slot <= MAX_SLOTS:
        raise SaveError(f"Slot must be between 1 and {MAX_SLOTS}.")


def _file_for(user_id: int, slot: int, saves_dir: Path) -> Path:
    return saves_dir / f"user{user_id}_slot{slot}.db"


def list_saves(app_conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return app_conn.execute(
        "SELECT * FROM saves WHERE user_id = ? ORDER BY slot", (user_id,)
    ).fetchall()


def new_game(app_conn, user_id: int, slot: int, club_id: int, club_name: str,
             saves_dir: Path | None = None) -> sqlite3.Connection:
    """Create a fresh save file for the slot (overwrites an existing one) and return its connection."""
    _check_slot(slot)
    saves_dir = Path(saves_dir or paths.SAVES_DIR)
    f = _file_for(user_id, slot, saves_dir)
    if f.exists():
        f.unlink()
    game = database.init_game_db(f)
    app_conn.execute(
        """INSERT INTO saves (user_id, slot, club_id, club_name, season, file_name)
           VALUES (?, ?, ?, ?, 1, ?)
           ON CONFLICT(user_id, slot) DO UPDATE SET club_id=excluded.club_id,
             club_name=excluded.club_name, season=1, game_date=NULL,
             file_name=excluded.file_name, last_played=datetime('now')""",
        (user_id, slot, club_id, club_name, f.name),
    )
    app_conn.commit()
    return game


def save_game(app_conn, user_id: int, slot: int, season: int, game_date: str | None,
              game_conn: sqlite3.Connection, saves_dir: Path | None = None) -> None:
    """Flush the live game and update slot metadata. The game DB *is* the save file."""
    _check_slot(slot)
    game_conn.commit()
    cur = app_conn.execute(
        "UPDATE saves SET season=?, game_date=?, last_played=datetime('now') "
        "WHERE user_id=? AND slot=?", (season, game_date, user_id, slot))
    if cur.rowcount == 0:
        raise SaveError(f"No save in slot {slot}; call new_game first.")
    app_conn.commit()


def load_game(app_conn, user_id: int, slot: int, saves_dir: Path | None = None) -> sqlite3.Connection:
    _check_slot(slot)
    saves_dir = Path(saves_dir or paths.SAVES_DIR)
    row = app_conn.execute(
        "SELECT file_name FROM saves WHERE user_id=? AND slot=?", (user_id, slot)).fetchone()
    f = saves_dir / row["file_name"] if row else None
    if row is None or not f.exists():
        raise SaveError(f"Slot {slot} is empty.")
    app_conn.execute("UPDATE saves SET last_played=datetime('now') WHERE user_id=? AND slot=?",
                     (user_id, slot))
    app_conn.commit()
    return database.connect(f)


def delete_save(app_conn, user_id: int, slot: int, saves_dir: Path | None = None) -> None:
    _check_slot(slot)
    saves_dir = Path(saves_dir or paths.SAVES_DIR)
    _file_for(user_id, slot, saves_dir).unlink(missing_ok=True)
    app_conn.execute("DELETE FROM saves WHERE user_id=? AND slot=?", (user_id, slot))
    app_conn.commit()
