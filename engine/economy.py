"""Club economics: season projections, weekly cash flow, prize money. Pure Python over sqlite3 rows."""
import sqlite3

SLOTS_PER_SEASON = 38
HOME_GAMES = 19
TICKET_PRICE = 45.0
LEAGUE_PRIZE_TOP = 45_000_000.0          # champion; last place gets ~9%
CL_PRIZE = {"Group": 12e6, "Round of 16": 20e6, "Quarter-final": 28e6, "Semi-final": 38e6, "Final": 48e6, "Winner": 70e6}
CUP_PRIZE = {"Winner": 8e6, "Final": 4e6, "Semi-final": 2e6}
BALANCE_FLOOR = -150e6                    # safeguard: clubs cannot spiral into absurd debt


def projection(conn: sqlite3.Connection, club_id: int, season: int) -> dict:
    """Baseline full-season income and expenses (before prizes and transfers)."""
    club = conn.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone()
    wages = conn.execute("SELECT COALESCE(SUM(wage),0) FROM contracts WHERE club_id=?", (club_id,)).fetchone()[0]
    spons = conn.execute(
        "SELECT COALESCE(SUM(annual_value),0) FROM sponsorships WHERE club_id=? AND active=1 "
        "AND start_season<=? AND end_season>=?", (club_id, season, season)).fetchone()[0]
    attendance = 0.55 + 0.4 * (club["reputation"] / 100)
    income = {"matchday": club["stadium_capacity"] * attendance * TICKET_PRICE * HOME_GAMES,
              "tv": 15_000_000.0 + club["reputation"] * 700_000.0, "sponsors": spons}
    expenses = {"wages": wages, "stadium": club["stadium_capacity"] * 380.0,
                "operations": 30_000_000.0 + club["reputation"] * 800_000.0}
    return {"income": income, "expenses": expenses, "wage_bill": wages}


def sync_budget(conn: sqlite3.Connection, club_id: int | None = None) -> None:
    """Transfer budget follows the bank balance (half of it, never negative)."""
    where, args = ("WHERE id=?", (club_id,)) if club_id else ("", ())
    conn.execute(f"UPDATE clubs SET transfer_budget = MAX(0, balance * 0.5) {where}", args)


def weekly_tick(conn: sqlite3.Connection, season: int) -> None:
    """Apply one slot of cash flow to every club."""
    rows = conn.execute("SELECT id FROM clubs").fetchall()
    for r in rows:
        p = projection(conn, r["id"], season)
        net = (sum(p["income"].values()) - sum(p["expenses"].values())) / SLOTS_PER_SEASON
        conn.execute("UPDATE clubs SET balance = MAX(?, balance + ?) WHERE id=?", (BALANCE_FLOOR, net, r["id"]))
    sync_budget(conn)


def book(conn: sqlite3.Connection, club_id: int, season: int, slot: int, category: str, amount: float,
         description: str = "") -> None:
    conn.execute("INSERT INTO finances (club_id, season, matchday, category, amount, description) VALUES (?,?,?,?,?,?)",
                 (club_id, season, slot, category, amount, description))
    conn.execute("UPDATE clubs SET balance = MAX(?, balance + ?) WHERE id=?", (BALANCE_FLOOR, amount, club_id))


def league_prize(position: int, n_clubs: int) -> float:
    return LEAGUE_PRIZE_TOP * (1 - (position - 1) / n_clubs) ** 1.6 + 4_000_000.0
