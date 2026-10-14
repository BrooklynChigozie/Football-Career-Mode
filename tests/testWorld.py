import random
from collections import Counter

import pytest

from engine.loader import world_from_records
from engine.models import map_position
from engine.sample_data import make_sample_world
from engine.world import World


@pytest.fixture(scope="module")
def season_world():
    w = make_sample_world(seed=3, user_club="Arsenal")
    w.advance_season()
    return w


def test_setup_has_96_clubs_and_32_cl_teams():
    w = make_sample_world(seed=1)
    assert len(w.clubs) == 96
    assert len(w.competitions["cl"].groups) == 8
    assert sum(len(g) for g in w.competitions["cl"].groups) == 32


def test_calendar_never_overloads_a_club():
    w = make_sample_world(seed=1)
    w.advance_season()
    per_week = Counter()
    for f in w.fixtures:
        per_week[(f.week, f.home_id)] += 1
        per_week[(f.week, f.away_id)] += 1
    assert max(per_week.values()) <= 2


def test_full_season_produces_all_winners(season_world):
    s = season_world.history[-1]
    assert len(s["champions"]) == 5
    assert len(s["cup_winners"]) == 5 and all(v is not None for v in s["cup_winners"].values())
    assert s["cl_winner"] is not None
    assert season_world.phase == "offseason"
    pl = season_world.get_table("league:Premier League")
    assert len(pl) == 20 and all(r["played"] == 38 for r in pl)
    bl = season_world.get_table("league:Bundesliga")
    assert all(r["played"] == 34 for r in bl)


def test_knockouts_always_have_a_winner(season_world):
    for f in season_world.fixtures:
        if "Final" in f.round_label:
            assert f.result.winner_id in (f.home_id, f.away_id)


def test_top_scorers_and_fixtures_api(season_world):
    assert season_world.get_history()
    assert season_world.get_fixtures(include_upcoming=False)
    assert season_world.get_squad()[0].position == "GK"


def test_save_load_roundtrip_is_deterministic():
    a = make_sample_world(seed=5, user_club="Arsenal")
    for _ in range(10):
        a.advance_day()
    b = World.load_bytes(a.save_bytes())
    for _ in range(10):
        a.advance_day()
        b.advance_day()
    ta, tb = a.get_table("league:La Liga"), b.get_table("league:La Liga")
    assert ta == tb


def test_two_seasons_keep_squads_healthy():
    w = make_sample_world(seed=7, user_club="Arsenal", max_seasons=3)
    w.advance_season()
    w.start_next_season()
    w.advance_season()
    assert all(len(c.players) >= 22 for c in w.clubs.values() if c.id != w.user_club_id)
    assert w.season_year == 2027


def test_game_finishes_after_max_seasons():
    w = make_sample_world(seed=2, max_seasons=2)
    w.advance_season()
    w.start_next_season()
    w.advance_season()
    assert w.finished and w.phase == "finished"
    with pytest.raises(RuntimeError):
        w.start_next_season()


def test_user_transfers_and_offers():
    w = make_sample_world(seed=4, user_club="Arsenal")
    w.advance_season()                       # offseason: window open
    assert w.can_transfer
    club = w.user_club
    club.budget = 1000
    target = w.search_players(position="FWD", min_overall=70, limit=1)[0]
    p = target["player"]
    ok, msg = w.buy_player(p.id, target["ask_price"] * 1.5, target["wage_demand"] * 1.2, 3)
    assert ok, msg
    assert p in club.players and p.club_id == club.id
    sold = club.players[0]
    w.list_player(sold.id)
    for _ in range(30):
        w.refresh_offers()
        if w.offers:
            break
    if w.offers:
        ok, _ = w.accept_offer(w.offers[0].id)
        assert ok


def test_lineup_validation():
    w = make_sample_world(seed=1, user_club="Arsenal")
    squad = w.get_squad()
    ids = [p.id for p in squad if p.position == "GK"][:1] + [p.id for p in squad if p.position != "GK"][:10]
    assert w.set_lineup(ids)[0]
    assert not w.set_lineup(ids[:10])[0]
    w.advance_day()


def test_loader_from_records():
    clubs = [{"id": i, "name": f"C{i}", "league": "L", "reputation": 60} for i in range(1, 9)]
    players, pid = [], 1
    rng = random.Random(1)
    for c in range(1, 9):
        for pos in ["GK"] * 2 + ["CB"] * 6 + ["CM"] * 6 + ["ST"] * 4:
            players.append({"id": pid, "name": f"P{pid}", "age": rng.randint(18, 33), "position": pos,
                            "overall": rng.randint(55, 80), "club_id": c})
            pid += 1
    w = world_from_records(clubs, players, user_club_id=1, seed=1, max_seasons=1)
    assert map_position("CB, LB") == "DEF" and map_position("ST") == "FWD"
    w.advance_season()
    assert w.finished