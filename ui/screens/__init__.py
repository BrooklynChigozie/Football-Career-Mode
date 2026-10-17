"""Screens are imported on demand so the older screens can't stop the app starting."""
import importlib

_LAZY = {
    "ChampionsLeagueScreen": "champions_league", "CupScreen": "cup", "LeagueTableScreen": "league_table",
    "LineupScreen": "lineup", "MatchDayScreen": "match_day", "NewsScreen": "news",
    "SeasonReviewScreen": "season_review", "TransfersScreen": "transfers",
}
_ORDER = ["MatchDayScreen", "LeagueTableScreen", "CupScreen", "ChampionsLeagueScreen", "LineupScreen",
          "TransfersScreen", "NewsScreen", "SeasonReviewScreen"]


def __getattr__(name):
    if name in _LAZY:
        return getattr(importlib.import_module(f".{_LAZY[name]}", __name__), name)
    if name == "ENGINE_SCREENS":
        return [__getattr__(n) for n in _ORDER]
    raise AttributeError(name)
