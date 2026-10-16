"""Finance system: summaries computed from the game DB, plus sponsorship tiers.

Contract: get_summary(club_id) returns income, expenses, balance, budget and wage bill.
The game connection comes from the argument or, if omitted, services.session.current.
If there is no game at all (UI tests, demos) it falls back to fixed stub numbers.
"""
import sqlite3

from engine.models import FinanceSummary, Sponsorship
from services import session

HOME_GAMES = 19
TICKET_PRICE = 45.0            # average, in the game's currency
MAX_ACTIVE_SPONSORS = 3


def _conn(conn):
    return conn or session.current.game


def _stub(club_id: int, season: int) -> FinanceSummary:
    inc = {"matchday": 12_000_000.0, "tv": 30_000_000.0, "sponsors": 18_000_000.0}
    exp = {"wages": 45_000_000.0, "stadium": 6_000_000.0}
    return FinanceSummary(club_id, season, sum(inc.values()), sum(exp.values()), 50_000_000.0,
                          20_000_000.0, exp["wages"], inc, exp)


def annual_sponsor_income(conn, club_id: int, season: int) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(annual_value),0) FROM sponsorships WHERE club_id=? AND active=1 "
        "AND start_season<=? AND end_season>=?", (club_id, season, season)).fetchone()[0]


def get_summary(club_id: int, season: int = 1, conn: sqlite3.Connection | None = None) -> FinanceSummary:
    conn = _conn(conn)
    if conn is None:
        return _stub(club_id, season)
    club = conn.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone()
    wages = conn.execute("SELECT COALESCE(SUM(wage),0) FROM contracts WHERE club_id=?", (club_id,)).fetchone()[0]
    attendance = 0.55 + 0.4 * (club["reputation"] / 100)          # form-based attendance comes later
    income = {
        "matchday": club["stadium_capacity"] * attendance * TICKET_PRICE * HOME_GAMES,
        "tv": 15_000_000.0 + club["reputation"] * 700_000.0,
        "sponsors": annual_sponsor_income(conn, club_id, season),
    }
    # Booked one-off items (transfer fees, prize money, bonuses) for this season.
    for cat, amt in conn.execute(
            "SELECT category, SUM(amount) FROM finances WHERE club_id=? AND season=? AND amount>0 GROUP BY category",
            (club_id, season)).fetchall():
        income[cat] = income.get(cat, 0.0) + amt
    expenses = {"wages": wages, "stadium": club["stadium_capacity"] * 380.0,
                "operations": 30_000_000.0 + club["reputation"] * 800_000.0}
    for cat, amt in conn.execute(
            "SELECT category, SUM(amount) FROM finances WHERE club_id=? AND season=? AND amount<0 GROUP BY category",
            (club_id, season)).fetchall():
        expenses[cat] = expenses.get(cat, 0.0) - amt
    return FinanceSummary(
        club_id=club_id, season=season, income=sum(income.values()), expenses=sum(expenses.values()),
        balance=club["balance"], transfer_budget=club["transfer_budget"], wage_bill=wages,
        income_breakdown=income, expense_breakdown=expenses)


def book(conn, club_id: int, season: int, category: str, amount: float, description: str = "",
         matchday: int = 0) -> None:
    """Record a one-off finance item (positive = income) and update the club balance."""
    conn.execute("INSERT INTO finances (club_id, season, matchday, category, amount, description) VALUES (?,?,?,?,?,?)",
                 (club_id, season, matchday, category, amount, description))
    conn.execute("UPDATE clubs SET balance = balance + ? WHERE id=?", (amount, club_id))
    conn.commit()


# ---- Sponsorships: fixed tiers (negotiation is a later nice-to-have) ----

TIERS = [
    # name, share of base value, years, bonus condition, bonus share
    ("Bronze", 0.6, 1, "Win 15 league games", 0.10),
    ("Silver", 1.0, 2, "Finish in the top half", 0.15),
    ("Gold", 1.5, 3, "Qualify for the Champions League", 0.25),
]
SPONSORS = ["Apex Mobile", "Nordwind Airlines", "Kestrel Energy", "Atlas Bank", "Vela Sportswear",
            "Orbit Telecom", "Summit Foods", "Zenith Motors", "Lumen Tech"]


def offers(conn, club_id: int, season: int) -> list[dict]:
    """Three offers scaled to club reputation. Deterministic per club and season."""
    club = conn.execute("SELECT reputation FROM clubs WHERE id=?", (club_id,)).fetchone()
    base = 1_000_000.0 * (club["reputation"] - 45) ** 1.2 / 4        # roughly 3M for a 60 rep club, 20M+ for the top
    out = []
    for i, (tier, share, years, cond, bonus) in enumerate(TIERS):
        out.append({"sponsor": SPONSORS[(club_id + season * 3 + i * 2) % len(SPONSORS)], "tier": tier,
                    "annual_value": round(base * share, -4), "years": years,
                    "bonus_condition": cond, "bonus_amount": round(base * share * bonus, -4)})
    return out


def active_sponsorships(conn, club_id: int, season: int) -> list[Sponsorship]:
    rows = conn.execute("SELECT * FROM sponsorships WHERE club_id=? AND active=1 AND end_season>=? ORDER BY id",
                        (club_id, season)).fetchall()
    return [Sponsorship(r["id"], r["club_id"], r["sponsor"], r["annual_value"], r["start_season"], r["end_season"],
                        r["bonus_condition"] or "", r["bonus_amount"], bool(r["active"])) for r in rows]


class SponsorError(Exception):
    pass


def accept_offer(conn, club_id: int, season: int, offer: dict) -> None:
    if len(active_sponsorships(conn, club_id, season)) >= MAX_ACTIVE_SPONSORS:
        raise SponsorError(f"You can have at most {MAX_ACTIVE_SPONSORS} active sponsors.")
    if any(s.sponsor == offer["sponsor"] for s in active_sponsorships(conn, club_id, season)):
        raise SponsorError(f"{offer['sponsor']} already sponsors your club.")
    conn.execute(
        """INSERT INTO sponsorships (club_id, sponsor, annual_value, start_season, end_season,
                                     bonus_condition, bonus_amount) VALUES (?,?,?,?,?,?,?)""",
        (club_id, offer["sponsor"], offer["annual_value"], season, season + offer["years"] - 1,
         offer["bonus_condition"], offer["bonus_amount"]))
    conn.commit()


def end_sponsorship(conn, sponsorship_id: int) -> None:
    conn.execute("UPDATE sponsorships SET active=0 WHERE id=?", (sponsorship_id,))
    conn.commit()
