"""One-off import of a Kaggle FIFA-style CSV into a game database.

Handles the usual mess: alternative column names, missing positions, duplicate
players, club-name variants. Names stay in the data files so they are easy to swap.
"""
import csv
import random
import re
import sqlite3
from pathlib import Path

from engine import attributes
from services import database

TOP_LEAGUES = {
    "Premier League": "England", "La Liga": "Spain", "Bundesliga": "Germany",
    "Serie A": "Italy", "Ligue 1": "France",
}
# Accepted spellings of each league name in common datasets.
LEAGUE_ALIASES = {
    "english premier league": "Premier League", "premier league": "Premier League",
    "spain primera division": "La Liga", "la liga": "La Liga", "laliga": "La Liga",
    "spanish primera division": "La Liga", "primera division": "La Liga",
    "german 1. bundesliga": "Bundesliga", "bundesliga": "Bundesliga",
    "italian serie a": "Serie A", "serie a": "Serie A",
    "french ligue 1": "Ligue 1", "ligue 1": "Ligue 1",
}
# Canonical field -> possible CSV headers (lower-case).
COLUMNS = {
    "name": ["short_name", "name", "player", "long_name"],
    "age": ["age"],
    "nationality": ["nationality", "nationality_name"],
    "position": ["player_positions", "position", "positions", "best_position"],
    "overall": ["overall", "overall_rating"],
    "potential": ["potential"],
    "value": ["value_eur", "value"],
    "wage": ["wage_eur", "wage"],
    "club": ["club_name", "club", "team"],
    "league": ["league_name", "league"],
    "contract_until": ["club_contract_valid_until", "contract_valid_until"],
    "pace": ["pace"], "shooting": ["shooting"], "passing": ["passing"],
    "dribbling": ["dribbling"], "defending": ["defending"], "physical": ["physic", "physical"],
}
POSITION_GROUPS = {"GK": "GK", "CB": "DF", "LB": "DF", "RB": "DF", "LWB": "DF", "RWB": "DF",
                   "CDM": "MF", "CM": "MF", "CAM": "MF", "LM": "MF", "RM": "MF",
                   "ST": "FW", "CF": "FW", "LW": "FW", "RW": "FW", "LF": "FW", "RF": "FW"}
STOCK = {"DF": "CB", "MF": "CM", "FW": "ST", "GK": "GK"}


def _pick(header: list[str], field: str) -> str | None:
    lower = {h.lower().strip(): h for h in header}
    for cand in COLUMNS[field]:
        if cand in lower:
            return lower[cand]
    return None


def _num(v, default=0.0) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def clean_club_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    return name


def normalise_position(raw: str, overall: int = 0) -> str:
    """First listed position, or a sensible default if missing/unknown."""
    for tok in re.split(r"[,/ ]+", (raw or "").upper()):
        if tok in POSITION_GROUPS:
            return tok
    return "CM"


def import_players_csv(csv_path: Path, game_conn: sqlite3.Connection,
                       start_season: int = 1, base_year: int = 2026) -> dict:
    """Load leagues, clubs, players, contracts. Returns a summary dict (also a cleaning report)."""
    stats = {"rows": 0, "players": 0, "clubs": 0, "skipped_league": 0,
             "duplicates": 0, "bad_rows": 0, "fixed_positions": 0}
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        cols = {f: _pick(reader.fieldnames or [], f) for f in COLUMNS}
        missing = [f for f in ("name", "age", "overall", "club", "league") if cols[f] is None]
        if missing:
            raise ValueError(f"CSV is missing required columns for: {', '.join(missing)}")

        rng = random.Random(2026)          # fixed seed: derived attributes are reproducible
        leagues: dict[str, int] = {}
        clubs: dict[tuple[str, str], int] = {}
        seen: set[tuple] = set()
        with database.transaction(game_conn):
            for league, country in TOP_LEAGUES.items():
                cur = game_conn.execute(
                    "INSERT INTO leagues (name, country) VALUES (?, ?)", (league, country))
                leagues[league] = cur.lastrowid
            for row in reader:
                stats["rows"] += 1
                league = LEAGUE_ALIASES.get((row[cols["league"]] or "").strip().lower())
                if league is None:
                    stats["skipped_league"] += 1
                    continue
                club = clean_club_name(row[cols["club"]])
                name = (row[cols["name"]] or "").strip()
                age = int(_num(row[cols["age"]], 0))
                overall = int(_num(row[cols["overall"]], 0))
                if not club or not name or age <= 0 or overall <= 0:
                    stats["bad_rows"] += 1
                    continue
                nat = (row[cols["nationality"]] if cols["nationality"] else "") or ""
                key = (name.lower(), age, nat.lower(), club.lower())
                if key in seen:
                    stats["duplicates"] += 1
                    continue
                seen.add(key)
                if (league, club) not in clubs:
                    cur = game_conn.execute(
                        "INSERT INTO clubs (name, league_id) VALUES (?, ?)",
                        (club, leagues[league]))
                    clubs[(league, club)] = cur.lastrowid
                raw_pos = row[cols["position"]] if cols["position"] else ""
                pos = normalise_position(raw_pos)
                if not raw_pos or raw_pos.upper().split(",")[0].strip() not in POSITION_GROUPS:
                    stats["fixed_positions"] += 1
                potential = max(int(_num(row[cols["potential"]], overall)) if cols["potential"] else overall, overall)
                value = _num(row[cols["value"]]) if cols["value"] else 0.0
                wage = _num(row[cols["wage"]]) if cols["wage"] else 0.0
                cid = clubs[(league, club)]
                derived = attributes.derive(pos, overall, rng)
                attr = {a: int(_num(row[cols[a]], derived[a])) if cols[a] else derived[a] for a in attributes.ATTRS}
                cur = game_conn.execute(
                    """INSERT INTO players (name, age, nationality, position, overall, potential, value, club_id,
                                            pace, shooting, passing, dribbling, defending, physical)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, age, nat or None, pos, overall, potential, value, cid,
                     attr["pace"], attr["shooting"], attr["passing"], attr["dribbling"], attr["defending"],
                     attr["physical"]))
                until = int(_num(row[cols["contract_until"]], 0)) if cols["contract_until"] else 0
                # Contracts are stored as a season index (1 = first season of the career).
                expires = max(start_season, start_season + (until - base_year)) if until else start_season + 2
                game_conn.execute(
                    "INSERT INTO contracts (player_id, club_id, wage, expires_season) VALUES (?,?,?,?)",
                    (cur.lastrowid, cid, wage * 52, expires))   # weekly wage -> annual
                stats["players"] += 1
            game_conn.execute(
                "UPDATE leagues SET num_clubs = (SELECT COUNT(*) FROM clubs WHERE league_id = leagues.id)")
            derive_club_attributes(game_conn)
            create_competitions(game_conn)
    stats["clubs"] = len(clubs)
    return stats


def derive_club_attributes(conn: sqlite3.Connection) -> None:
    """Kaggle has no stadium or finance data, so derive it from squad strength."""
    for c in conn.execute("SELECT id FROM clubs").fetchall():
        top = [r[0] for r in conn.execute(
            "SELECT overall FROM players WHERE club_id=? ORDER BY overall DESC LIMIT 14", (c["id"],))]
        if not top:
            continue
        avg = sum(top) / len(top)
        wages = conn.execute("SELECT COALESCE(SUM(wage),0) FROM contracts WHERE club_id=?", (c["id"],)).fetchone()[0]
        balance = max(2_000_000.0, (avg - 58) * 5_000_000.0)
        conn.execute(
            """UPDATE clubs SET reputation=?, stadium_capacity=?, balance=?, transfer_budget=?, wage_budget=?
               WHERE id=?""",
            (round(avg), int(min(80000, max(12000, 15000 + (avg - 65) * 4500))), balance, balance * 0.5,
             wages * 1.08, c["id"]))


def create_competitions(conn: sqlite3.Connection) -> None:
    """One league and one cup per league, plus the Champions League."""
    for lg in conn.execute("SELECT id, name FROM leagues").fetchall():
        conn.execute("INSERT INTO competitions (name, kind, league_id) VALUES (?, 'league', ?)", (lg["name"], lg["id"]))
        conn.execute("INSERT INTO competitions (name, kind, league_id) VALUES (?, 'cup', ?)",
                     (f"{lg['name']} Cup", lg["id"]))
    conn.execute("INSERT INTO competitions (name, kind, league_id) VALUES ('Champions League', 'champions_league', NULL)")
