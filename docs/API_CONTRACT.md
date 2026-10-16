# API contract (Brooklyn <-> Prosper)

Dataclasses live in `engine/models.py`. Any change must be announced to the other lead before merging.

| Function | Owner | Returns |
|---|---|---|
| `world.advance_day()` | Brooklyn | None, moves one matchday |
| `world.advance_season()` | Brooklyn | None, end-of-season process |
| `world.get_clubs(league_id=None)` | Brooklyn | `list[Club]` (added for club selection) |
| `world.get_squad(club_id)` | Brooklyn | `list[Player]` |
| `world.get_table(competition_id)` | Brooklyn | `list[TableRow]`, best first |
| `world.get_fixtures(club_id)` | Brooklyn | `list[Fixture]`, past and upcoming |
| `finance.get_summary(club_id, season=1)` | Prosper | `FinanceSummary` |
| `auth.register(conn, username, password)` / `auth.login(...)` | Prosper | `User`; raises `AuthError` |
| `saves.new_game / save_game / load_game / list_saves / delete_save` | Prosper | see `services/saves.py` |

## Differences from the original plan (please confirm)
1. `auth` and `saves` functions take the app DB connection (and `user_id`) explicitly, so they are testable without globals. The UI holds the current user.
2. `saves.save_game` also needs `season`, `game_date` and the live game connection.
3. `world.get_clubs()` is new: club selection needs it.
4. The world functions currently take no game connection. Open question: does the engine keep its own state in memory and the save layer snapshot it, or does it read/write the game DB directly? The schema in `services/database.py` assumes the game DB is the source of truth.

Stubs in `engine/world.py` and `services/finance.py` return fake data until the real implementations replace them.

## Update: real engine (v2)

`engine/world.py` now holds a real `World` class. The UI calls `world.bind(conn, user_club_id)` when a save is opened
(`GameContext._enter`); the original module-level functions (`advance_day`, `advance_season`, `get_clubs`, `get_squad`,
`get_table`, `get_fixtures`) keep their signatures and fall back to fake data when nothing is bound.

New on `World` (used via `ctx.engine`): `state()` (PRE_SEASON / IN_SEASON / MATCH_DAY / SEASON_END / CAREER_OVER),
`pending_user_fixtures`, `begin_match_day`, `start_live_match`, `commit_live_match`, `tactics_of`, `set_tactics`, `set_xi`,
`set_role`, `set_training_plan`, `tactical_report` (Tactical Effectiveness Rating), `market_search`, `buy_player`,
`sell_player`, `window_open`, `cup_rounds`, `history`, plus `engine/match.py` (`LiveMatch`), `engine/tactics.py`,
`engine/development.py`, `engine/offseason.py`. The engine owns `season` and `matchday` in the `meta` table; the UI only reads them.
Schema version 2 adds `club_state`, `familiarity`, `player_stats`, `season_history`, `news` and new `players`/`fixtures` columns.
