import shutil

import pytest

from engine import schedule, world as W
from engine.offseason import MarketError
from services import catalog, database


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    return catalog.ensure_template(tmp_path_factory.mktemp("tpl") / "t.db")


def make(template, tmp_path, name="g.db", seed=7, club=21):
    g = tmp_path / name
    shutil.copy(template, g)
    conn = database.connect(g)
    database.migrate(conn)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('season','1')")
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('seed',?)", (str(seed),))
    conn.commit()
    return W.World(conn, club)


def test_full_season_structure(template, tmp_path):
    w = make(template, tmp_path)
    assert w.state().value == "pre_season"
    while w.matchday < schedule.LAST_SLOT:
        w.advance_day()
    assert w.state().value == "season_end"
    for lid in range(1, 6):
        table = w.get_table(w.comp_of("league", lid)["id"])
        n = len(table)
        assert {t.played for t in table} == {2 * (n - 1)}
        assert sum(t.won for t in table) == sum(t.lost for t in table)
    cl = w.comp_of("champions_league")["id"]
    stages = {r[0]: r[1] for r in w.conn.execute("SELECT stage, SUM(played) FROM fixtures WHERE competition_id=? GROUP BY stage", (cl,))}
    assert stages["Final"] == 1 and stages["Round of 16"] == 16 and stages["Quarter-final"] == 8 and stages["Semi-final"] == 4
    assert all(r["winner_id"] for r in w.conn.execute("SELECT * FROM fixtures WHERE stage='Final'"))


def test_deterministic_same_seed(template, tmp_path):
    out = []
    for i in range(2):
        w = make(template, tmp_path, f"d{i}.db", seed=99)
        for _ in range(10):
            w.advance_day()
        out.append([tuple(r) for r in w.conn.execute("SELECT home_goals, away_goals FROM fixtures WHERE played=1 ORDER BY id")])
    assert out[0] == out[1] and out[0]


def test_next_season_and_squad_sizes(template, tmp_path):
    w = make(template, tmp_path)
    w.advance_season()
    assert w.season == 2 and w.matchday == 0 and w.history(1)["user_position"]
    assert all(21 <= len(pl) <= 32 for pl in w._players.values())
    assert w.pending_user_fixtures() == [] or w.pending_user_fixtures()[0].matchday == 1


def test_live_match_commit(template, tmp_path):
    w = make(template, tmp_path)
    fx = w.begin_match_day()
    assert fx and w.state().value == "match_day"
    live = w.start_live_match(fx[0].id)
    live.shout(live.user_side, "Focus")
    live.play_to_end()
    out = w.commit_live_match(fx[0].id, live)
    assert out["home_goals"] == live.score["home"]
    w.advance_day()
    assert w.matchday == 1 and w.state().value == "in_season"


def test_tactics_and_ter(template, tmp_path):
    w = make(template, tmp_path)
    before = w.tactical_report()["ter"]
    w.set_tactics(formation="4-2-3-1" if w.tactics_of(21)["formation"] != "4-2-3-1" else "3-5-2")
    assert w.tactical_report()["understanding"] < w.tactics_of(21)["understanding"] + 1
    assert w.tactical_report()["ter"] != before
    w.set_role(0, "Sweeper Keeper")
    assert w.team_setup(21).role_name(0) == "Sweeper Keeper"
    with pytest.raises(ValueError):
        w.set_training_plan(["nonsense"] * 5)


def test_market(template, tmp_path):
    w = make(template, tmp_path)
    mine = w.get_squad(21)[-1]
    out = w.sell_player(mine.id)
    assert out["fee"] > 0 and mine.id not in {p.id for p in w.get_squad(21)}
    cheap = w.market_search(max_value=out["fee"], min_overall=40, limit=1)[0]
    w.buy_player(cheap.id)
    assert cheap.id in {p.id for p in w.get_squad(21)}
    w.set_meta("matchday", 10)
    with pytest.raises(MarketError):
        w.buy_player(w.market_search(limit=1)[0].id)
