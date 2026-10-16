"""Fake-data fallbacks used when no game is loaded (tests, demos)."""
from engine.models import Club, Fixture, Player, TableRow

_CLUBS = {1: "Stub United", 2: "Fake City", 3: "Mock Rovers", 4: "Demo Athletic"}
_POSITIONS = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST", "ST", "GK", "CB", "CM"]


def stub_advance_day() -> None:
    """Move the game forward one matchday."""


def stub_advance_season() -> None:
    """Run the end-of-season process (development, retirement, regens, new fixtures)."""


def stub_get_clubs(league_id: int | None = None) -> list[Club]:
    """All clubs, optionally for one league. (Added for the club selection screen.)"""
    return [Club(id=i, name=n, league_id=league_id or 1, balance=50_000_000.0,
                 transfer_budget=20_000_000.0, wage_budget=60_000_000.0)
            for i, n in _CLUBS.items()]


def stub_get_squad(club_id: int) -> list[Player]:
    """The club's players."""
    return [Player(id=club_id * 100 + i, name=f"Player {club_id}-{i + 1}", age=20 + i,
                   position=pos, overall=60 + i, potential=70 + i, club_id=club_id,
                   value=1_000_000.0 * (i + 1), wage=500_000.0 + 50_000.0 * i,
                   contract_expires=2 + i % 4)
            for i, pos in enumerate(_POSITIONS)]


def stub_get_table(competition_id: int) -> list[TableRow]:
    """Standings for a competition, sorted best first."""
    return [TableRow(club_id=i, club_name=n, played=10, won=8 - i, drawn=1, lost=i,
                     goals_for=20 - 2 * i, goals_against=8 + 2 * i)
            for i, n in _CLUBS.items()]


def stub_get_fixtures(club_id: int) -> list[Fixture]:
    """Past and upcoming fixtures for a club."""
    others = [c for c in _CLUBS if c != club_id]
    return [Fixture(id=i + 1, competition_id=1, season=1, matchday=i + 1,
                    home_id=club_id if i % 2 == 0 else o,
                    away_id=o if i % 2 == 0 else club_id,
                    home_goals=2 if i == 0 else None, away_goals=1 if i == 0 else None,
                    played=i == 0)
            for i, o in enumerate(others)]
