"""Player development, ageing, valuation and regens. Pure Python."""
import random

from engine import attributes
from engine.names import NAMES

TARGET_SQUAD = {"GK": 3, "CB": 4, "LB": 2, "RB": 2, "CDM": 2, "CM": 3, "CAM": 1, "LW": 2, "RW": 2, "ST": 3}


def market_value(overall: int, potential: int, age: int) -> float:
    base = 20_000 * 2.718281828 ** ((overall - 40) * 0.17)
    youth = 1 + max(0, potential - overall) * 0.025 * max(0, 25 - age) / 5
    ageing = 1.0 if age <= 29 else max(0.25, 1 - (age - 29) * 0.13)
    return round(min(base * youth * ageing, 180_000_000.0), -3)


def wage_for(value: float, overall: int) -> float:
    return round(max(120_000.0, value * 0.09 + overall * 3_000.0), -3)


def yearly_change(age: int, overall: int, potential: int, rng: random.Random) -> int:
    if age <= 21:
        mean = 2.6 + 0.12 * (potential - overall)
    elif age <= 25:
        mean = 1.0 + 0.10 * (potential - overall)
    elif age <= 29:
        mean = 0.1
    elif age <= 32:
        mean = -1.0
    else:
        mean = -2.3
    d = round(rng.gauss(mean, 1.6))
    if overall + d > potential + 1:
        d = potential - overall
    return max(-6, min(7, d))


def develop(p, rng: random.Random) -> None:
    """Age a player one year: overall and the six attributes drift together."""
    d = yearly_change(p.age, p.overall, p.potential, rng)
    p.age += 1
    p.overall = max(35, min(94, p.overall + d))
    p.potential = max(p.overall, p.potential - (1 if p.age > 24 else 0))
    for a in attributes.ATTRS:
        shift = d + (-1 if (a == "pace" and p.age > 29) else 0) + rng.choice((-1, 0, 0, 1))
        setattr(p, a, max(20, min(97, getattr(p, a) + shift)))
    p.value = market_value(p.overall, p.potential, p.age)


def retires(age: int, overall: int, rng: random.Random) -> bool:
    if age < 34:
        return False
    return rng.random() < min(0.95, 0.2 + (age - 34) * 0.22 + (0.1 if overall < 70 else 0))


def new_player(position: str, rep: int, rng: random.Random, nationality: str | None = None) -> dict:
    """A youth/regen: young, rating scaled by the club's reputation."""
    nat = nationality or rng.choice(list(NAMES))
    first, last = rng.choice(NAMES[nat][0]), rng.choice(NAMES[nat][1])
    overall = max(42, min(78, round(rng.gauss(46 + rep * 0.22, 4))))
    age = rng.randint(17, 21)
    potential = min(92, overall + rng.randint(4, 20))
    attrs = attributes.derive(position, overall, rng)
    return {"name": f"{first} {last}", "age": age, "nationality": nat, "position": position, "overall": overall,
            "potential": potential, "value": market_value(overall, potential, age), **attrs}
