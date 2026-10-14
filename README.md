# Engine guide (Brooklyn's side)

Everything lives in `engine/` and has **no UI or database imports**. The UI and Prosper's services only talk to `World`.

## Quick start
```python
from engine.sample_data import make_sample_world      # 96 clubs, generated players
world = make_sample_world(seed=1, user_club="Arsenal")
while not world.finished:
    while world.phase == "season":
        world.advance_day()                            # 1 call = 1 calendar week
    # offseason: transfers, contracts, lineup...
    if not world.finished:
        world.start_next_season()
```
Headless checks: `python run_seven_seasons.py` (balance) and `pytest` (tests).

## Files
| File | Purpose |
|---|---|
| `models.py` | Player, Club, Fixture, MatchResult... (shared contract with Prosper) |
| `match_sim.py` | Fast + detailed match models, extra time, penalties |
| `competitions.py` | League, KnockoutCup, ChampionsLeague (32 teams, 8 groups, two-leg knockouts) |
| `calendar.py` | 40-week season: league weeks 1-38, CL weeks, cup rounds, winter window weeks 18-22 |
| `transfers.py` | Valuation, user buy/sell, offers inbox, AI transfer rounds |
| `development.py` | Aging, progression, retirement, contract expiry, regens |
| `ai.py` | AI formation choice |
| `finance_hooks.py` | **Interface to Prosper's finance** + a placeholder `SimpleFinance` |
| `world.py` | The `World` class (all UI-facing methods) |
| `sample_data.py` / `loader.py` | Fake data for development / build a World from DB rows |

## World API for UI screens
**Time:** `advance_day()`, `advance_to_next_user_match()`, `advance_season()`, `start_next_season()`
**State:** `phase` ("season" | "offseason" | "finished"), `week`, `season_label`, `can_transfer`, `finished`
**Reading:** `get_squad(club_id)`, `get_table("league:<League>")`, `get_table("cl")` (groups), `get_fixtures(club_id)`, `get_top_scorers(league, n)`, `get_top_assists`, `get_cup_status(league)`, `get_user_summary()`, `get_news(n)`, `get_history()`, `get_competitions()`
**Squad:** `set_formation(name)`, `set_lineup(ids)`, `get_lineup()`, `list_player(id)`, `renew_contract(id, wage, years)`, `release_player(id)`
**Transfers:** `search_players(position, min_overall, max_age, max_price, league)`, `buy_player(id, fee, wage, years)` -> (ok, message), `offers` (inbox), `accept_offer(id)`, `reject_offer(id)`
**Match reports:** every `Fixture.result.events` holds goals, assists, cards, injuries (also for AI matches).

Run `advance_day()` in a worker thread (QThread) so the window never freezes. A whole season takes about 0.5 seconds, so this is mostly for the progress bar.

## For Prosper
1. **Model changes** (add these columns): `Player.potential, wage, contract_until, suspended_matches, listed, career_apps/goals/assists`; `Club.budget, custom_lineup`. Money is in millions, wages are per year.
2. **Finance:** subclass `FinanceHooks` (see `finance_hooks.py`) and call `world.attach_finance(ProsperFinance())`. The engine calls `available_budget`, `record_transfer`, `record_match` (matchday income) and `end_of_season` (prize money, sponsors, wages). The default `SimpleFinance` keeps AI clubs healthy over 7 seasons; keep that behaviour for AI clubs when you replace it.
3. **Saves:** `world.save_bytes()` returns compressed bytes for a BLOB column; `World.load_bytes(data)` restores it. The finance object is not saved, so re-attach it after loading. Only load saves your own game created (pickle).
4. **Real data:** `world_from_records(club_rows, player_rows, user_club_id, seed=...)` builds a World. Club leagues should be named "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1" so the Champions League spots (7/7/6/6/6) and cup names apply; other names fall back to an even split.

## Known simplifications (candidates for polish if time allows)
No in-match substitutions or tactics sliders; red cards and 5-yellow bans are simple; cup draws are random; no international breaks; AI transfers are need-based, not scout-based.
