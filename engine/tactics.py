"""Tactics: mentality, pressing, passing style, roles, and the Tactical Effectiveness Rating.

Pure Python. All numbers here are small multipliers so that tactics matter without
overwhelming player quality.
"""
from collections import namedtuple

from engine.attributes import ATTRS

MENTALITIES = ["Defensive", "Cautious", "Balanced", "Positive", "Attacking"]
PRESSING = ["Low", "Medium", "High"]
PASSING = ["Short", "Mixed", "Direct"]

# mentality -> (attack multiplier, defence multiplier)
MENTALITY_FX = {"Defensive": (0.93, 1.06), "Cautious": (0.97, 1.03), "Balanced": (1.0, 1.0),
                "Positive": (1.03, 0.98), "Attacking": (1.06, 0.95)}
# pressing -> (midfield multiplier, fatigue/foul load)
PRESSING_FX = {"Low": (0.985, 0.8), "Medium": (1.0, 1.0), "High": (1.02, 1.3)}
# passing -> (possession points, shot volume multiplier, pass accuracy points)
PASSING_FX = {"Short": (4.0, 0.95, 5.0), "Mixed": (0.0, 1.0, 0.0), "Direct": (-5.0, 1.07, -6.0)}

Role = namedtuple("Role", "name attack defence weights")   # weights follow attributes.ATTRS order
#                                   pace shoot pass drib def phys
ROLES: dict[str, list[Role]] = {
    "GK": [Role("Goalkeeper", 0, 0, (1, 1, 1, 1, 1, 1)), Role("Sweeper Keeper", 0.01, 0.0, (2, 0, 3, 2, 2, 1))],
    "CB": [Role("Central Defender", 0, 0.02, (0, 0, 0, 0, 4, 3)),
           Role("Ball-Playing Defender", 0.01, 0.0, (1, 0, 3, 2, 3, 1)),
           Role("Stopper", -0.005, 0.025, (1, 0, 0, 0, 4, 4))],
    "FB": [Role("Full-Back", 0, 0.01, (2, 0, 2, 1, 3, 2)),
           Role("Attacking Full-Back", 0.02, -0.01, (3, 0, 3, 3, 1, 1)),
           Role("Wing-Back", 0.015, -0.005, (4, 0, 2, 2, 1, 3))],
    "CDM": [Role("Ball-Winning Midfielder", 0, 0.02, (1, 0, 1, 0, 4, 4)),
            Role("Anchor", -0.005, 0.025, (0, 0, 2, 0, 4, 3)),
            Role("Deep-Lying Playmaker", 0.01, 0.0, (0, 0, 4, 2, 2, 1))],
    "CM": [Role("Box-to-Box Midfielder", 0.01, 0.01, (2, 2, 3, 2, 2, 3)),
           Role("Central Midfielder", 0.005, 0.005, (1, 1, 3, 2, 2, 2)),
           Role("Advanced Playmaker", 0.02, -0.01, (1, 2, 4, 3, 0, 1))],
    "CAM": [Role("Advanced Playmaker", 0.02, -0.005, (1, 2, 4, 3, 0, 0)),
            Role("Shadow Striker", 0.025, -0.015, (3, 4, 2, 3, 0, 1)),
            Role("Attacking Midfielder", 0.015, -0.01, (1, 3, 3, 4, 0, 0))],
    "WM": [Role("Wide Midfielder", 0.005, 0.005, (3, 1, 3, 3, 1, 2)),
           Role("Winger", 0.015, -0.01, (4, 1, 2, 4, 0, 1))],
    "W": [Role("Inverted Winger", 0.02, -0.015, (3, 3, 2, 4, 0, 0)), Role("Winger", 0.015, -0.01, (4, 1, 3, 4, 0, 0)),
          Role("Inside Forward", 0.025, -0.02, (3, 4, 1, 4, 0, 1))],
    "ST": [Role("Poacher", 0.025, -0.015, (2, 5, 0, 1, 0, 1)), Role("Target Man", 0.015, -0.005, (0, 3, 1, 0, 0, 5)),
           Role("Complete Forward", 0.02, -0.01, (3, 3, 2, 3, 0, 2)), Role("False Nine", 0.015, -0.01, (1, 2, 4, 4, 0, 0))],
}
_LABEL_GROUP = {"GK": "GK", "CB": "CB", "LB": "FB", "RB": "FB", "CDM": "CDM", "CM": "CM", "CAM": "CAM",
                "LM": "WM", "RM": "WM", "LW": "W", "RW": "W", "ST": "ST"}


def roles_for(slot_label: str) -> list[Role]:
    return ROLES[_LABEL_GROUP.get(slot_label, "CM")]


def default_role(slot_label: str) -> str:
    return roles_for(slot_label)[0].name


def get_role(slot_label: str, name: str | None) -> Role:
    rs = roles_for(slot_label)
    return next((r for r in rs if r.name == name), rs[0])


def role_fit(player, role: Role) -> float:
    """Factor ~0.96-1.03: how well the player's attributes suit the role relative to their overall."""
    if player.position == "GK":
        return 1.0
    total = sum(role.weights) or 1
    score = sum(w * getattr(player, a) for w, a in zip(role.weights, ATTRS)) / total
    return 1 + max(-0.04, min(0.03, (score - player.overall) / 120))


def tactical_effectiveness(understanding: float, avg_overall: float, buy_in: float) -> float:
    """0-100. Combines how well the squad knows the system, player ability and player buy-in."""
    ability = max(0.0, min(100.0, (avg_overall - 50) * 2.2))
    return round(0.40 * understanding + 0.35 * ability + 0.25 * buy_in, 1)


def ter_multiplier(ter: float) -> float:
    return 0.94 + 0.12 * ter / 100


# --- Training blocks (weekly plan = 5 sessions) ---
TrainingBlock = namedtuple("TrainingBlock", "key name load understanding buy_in attr recovery description")
TRAINING_BLOCKS = {b.key: b for b in [
    TrainingBlock("defensive_shape", "Defensive Block Shape", 2, 1.2, 0.0, "defending", 0, "Compactness and shape out of possession."),
    TrainingBlock("final_third", "Final Third Penetration", 3, 1.3, 0.0, "shooting", 0, "Movement and finishing in the box."),
    TrainingBlock("cohesion", "Match Cohesion", 1, 0.8, 1.2, None, 0, "Team bonding and shared understanding."),
    TrainingBlock("pressing", "Pressing Drills", 3, 1.1, 0.0, "physical", 0, "Trigger-based pressing. Tiring."),
    TrainingBlock("transitions", "Counter-Attack Transitions", 3, 1.2, 0.0, "pace", 0, "Fast breaks after winning the ball."),
    TrainingBlock("fitness", "Fitness Conditioning", 4, 0.2, 0.0, "physical", 0, "Builds physical strength. Very tiring."),
    TrainingBlock("set_pieces", "Set Pieces", 1, 0.6, 0.0, "passing", 0, "Corners, free kicks, throw-ins."),
    TrainingBlock("recovery", "Recovery & Rest", 0, 0.0, 0.3, None, 8, "Rest and treatment. Restores fitness."),
]}
DEFAULT_PLAN = ["cohesion", "defensive_shape", "final_third", "set_pieces", "recovery"]
PLAN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def plan_load(plan: list[str]) -> int:
    return sum(TRAINING_BLOCKS[k].load for k in plan if k in TRAINING_BLOCKS)


def injury_risk_multiplier(plan: list[str]) -> float:
    return 1.0 + max(0, plan_load(plan) - 9) * 0.12


def weekly_fitness_change(plan: list[str]) -> float:
    load = plan_load(plan)
    rec = sum(TRAINING_BLOCKS[k].recovery for k in plan if k in TRAINING_BLOCKS)
    return 14.0 - 2.2 * max(0, load - 6) + rec


# --- Shouts (live match) ---
SHOUTS = {
    "Demand More": "Push harder: attack +3% for 3 spells, but buy-in risk if the squad is unsettled.",
    "Encourage": "Lift the team: small boost to everything for 3 spells.",
    "Focus": "Concentrate: defence +3% for 3 spells.",
    "Calm Down": "Fewer fouls and cards for 3 spells.",
    "Praise": "Boosts buy-in a little and team spirit.",
}
