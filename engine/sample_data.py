"""Sample world: real club names, generated players. Prosper's CSV importer replaces this with real data."""
import random
from .finance_hooks import club_revenue
from .models import Club, Player
from .names import random_name
from .transfers import estimate_wage, market_value
from .world import World

LEAGUES = {
    "Premier League": ["Manchester City", "Arsenal", "Liverpool", "Chelsea", "Manchester United", "Tottenham Hotspur",
                       "Newcastle United", "Aston Villa", "Brighton & Hove Albion", "West Ham United",
                       "Crystal Palace", "Fulham", "Brentford", "Everton", "Nottingham Forest",
                       "Wolverhampton Wanderers", "Bournemouth", "Leeds United", "Sunderland", "Burnley"],
    "La Liga": ["Real Madrid", "FC Barcelona", "Atlético Madrid", "Athletic Club", "Real Sociedad", "Villarreal",
                "Real Betis", "Sevilla", "Valencia", "Girona", "Celta Vigo", "Osasuna", "Getafe",
                "Rayo Vallecano", "Mallorca", "Espanyol", "Alavés", "Elche", "Levante", "Real Oviedo"],
    "Serie A": ["Inter", "Napoli", "AC Milan", "Juventus", "Atalanta", "Roma", "Lazio", "Fiorentina", "Bologna",
                "Torino", "Udinese", "Genoa", "Cagliari", "Como", "Parma", "Sassuolo", "Lecce", "Hellas Verona",
                "Cremonese", "Pisa"],
    "Bundesliga": ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig", "Eintracht Frankfurt",
                   "VfB Stuttgart", "SC Freiburg", "Borussia Mönchengladbach", "VfL Wolfsburg", "Werder Bremen",
                   "Mainz 05", "Union Berlin", "FC Augsburg", "Hoffenheim", "Heidenheim", "St. Pauli", "FC Köln",
                   "Hamburger SV"],
    "Ligue 1": ["Paris Saint-Germain", "Marseille", "Monaco", "Lille", "Lyon", "Nice", "Lens", "Rennes",
                "Strasbourg", "Toulouse", "Nantes", "Brest", "Auxerre", "Angers", "Le Havre", "Lorient", "Metz",
                "Paris FC"],
}
LEAGUE_BONUS = {"Premier League": 0, "La Liga": -2, "Serie A": -4, "Bundesliga": -4, "Ligue 1": -9}
LAYOUT = ["GK"] * 3 + ["DEF"] * 8 + ["MID"] * 8 + ["FWD"] * 7
STARTERS = {"GK": 1, "DEF": 4, "MID": 4, "FWD": 3}


def _age(rng):
    return rng.choices(range(17, 37), weights=[2, 3, 5, 6, 7, 8, 8, 8, 8, 7, 7, 6, 5, 4, 3, 2, 2, 1, 1, 1])[0]


def make_players(club, rng, next_id, year):
    avg = 40 + club.reputation * 0.47
    seen = {pos: 0 for pos in STARTERS}
    players = []
    for pos in LAYOUT:
        starter = seen[pos] < STARTERS[pos]
        seen[pos] += 1
        ovr = int(max(38, min(94, rng.gauss(avg if starter else avg - 8, 3.5 if starter else 4))))
        age = _age(rng)
        pot = ovr + rng.randint(0, 14) if age <= 23 else ovr
        p = Player(next_id + len(players), random_name(rng), age, pos, ovr, club.id, pot)
        p.wage = round(estimate_wage(market_value(p)) * rng.uniform(0.9, 1.1), 2)
        p.contract_until = year + rng.randint(0, 4)
        players.append(p)
    return players


def make_sample_world(seed=1, user_club=None, **world_kwargs):
    """user_club: club name or id (default: first club). Extra kwargs go to World()."""
    rng = random.Random(seed)
    year = world_kwargs.get("start_year", 2026)
    clubs, next_id, cid = [], 1, 1
    for league, names in LEAGUES.items():
        for rank, name in enumerate(names):
            rep = int(LEAGUE_BONUS[league] + 90 - rank * 2.4)
            club = Club(cid, name, league, reputation=rep, budget=round(club_revenue(rep) * 0.6, 1))
            club.players = make_players(club, rng, next_id, year)
            next_id += len(club.players)
            clubs.append(club)
            cid += 1
    if user_club is None:
        uid = 1
    elif isinstance(user_club, int):
        uid = user_club
    else:
        uid = next(c.id for c in clubs if c.name == user_club)
    return World(clubs, uid, seed=seed, **world_kwargs)