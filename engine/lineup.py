"""Formations and lineup selection. Pure Python (no UI, no DB) so it is easy to test.

A formation is a list of 11 slots (label, accepted positions, x, y) with x/y in 0..1 on a
pitch where y=1 is our own goal line.
"""
from dataclasses import dataclass
from functools import lru_cache

GK, DEF, MID, ATT = {"GK"}, {"CB", "LB", "RB"}, {"CDM", "CM", "CAM", "LM", "RM"}, {"LW", "RW", "ST"}


@dataclass(frozen=True)
class Slot:
    label: str
    accepts: frozenset
    x: float
    y: float


def _s(label, accepts, x, y):
    return Slot(label, frozenset(accepts), x, y)


def _row(labels_accepts, y):
    n = len(labels_accepts)
    return [_s(l, a, (i + 1) / (n + 1), y) for i, (l, a) in enumerate(labels_accepts)]


FORMATIONS: dict[str, list[Slot]] = {
    "4-4-2": [_s("GK", GK, .5, .93)]
    + _row([("LB", {"LB", "CB"}), ("CB", {"CB"}), ("CB", {"CB"}), ("RB", {"RB", "CB"})], .76)
    + _row([("LM", {"LM", "LW", "CM"}), ("CM", {"CM", "CDM"}), ("CM", {"CM", "CAM"}), ("RM", {"RM", "RW", "CM"})], .5)
    + _row([("ST", {"ST"}), ("ST", {"ST", "LW", "RW"})], .22),
    "4-3-3": [_s("GK", GK, .5, .93)]
    + _row([("LB", {"LB", "CB"}), ("CB", {"CB"}), ("CB", {"CB"}), ("RB", {"RB", "CB"})], .76)
    + _row([("CM", {"CM", "CDM"}), ("CDM", {"CDM", "CM"}), ("CM", {"CM", "CAM"})], .52)
    + _row([("LW", {"LW", "ST"}), ("ST", {"ST"}), ("RW", {"RW", "ST"})], .22),
    "4-2-3-1": [_s("GK", GK, .5, .93)]
    + _row([("LB", {"LB", "CB"}), ("CB", {"CB"}), ("CB", {"CB"}), ("RB", {"RB", "CB"})], .78)
    + _row([("CDM", {"CDM", "CM"}), ("CDM", {"CDM", "CM"})], .6)
    + _row([("LW", {"LW", "LM"}), ("CAM", {"CAM", "CM"}), ("RW", {"RW", "RM"})], .4)
    + _row([("ST", {"ST"})], .2),
    "3-5-2": [_s("GK", GK, .5, .93)]
    + _row([("CB", {"CB"}), ("CB", {"CB"}), ("CB", {"CB"})], .76)
    + _row([("LM", {"LM", "LB", "LW"}), ("CM", {"CM", "CDM"}), ("CAM", {"CAM", "CM"}), ("CM", {"CM", "CDM"}),
            ("RM", {"RM", "RB", "RW"})], .5)
    + _row([("ST", {"ST"}), ("ST", {"ST", "LW", "RW"})], .22),
    "5-3-2": [_s("GK", GK, .5, .93)]
    + _row([("LB", {"LB"}), ("CB", {"CB"}), ("CB", {"CB"}), ("CB", {"CB"}), ("RB", {"RB"})], .76)
    + _row([("CM", {"CM", "CDM"}), ("CM", {"CM", "CAM"}), ("CM", {"CM", "CDM"})], .5)
    + _row([("ST", {"ST"}), ("ST", {"ST", "LW", "RW"})], .22),
}
STRATEGIES = ["Balanced", "Attacking", "Defensive", "Counter-attack", "Possession"]

_FALLBACK_GROUP = {"GK": GK, "CB": DEF, "LB": DEF, "RB": DEF, "CDM": MID, "CM": MID, "CAM": MID,
                   "LM": MID | ATT, "RM": MID | ATT, "LW": ATT | MID, "RW": ATT | MID, "ST": ATT}


@lru_cache(maxsize=None)
def _penalty(position: str, slot: Slot) -> float:
    if position in slot.accepts:
        return 0.0
    if position in set().union(*[_FALLBACK_GROUP.get(a, {a}) for a in slot.accepts]):
        return 12.0
    return 40.0 if "GK" not in (position, *slot.accepts) else 1e4


def _fit(player, slot: Slot) -> float:
    """Score of a player in a slot: overall, with penalties for playing out of position."""
    return player.overall - _penalty(player.position, slot)


def assign(players, formation: str) -> list[tuple[Slot, object | None]]:
    """Place the given players (up to 11) into the formation. Scarce slots (GK) are filled first."""
    slots = FORMATIONS[formation]
    pool = list(players)
    order = sorted(range(len(slots)), key=lambda i: (slots[i].label != "GK", len(slots[i].accepts)))
    result: dict[int, object | None] = {}
    for i in order:
        best = max(pool, key=lambda p: _fit(p, slots[i]), default=None)
        if best is not None and _fit(best, slots[i]) > -500:
            result[i] = best
            pool.remove(best)
        else:
            result[i] = None
    return [(slots[i], result.get(i)) for i in range(len(slots))]


def best_xi(squad, formation: str) -> list:
    """Pick the strongest 11 for a formation from the whole squad."""
    slots = FORMATIONS[formation]
    pool = [p for p in squad if p.fitness > 0 and not p.retired]
    chosen = []
    order = sorted(range(len(slots)), key=lambda i: (slots[i].label != "GK", len(slots[i].accepts)))
    for i in order:
        cands = [p for p in pool if p not in chosen]
        if not cands:
            break
        best = max(cands, key=lambda p: _fit(p, slots[i]))
        if _fit(best, slots[i]) > -500:
            chosen.append(best)
    return chosen


def _scarce_first(slots) -> list[int]:
    return sorted(range(len(slots)), key=lambda i: (slots[i].label != "GK", len(slots[i].accepts)))


def complete_xi(formation: str, current: list, pool) -> list:
    """Return 11 players in slot order. Keeps players already in `current` (Player or None per slot) and
    fills the empty slots from `pool` with the best fits, scarce positions first."""
    slots = FORMATIONS[formation]
    xi = list(current) + [None] * (len(slots) - len(current))
    used = {p.id for p in xi if p}
    free = [p for p in pool if p.id not in used]
    for i in _scarce_first(slots):
        if xi[i] is not None or not free:
            continue
        best = max(free, key=lambda p: _fit(p, slots[i]))
        if _fit(best, slots[i]) > -500:
            xi[i] = best
            free.remove(best)
    return xi


def best_formation(pool) -> str:
    """Formation whose best XI has the highest total fit (used for AI clubs)."""
    best, best_score = "4-3-3", -1e9
    for name, slots in FORMATIONS.items():
        xi = complete_xi(name, [], pool)
        score = sum(_fit(p, s) for s, p in zip(slots, xi) if p) - 30 * sum(p is None for p in xi)
        if score > best_score:
            best, best_score = name, score
    return best
