"""Read/write helpers on a game database (the live save). Pure sqlite, no UI imports."""
import json
import sqlite3

from engine.models import Club, Player

START_DATE = "2026-08-01"


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
    conn.commit()


def list_leagues(conn):
    return conn.execute("SELECT id, name, country, num_clubs FROM leagues ORDER BY id").fetchall()


def _club(r) -> Club:
    return Club(id=r["id"], name=r["name"], league_id=r["league_id"], stadium_capacity=r["stadium_capacity"],
                reputation=r["reputation"], balance=r["balance"], transfer_budget=r["transfer_budget"],
                wage_budget=r["wage_budget"])


def list_clubs(conn, league_id: int | None = None) -> list[Club]:
    q = "SELECT * FROM clubs" + (" WHERE league_id=?" if league_id else "") + " ORDER BY reputation DESC, name"
    return [_club(r) for r in conn.execute(q, (league_id,) if league_id else ())]


def get_club(conn, club_id: int) -> Club:
    return _club(conn.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone())


def get_squad(conn, club_id: int) -> list[Player]:
    rows = conn.execute(
        """SELECT p.*, COALESCE(c.wage,0) AS wage, COALESCE(c.expires_season,0) AS expires
           FROM players p LEFT JOIN contracts c ON c.player_id=p.id
           WHERE p.club_id=? AND p.retired=0 ORDER BY p.overall DESC""", (club_id,)).fetchall()
    return [Player(id=r["id"], name=r["name"], age=r["age"], position=r["position"], overall=r["overall"],
                   potential=r["potential"], nationality=r["nationality"] or "", value=r["value"],
                   club_id=r["club_id"], wage=r["wage"], contract_expires=r["expires"],
                   morale=r["morale"], fitness=r["fitness"], retired=bool(r["retired"]),
                   pace=r["pace"], shooting=r["shooting"], passing=r["passing"], dribbling=r["dribbling"],
                   defending=r["defending"], physical=r["physical"], injured_weeks=r["injured_weeks"],
                   suspended_games=r["suspended_games"], yellow_cards=r["yellow_cards"], form=r["form"])
            for r in rows]


def league_name_for_club(conn, club_id: int) -> str:
    r = conn.execute("SELECT l.name FROM clubs c JOIN leagues l ON l.id=c.league_id WHERE c.id=?",
                     (club_id,)).fetchone()
    return r[0] if r else ""
