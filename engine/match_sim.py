"""Match simulation.

* simulate_fast     - cheap Poisson model used for AI-vs-AI matches (still records scorers and incidents)
* simulate_detailed - 5-minute-chunk model with goals, assists, cards and injuries (used for the user's matches)
* extra_time / penalty_shootout - used by knockout competitions
All functions take a random.Random so results are reproducible.
"""
import math
import random
from .models import FORMATIONS, Club, MatchEvent, MatchResult

HOME_ADVANTAGE = 1.08
BASE_GOALS = 1.2
STRENGTH_EXP = 2.6
SHOOTER_W = {"FWD": 5.0, "MID": 2.0, "DEF": 0.5, "GK": 0.0}
ASSIST_W = {"FWD": 2.5, "MID": 4.0, "DEF": 1.0, "GK": 0.1}


# ----------------------------------------------------------------------------- lineups & strength
def pick_lineup(club: Club) -> list:
    """Best available XI. Uses the user's custom lineup if it is valid, else picks automatically."""
    if club.custom_lineup:
        by_id = {p.id: p for p in club.players}
        chosen = [by_id.get(i) for i in club.custom_lineup]
        if len(chosen) == 11 and all(p is not None and p.available for p in chosen):
            return chosen
    d, m, f = FORMATIONS[club.formation]
    need = {"GK": 1, "DEF": d, "MID": m, "FWD": f}
    lineup = []
    for pos, count in need.items():
        pool = [p for p in club.players if p.position == pos and p.available]
        pool.sort(key=lambda p: p.overall * (0.7 + 0.3 * p.fitness / 100), reverse=True)
        lineup.extend(pool[:count])
    if len(lineup) < 11:  # injuries / thin squads: fill with best remaining
        rest = [p for p in club.players if p.available and p not in lineup]
        rest.sort(key=lambda p: p.overall, reverse=True)
        lineup.extend(rest[: 11 - len(lineup)])
    return lineup


def _avg(players, default=50.0):
    return sum(p.overall for p in players) / len(players) if players else default


def team_strength(lineup: list) -> dict:
    """Attack / midfield / defence ratings, scaled by fitness and morale."""
    n = max(len(lineup), 1)
    by = lambda pos: [p for p in lineup if p.position == pos]
    form = sum(0.8 + 0.2 * p.fitness / 100 for p in lineup) / n
    mood = 0.95 + 0.1 * (sum(p.morale for p in lineup) / n) / 100
    mult = form * mood
    attack = (_avg(by("FWD")) * 0.6 + _avg(by("MID")) * 0.4) * mult
    middle = _avg(by("MID")) * mult
    defence = (_avg(by("DEF")) * 0.6 + _avg(by("GK")) * 0.25 + _avg(by("MID")) * 0.15) * mult
    return {"attack": attack, "mid": middle, "defence": defence}


# ----------------------------------------------------------------------------- helpers
def _poisson(lam: float, rng: random.Random) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _weighted_pick(players, weights, rng):
    total = sum(weights)
    if total <= 0:
        return players[-1] if players else None
    r = rng.random() * total
    for p, w in zip(players, weights):
        r -= w
        if r <= 0:
            return p
    return players[-1]


def _goal_events(lineup, club_id, n, rng, lo=1, hi=90):
    """Create n goal events (scorer + optional assist) and update player stats."""
    events = []
    if n <= 0 or not lineup:
        return events
    sw = [SHOOTER_W[p.position] * p.overall for p in lineup]
    for _ in range(n):
        scorer = _weighted_pick(lineup, sw, rng)
        assister = None
        if rng.random() < 0.7:
            others = [p for p in lineup if p is not scorer]
            assister = _weighted_pick(others, [ASSIST_W[p.position] * p.overall for p in others], rng)
        scorer.goals += 1
        if assister:
            assister.assists += 1
        events.append(MatchEvent(rng.randint(lo, hi), "goal", club_id, scorer.id,
                                 assister.id if assister else None))
    return events


def _yellow(p, club_id, minute, events):
    p.yellow_cards += 1
    if p.yellow_cards % 5 == 0:
        p.suspended_matches = max(p.suspended_matches, 1)
    events.append(MatchEvent(minute, "yellow", club_id, p.id))


def _red(p, club_id, minute, events, rng):
    p.red_cards += 1
    p.suspended_matches += rng.randint(1, 3)
    events.append(MatchEvent(minute, "red", club_id, p.id))


def _injury(p, club_id, minute, events, rng):
    p.injured_days = rng.randint(7, 60)
    events.append(MatchEvent(minute, "injury", club_id, p.id))


def _incidents(club, lineup, rng, events):
    """Cheap per-match discipline and injuries for the fast model."""
    for _ in range(_poisson(1.6, rng)):
        _yellow(rng.choice(lineup), club.id, rng.randint(1, 90), events)
    if rng.random() < 0.04:
        _red(rng.choice(lineup), club.id, rng.randint(1, 90), events, rng)
    if rng.random() < 0.07:
        _injury(rng.choice(lineup), club.id, rng.randint(1, 90), events, rng)


def _aftermath(club, lineup):
    """Appearances, fatigue and ban countdown after a match."""
    ids = {p.id for p in lineup}
    for p in club.players:
        if p.id in ids:
            p.appearances += 1
            p.career_apps += 1
            p.fitness = max(30.0, p.fitness - 12)
        elif p.suspended_matches > 0:
            p.suspended_matches -= 1


# ----------------------------------------------------------------------------- simulations
def simulate_fast(home: Club, away: Club, rng: random.Random, neutral: bool = False) -> MatchResult:
    """Cheap model for AI-vs-AI matches: Poisson goals from team ratings."""
    hl, al = pick_lineup(home), pick_lineup(away)
    h, a = team_strength(hl), team_strength(al)
    adv = 1.0 if neutral else HOME_ADVANTAGE
    lam_h = min(BASE_GOALS * adv * (h["attack"] / a["defence"]) ** STRENGTH_EXP, 6)
    lam_a = min(BASE_GOALS / adv * (a["attack"] / h["defence"]) ** STRENGTH_EXP, 6)
    hg, ag = _poisson(lam_h, rng), _poisson(lam_a, rng)
    events = _goal_events(hl, home.id, hg, rng) + _goal_events(al, away.id, ag, rng)
    _incidents(home, hl, rng, events)
    _incidents(away, al, rng, events)
    events.sort(key=lambda e: e.minute)
    _aftermath(home, hl)
    _aftermath(away, al)
    return MatchResult(home.id, away.id, hg, ag, events)


def simulate_detailed(home: Club, away: Club, rng: random.Random, neutral: bool = False) -> MatchResult:
    """90 minutes in 5-minute chunks, producing goals, assists, cards and injuries."""
    lineups = {home.id: pick_lineup(home), away.id: pick_lineup(away)}
    strength = {c.id: team_strength(lineups[c.id]) for c in (home, away)}
    penalty = {home.id: 1.0, away.id: 1.0}  # a red card weakens a team
    goals = {home.id: 0, away.id: 0}
    events = []

    for minute in range(5, 95, 5):
        for club, opp in ((home, away), (away, home)):
            s, o = strength[club.id], strength[opp.id]
            pen_s, pen_o = penalty[club.id], penalty[opp.id]
            boost = 1.0 if neutral else (HOME_ADVANTAGE if club is home else 1 / HOME_ADVANTAGE)
            chance_p = min(0.25 * (s["mid"] * pen_s / (o["mid"] * pen_o)) ** 2 * boost, 0.6)
            if rng.random() < chance_p:
                conv = min(0.30 * (s["attack"] * pen_s / (o["defence"] * pen_o)) ** 2, 0.8)
                if rng.random() < conv:
                    goals[club.id] += 1
                    events += _goal_events(lineups[club.id], club.id, 1, rng, minute - 4, minute)
            team = lineups[club.id]
            if rng.random() < 0.04:
                _yellow(rng.choice(team), club.id, minute, events)
            if rng.random() < 0.004:
                _red(rng.choice(team), club.id, minute, events, rng)
                penalty[club.id] *= 0.93
            if rng.random() < 0.006:
                _injury(rng.choice(team), club.id, minute, events, rng)

    _aftermath(home, lineups[home.id])
    _aftermath(away, lineups[away.id])
    return MatchResult(home.id, away.id, goals[home.id], goals[away.id], events)


def extra_time(home: Club, away: Club, rng: random.Random, neutral: bool = False):
    """30 minutes of extra time. Returns (home_goals, away_goals, events)."""
    hl, al = pick_lineup(home), pick_lineup(away)
    h, a = team_strength(hl), team_strength(al)
    adv = 1.0 if neutral else HOME_ADVANTAGE
    third = 30 / 90
    eh = _poisson(min(BASE_GOALS * adv * (h["attack"] / a["defence"]) ** STRENGTH_EXP, 6) * third, rng)
    ea = _poisson(min(BASE_GOALS / adv * (a["attack"] / h["defence"]) ** STRENGTH_EXP, 6) * third, rng)
    events = _goal_events(hl, home.id, eh, rng, 91, 120) + _goal_events(al, away.id, ea, rng, 91, 120)
    events.sort(key=lambda e: e.minute)
    return eh, ea, events


def penalty_shootout(rng: random.Random, p_score: float = 0.76):
    """Returns (home_pens, away_pens); never level."""
    hp = sum(rng.random() < p_score for _ in range(5))
    ap = sum(rng.random() < p_score for _ in range(5))
    while hp == ap:
        hp += rng.random() < p_score
        ap += rng.random() < p_score
    return hp, ap