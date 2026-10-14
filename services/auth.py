"""Registration and login with bcrypt-hashed passwords."""
import re
import sqlite3
from dataclasses import dataclass

import bcrypt

MIN_PASSWORD_LEN = 8
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class AuthError(Exception):
    """Raised with a user-friendly message the UI can show directly."""


@dataclass(frozen=True)
class User:
    id: int
    username: str


def _validate(username: str, password: str) -> None:
    if not USERNAME_RE.match(username or ""):
        raise AuthError("Username must be 3-20 characters: letters, numbers or underscore.")
    if len(password or "") < MIN_PASSWORD_LEN:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")


def register(conn: sqlite3.Connection, username: str, password: str) -> User:
    username = (username or "").strip()
    _validate(username, password)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise AuthError("That username is already taken.") from None
    return User(cur.lastrowid, username)


def login(conn: sqlite3.Connection, username: str, password: str) -> User:
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        ((username or "").strip(),),
    ).fetchone()
    # Same message for unknown user and wrong password: don't reveal which usernames exist.
    if row is None or not bcrypt.checkpw((password or "").encode("utf-8"), row["password_hash"]):
        raise AuthError("Invalid username or password.")
    conn.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (row["id"],))
    conn.commit()
    return User(row["id"], row["username"])
