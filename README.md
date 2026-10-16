# Football Career Mode

A simulation-only football career mode: sign up, pick a club from the top five leagues, and manage it for up to 7 seasons. Built with Python, PySide6 and SQLite.

## Run it

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Tests: `python -m pytest`

## Data

The game needs a player dataset. By default it uses `data/sample_players.csv` (96 real club names, invented players),
made by `scripts/generate_sample_data.py`. To use real data, put a Kaggle FIFA-style CSV at `data/kaggle/players.csv`,
delete `userdata/template.db`, and start the game; it is imported once (`services/importer.py`).

## Layout

| Folder | Owner | What |
|---|---|---|
| `engine/` | Brooklyn | Simulation and world (currently stubs in `engine/world.py`) plus shared `models.py` |
| `services/` | Prosper | Database, auth, save slots, importer, finance and sponsors, lineup logic |
| `ui/` | Prosper | Theme (`theme.qss`), shell, components and screens |
| `docs/API_CONTRACT.md` | Both | Functions the two sides call |

The engine never imports the UI; the UI only calls the engine and services.

## Screens (Prosper)

Login and sign-up, career select (5 save slots, club picker), dashboard, team (formation, lineup, pitch view),
finances and sponsors (with chart), calendar, competitions, settings. Calendar and competitions show placeholder
data until the real engine replaces the stubs. Transfers and Statistics are waiting on the engine.

## Advanced features
Tactics board (drag and drop, roles, familiarity, pressing/passing arrows, Tactical Effectiveness Rating), weekly Training matrix,
live Match Day hub (momentum bar, xG chart, shouts, subs), Scouting & Transfers with radar charts, domestic cups and a
Champions League. Run `python scripts/simulate_seasons.py` for a headless 7-season balance check.
