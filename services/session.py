"""Holds the logged-in user and the live game connection for the running app."""
from dataclasses import dataclass, field
import sqlite3


@dataclass
class Session:
    user: object | None = None
    slot: int | None = None
    game: sqlite3.Connection | None = None
    club_id: int | None = None
    club_name: str = ""

    def close_game(self) -> None:
        if self.game is not None:
            self.game.close()
        self.game = None
        self.slot = None
        self.club_id = None
        self.club_name = ""


current = Session()   # simple module-level default; the UI can also own its own instance
