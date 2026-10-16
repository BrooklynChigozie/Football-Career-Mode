import pytest

from services import catalog, database, finance, gamedata, lineup


@pytest.fixture(scope="module")
def game(tmp_path_factory):
    path = catalog.ensure_template(tmp_path_factory.mktemp("g") / "t.db")
    conn = database.connect(path)
    yield conn
    conn.close()


def test_sample_data_shape(game):
    leagues = {r["name"]: r["num_clubs"] for r in gamedata.list_leagues(game)}
    assert sorted(leagues.values()) == [18, 18, 20, 20, 20] and sum(leagues.values()) == 96
    for club in gamedata.list_clubs(game):
        squad = gamedata.get_squad(game, club.id)
        assert len(squad) == 24 and sum(p.position == "GK" for p in squad) == 3
        assert club.stadium_capacity >= 12000 and club.balance > 0


def test_lineup_fills_every_formation(game):
    squad = gamedata.get_squad(game, gamedata.list_clubs(game)[0].id)
    for name in lineup.FORMATIONS:
        xi = lineup.best_xi(squad, name)
        assert len(xi) == 11 and len({p.id for p in xi}) == 11
        assigned = lineup.assign(xi, name)
        assert all(p is not None for _, p in assigned)
        assert [p.position for s, p in assigned if s.label == "GK"] == ["GK"]


def test_finance_summary_adds_up_and_is_sane(game):
    ratios = []
    for club in gamedata.list_clubs(game):
        s = finance.get_summary(club.id, 1, game)
        assert s.income == pytest.approx(sum(s.income_breakdown.values()))
        assert s.expenses == pytest.approx(sum(s.expense_breakdown.values()))
        ratios.append(s.wage_bill / s.income)
    # world health check: no club starts with an absurd wage-to-revenue ratio
    assert max(ratios) < 1.2 and sum(ratios) / len(ratios) < 0.9


def test_sponsor_rules(tmp_path):
    path = catalog.ensure_template(tmp_path / "t.db")
    conn = database.connect(path)
    cid = gamedata.list_clubs(conn)[0].id
    offers = finance.offers(conn, cid, 1)
    assert [o["tier"] for o in offers] == ["Bronze", "Silver", "Gold"]
    assert offers[0]["annual_value"] < offers[1]["annual_value"] < offers[2]["annual_value"]
    finance.accept_offer(conn, cid, 1, offers[0])
    with pytest.raises(finance.SponsorError):
        finance.accept_offer(conn, cid, 1, offers[0])        # same sponsor twice
    finance.accept_offer(conn, cid, 1, offers[1])
    finance.accept_offer(conn, cid, 1, offers[2])
    with pytest.raises(finance.SponsorError):
        finance.accept_offer(conn, cid, 1, dict(offers[0], sponsor="Another Co"))   # max 3
    sp = finance.active_sponsorships(conn, cid, 1)
    finance.end_sponsorship(conn, sp[0].id)
    assert len(finance.active_sponsorships(conn, cid, 1)) == 2


def test_booked_items_move_balance(tmp_path):
    conn = database.connect(catalog.ensure_template(tmp_path / "t.db"))
    cid = gamedata.list_clubs(conn)[0].id
    before = gamedata.get_club(conn, cid).balance
    finance.book(conn, cid, 1, "prize money", 5_000_000)
    finance.book(conn, cid, 1, "transfer fees", -2_000_000)
    assert gamedata.get_club(conn, cid).balance == before + 3_000_000
    s = finance.get_summary(cid, 1, conn)
    assert s.income_breakdown["prize money"] == 5_000_000 and s.expense_breakdown["transfer fees"] == 2_000_000
