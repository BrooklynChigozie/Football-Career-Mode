"""Fixture generation: round-robin leagues, cup and Champions League draws. Pure Python."""
import random

LAST_SLOT = 38
CL_GROUP_SLOTS = [3, 6, 9, 12, 15, 18]
CL_KNOCKOUT = [("Round of 16", [23, 26]), ("Quarter-final", [29, 32]), ("Semi-final", [34, 36]), ("Final", [38])]
CUP_ROUNDS = [("Preliminary round", 4), ("Round of 16", 10), ("Quarter-final", 16), ("Semi-final", 21), ("Final", 28)]
CUP_FIELD = 16                       # clubs left after the preliminary round


def round_robin(ids: list[int], rng: random.Random) -> list[list[tuple[int, int]]]:
    """Double round-robin by the circle method. Returns rounds of (home, away) pairs."""
    teams = list(ids)
    rng.shuffle(teams)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    first = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is None or b is None:
                continue
            flip = (r % 2 == 0) if i == 0 else (i % 2 == 0)   # alternates venues as teams rotate
            pairs.append((a, b) if flip else (b, a))
        first.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    second = [[(b, a) for a, b in rnd] for rnd in first]
    return first + second


def draw_groups(ids_by_strength: list[int], rng: random.Random, n_groups: int = 8) -> list[list[int]]:
    """Seeded draw: split into pots by strength, one team from each pot per group."""
    pots = [ids_by_strength[i:i + n_groups] for i in range(0, len(ids_by_strength), n_groups)]
    groups = [[] for _ in range(n_groups)]
    for pot in pots:
        pot = list(pot)
        rng.shuffle(pot)
        for g, t in zip(groups, pot):
            g.append(t)
    return groups


def pair_random(ids: list[int], rng: random.Random) -> list[tuple[int, int]]:
    ids = list(ids)
    rng.shuffle(ids)
    return [(ids[i], ids[i + 1]) for i in range(0, len(ids) - 1, 2)]


def pair_winners_runners(winners: list[tuple[int, str]], runners: list[tuple[int, str]],
                         rng: random.Random) -> list[tuple[int, int]]:
    """Round of 16: group winners face runners-up from another group. Entries are (club_id, group)."""
    for _ in range(200):
        r = list(runners)
        rng.shuffle(r)
        if all(w[1] != x[1] for w, x in zip(winners, r)):
            return [(w[0], x[0]) for w, x in zip(winners, r)]
    return [(w[0], x[0]) for w, x in zip(winners, runners)]


def cup_prelim_teams(ids_by_strength_desc: list[int]) -> tuple[list[int], list[int]]:
    """Return (teams playing the preliminary round, teams with a bye). Weakest clubs play first."""
    n = len(ids_by_strength_desc)
    ties = max(0, n - CUP_FIELD)
    if ties == 0:
        return [], list(ids_by_strength_desc)
    playing = ids_by_strength_desc[-2 * ties:]
    return playing, ids_by_strength_desc[:-2 * ties]
