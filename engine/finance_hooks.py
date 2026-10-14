"""The engine's contract with the finance system (Prosper's side).

The engine never does money maths itself; it calls these hooks. SimpleFinance is a working placeholder
so the engine runs on its own. Prosper's real finance class should subclass FinanceHooks and be passed
to World(..., finance=ProsperFinance()) or attached with world.attach_finance(...).
"""
import math


def club_revenue(reputation: float) -> float:
    """Rough yearly revenue in millions for a club of this reputation."""
    return 8 + 24 * math.exp((reputation - 60) / 14)


class FinanceHooks:
    def available_budget(self, club) -> float:
        """How much the club can spend on transfer fees right now."""
        return club.budget

    def record_transfer(self, world, buyer, seller, fee, wage):
        """Called for every completed transfer. buyer/seller may be None (free agent / released)."""
        if buyer is not None:
            buyer.budget -= fee
        if seller is not None:
            seller.budget += fee

    def record_match(self, world, fixture):
        """Called for every match played (matchday income, attendance...)."""

    def end_of_season(self, world, summary):
        """Called once at the end of each season (prize money, sponsorship payouts, wages...).
        summary = {'league_positions': {club_id: pos}, 'champions': {...}, 'cup_winners': {...},
                   'cl_winner': club_id | None, 'season': year}"""


class SimpleFinance(FinanceHooks):
    """Placeholder economy: yearly revenue by reputation + prize money - wages - running costs."""

    def end_of_season(self, world, summary):
        sizes = {}
        for c in world.clubs.values():
            sizes[c.league] = sizes.get(c.league, 0) + 1
        for club in world.clubs.values():
            rev = club_revenue(club.reputation)
            pos = summary["league_positions"].get(club.id, sizes[club.league])
            n = max(sizes[club.league] - 1, 1)
            prize = rev * 0.15 * (1 - (pos - 1) / n)
            if summary.get("cl_winner") == club.id:
                prize += rev * 0.25
            wages = sum(p.wage for p in club.players)
            net = rev + prize - wages - 0.25 * rev
            club.budget = max(0.0, min(club.budget + net, rev * 1.5))