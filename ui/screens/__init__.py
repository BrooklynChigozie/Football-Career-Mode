from .champions_league import ChampionsLeagueScreen
from .cup import CupScreen
from .league_table import LeagueTableScreen
from .lineup import LineupScreen
from .match_day import MatchDayScreen
from .news import NewsScreen
from .season_review import SeasonReviewScreen
from .transfers import TransfersScreen

ENGINE_SCREENS = [MatchDayScreen, LeagueTableScreen, CupScreen, ChampionsLeagueScreen, LineupScreen,
                  TransfersScreen, NewsScreen, SeasonReviewScreen]