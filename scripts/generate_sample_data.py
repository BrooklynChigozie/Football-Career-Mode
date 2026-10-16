"""Generate data/sample_players.csv: 96 real club names, fictional players.

Stand-in for the Kaggle FIFA-style dataset (same column names), so the game runs without it.
To use real data instead, drop the Kaggle CSV at data/players.csv and rebuild the template.
Run: python scripts/generate_sample_data.py
"""
import csv
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import attributes  # noqa: E402
from engine.names import NAMES  # noqa: E402

LEAGUES = {
    "English Premier League": [
        ("Manchester City", 92), ("Arsenal", 90), ("Liverpool", 90), ("Chelsea", 85), ("Tottenham Hotspur", 84),
        ("Manchester United", 83), ("Newcastle United", 82), ("Aston Villa", 80), ("Brighton", 76), ("West Ham United", 76),
        ("Crystal Palace", 74), ("Fulham", 72), ("Brentford", 72), ("Bournemouth", 72), ("Wolverhampton", 71),
        ("Everton", 71), ("Nottingham Forest", 71), ("Leeds United", 70), ("Burnley", 66), ("Sunderland", 66)],
    "Spain Primera Division": [
        ("Real Madrid", 93), ("FC Barcelona", 91), ("Atletico Madrid", 85), ("Athletic Club", 79), ("Real Sociedad", 78),
        ("Villarreal", 77), ("Real Betis", 77), ("Sevilla", 76), ("Valencia", 74), ("Girona", 73),
        ("Celta Vigo", 71), ("Osasuna", 70), ("Getafe", 69), ("Rayo Vallecano", 69), ("Mallorca", 69),
        ("Alaves", 67), ("Espanyol", 66), ("Elche", 65), ("Levante", 65), ("Real Oviedo", 64)],
    "Italian Serie A": [
        ("Inter", 87), ("Napoli", 85), ("Juventus", 85), ("AC Milan", 84), ("Atalanta", 82),
        ("Roma", 80), ("Lazio", 78), ("Fiorentina", 76), ("Bologna", 75), ("Torino", 72),
        ("Udinese", 70), ("Genoa", 69), ("Como", 68), ("Cagliari", 66), ("Parma", 66),
        ("Sassuolo", 66), ("Lecce", 65), ("Hellas Verona", 65), ("Pisa", 63), ("Cremonese", 63)],
    "German 1. Bundesliga": [
        ("FC Bayern Munich", 91), ("Bayer Leverkusen", 85), ("Borussia Dortmund", 85), ("RB Leipzig", 83),
        ("Eintracht Frankfurt", 77), ("VfB Stuttgart", 77), ("SC Freiburg", 73), ("VfL Wolfsburg", 72),
        ("Hoffenheim", 72), ("Borussia Monchengladbach", 71), ("Werder Bremen", 70), ("Mainz 05", 69),
        ("Union Berlin", 68), ("FC Augsburg", 67), ("Heidenheim", 65), ("FC St. Pauli", 65), ("FC Koln", 65),
        ("Hamburger SV", 65)],
    "French Ligue 1": [
        ("Paris Saint-Germain", 90), ("Marseille", 79), ("Monaco", 78), ("Lyon", 77), ("Lille", 76),
        ("Lens", 74), ("Nice", 73), ("Rennes", 73), ("Strasbourg", 68), ("Brest", 68),
        ("Toulouse", 67), ("Nantes", 66), ("Auxerre", 62), ("Angers", 62), ("Lorient", 62),
        ("Paris FC", 62), ("Le Havre", 61), ("Metz", 61)],
}
HOME = {"English Premier League": "England", "Spain Primera Division": "Spain", "Italian Serie A": "Italy",
        "German 1. Bundesliga": "Germany", "French Ligue 1": "France"}
POSITIONS = ["GK"] * 3 + ["CB"] * 4 + ["LB"] * 2 + ["RB"] * 2 + ["CDM"] * 2 + ["CM"] * 3 + ["CAM"] \
    + ["LW"] * 2 + ["RW"] * 2 + ["ST"] * 3


def value_eur(overall: int, age: int) -> int:
    v = 3e5 * 10 ** ((overall - 50) / 14)
    if age >= 31:
        v *= max(0.2, 1 - 0.15 * (age - 30))
    return int(round(v, -3))


def main(out: Path | None = None) -> Path:
    rng = random.Random(2026)
    out = Path(out or Path(__file__).resolve().parent.parent / "data" / "sample_players.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for league, clubs in LEAGUES.items():
        for club, rep in clubs:
            mean = 45 + 0.38 * rep
            used = set()
            for i, pos in enumerate(POSITIONS):
                nat = HOME[league] if rng.random() < 0.55 else rng.choice(list(NAMES))
                while True:
                    first, last = rng.choice(NAMES[nat][0]), rng.choice(NAMES[nat][1])
                    if (first[0], last) not in used:      # short names must be unique within a club
                        used.add((first[0], last))
                        break
                squad_rank_penalty = 0 if i < 14 else 5      # a few weaker reserves
                overall = max(48, min(92, round(rng.gauss(mean - squad_rank_penalty, 4))))
                age = max(17, min(38, round(rng.gauss(26.5, 4.2))))
                potential = min(95, overall + max(0, round((27 - age) * rng.uniform(0.3, 1.2))))
                value = value_eur(overall, age)
                attrs = attributes.derive(pos, overall, rng)
                rows.append({
                    "short_name": f"{first[0]}. {last}", "age": age, "nationality_name": nat,
                    "player_positions": pos, "overall": overall, "potential": potential,
                    "pace": attrs["pace"], "shooting": attrs["shooting"], "passing": attrs["passing"],
                    "dribbling": attrs["dribbling"], "defending": attrs["defending"], "physic": attrs["physical"],
                    "value_eur": value, "wage_eur": int(round(value * 0.0016, -2)),
                    "club_name": club, "league_name": league,
                    "club_contract_valid_until": 2027 + rng.randint(0, 4)})
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} players for {sum(len(c) for c in LEAGUES.values())} clubs -> {out}")
    return out


if __name__ == "__main__":
    main()
