"""Player attributes. Pure Python.

Six attributes mirror the Kaggle FIFA-style columns (pace, shooting, passing, dribbling,
defending, physic). Goalkeepers reuse the same six slots with goalkeeping meanings; use
`labels_for(position)` to show the right names.
"""
import random

ATTRS = ["pace", "shooting", "passing", "dribbling", "defending", "physical"]
OUTFIELD_LABELS = ["Pace", "Shooting", "Passing", "Dribbling", "Defending", "Physical"]
GK_LABELS = ["Speed", "Reflexes", "Distribution", "Handling", "Positioning", "Aerial"]

# Offset of each attribute from the overall rating, by position.
PROFILES = {
    "CB": (-8, -22, -8, -14, 6, 4),
    "LB": (4, -14, -3, -3, 0, -2), "RB": (4, -14, -3, -3, 0, -2),
    "CDM": (-6, -12, 2, -6, 4, 4),
    "CM": (-4, -6, 4, 0, -6, -2),
    "CAM": (-2, 0, 6, 6, -18, -8),
    "LM": (6, -3, 1, 6, -18, -6), "RM": (6, -3, 1, 6, -18, -6),
    "LW": (8, 0, 0, 8, -24, -10), "RW": (8, 0, 0, 8, -24, -10),
    "ST": (2, 7, -6, 3, -28, 0),
    "GK": (-20, 0, -4, 0, 0, -2),
}


def labels_for(position: str) -> list[str]:
    return GK_LABELS if position == "GK" else OUTFIELD_LABELS


def derive(position: str, overall: int, rng: random.Random) -> dict[str, int]:
    prof = PROFILES.get(position, PROFILES["CM"])
    return {a: max(20, min(97, round(overall + off + rng.gauss(0, 4)))) for a, off in zip(ATTRS, prof)}
