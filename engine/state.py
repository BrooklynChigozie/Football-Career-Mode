"""Game states and which actions each state allows. Pure Python."""
from enum import Enum


class GameState(str, Enum):
    PRE_SEASON = "pre_season"      # before the first matchday: set tactics, training, make transfers
    IN_SEASON = "in_season"        # between matchdays
    MATCH_DAY = "match_day"        # a live match is in progress
    SEASON_END = "season_end"      # all fixtures played; review the season, then start the next
    CAREER_OVER = "career_over"    # seven seasons completed

    @property
    def label(self) -> str:
        return LABELS[self]


LABELS = {
    GameState.PRE_SEASON: "Pre-season",
    GameState.IN_SEASON: "In season",
    GameState.MATCH_DAY: "Match day",
    GameState.SEASON_END: "Season review",
    GameState.CAREER_OVER: "Career complete",
}

# actions: tactics, training, transfers, play (advance / start match), end_season
ALLOWED = {
    GameState.PRE_SEASON: {"tactics", "training", "transfers", "play"},
    GameState.IN_SEASON: {"tactics", "training", "transfers", "play"},
    GameState.MATCH_DAY: {"tactics"},
    GameState.SEASON_END: {"end_season"},
    GameState.CAREER_OVER: set(),
}


def can(state: GameState, action: str) -> bool:
    return action in ALLOWED[state]
