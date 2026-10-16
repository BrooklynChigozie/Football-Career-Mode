"""Shared dataclasses: the contract between engine (Brooklyn) and services/UI (Prosper).

Pure Python, no UI or database imports. Field names match the columns in
services/database.py GAME_SCHEMA. Any change here must be announced to the other lead
before merging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Position(str, Enum):
    GK = "GK"
    CB = "CB"
    LB = "LB"
    RB = "RB"
    CDM = "CDM"
    CM = "CM"
    CAM = "CAM"
    LM = "LM"
    RM = "RM"
    LW = "LW"
    RW = "RW"
    ST = "ST"


class CompetitionKind(str, Enum):
    LEAGUE = "league"
    CUP = "cup"
    CHAMPIONS_LEAGUE = "champions_league"


@dataclass
class Player:
    id: int
    name: str
    age: int
    position: str            # a Position value, kept as str for easy DB round-trips
    overall: int
    potential: int
    nationality: str = ""
    value: float = 0.0       # market value
    club_id: int | None = None
    wage: float = 0.0        # annual
    contract_expires: int = 0  # season number
    morale: int = 70
    fitness: int = 100
    retired: bool = False
    pace: int = 60
    shooting: int = 60
    passing: int = 60
    dribbling: int = 60
    defending: int = 60
    physical: int = 60
    injured_weeks: int = 0
    suspended_games: int = 0
    yellow_cards: int = 0
    form: float = 6.5

    @property
    def available(self) -> bool:
        return not self.retired and self.injured_weeks <= 0 and self.suspended_games <= 0

    @property
    def attrs(self) -> dict:
        return {"pace": self.pace, "shooting": self.shooting, "passing": self.passing,
                "dribbling": self.dribbling, "defending": self.defending, "physical": self.physical}


@dataclass
class Club:
    id: int
    name: str
    league_id: int
    stadium_capacity: int = 30000
    reputation: int = 50
    balance: float = 0.0
    transfer_budget: float = 0.0
    wage_budget: float = 0.0


@dataclass
class Competition:
    id: int
    name: str
    kind: str                # a CompetitionKind value
    league_id: int | None = None


@dataclass
class Fixture:
    id: int
    competition_id: int
    season: int
    matchday: int
    home_id: int
    away_id: int
    home_goals: int | None = None
    away_goals: int | None = None
    played: bool = False
    stage: str = ""
    leg: int = 1
    winner_id: int | None = None
    extra_time: bool = False
    pens_home: int | None = None
    pens_away: int | None = None
    neutral: bool = False


@dataclass
class TableRow:
    club_id: int
    club_name: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    group: str = ""

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


@dataclass
class Sponsorship:
    id: int
    club_id: int
    sponsor: str
    annual_value: float
    start_season: int
    end_season: int
    bonus_condition: str = ""
    bonus_amount: float = 0.0
    active: bool = True


@dataclass
class FinanceSummary:
    club_id: int
    season: int
    income: float
    expenses: float
    balance: float
    transfer_budget: float
    wage_bill: float
    income_breakdown: dict[str, float] = field(default_factory=dict)
    expense_breakdown: dict[str, float] = field(default_factory=dict)
