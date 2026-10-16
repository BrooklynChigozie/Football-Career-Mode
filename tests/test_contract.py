from engine import models, world
from services import finance


def test_world_stubs_have_contract_shape():
    assert all(isinstance(c, models.Club) for c in world.get_clubs())
    squad = world.get_squad(1)
    assert len(squad) >= 11 and all(isinstance(p, models.Player) for p in squad)
    assert sum(p.position == "GK" for p in squad) >= 1
    table = world.get_table(1)
    assert all(isinstance(r, models.TableRow) for r in table)
    assert table[0].points >= table[-1].points
    fx = world.get_fixtures(1)
    assert all(1 in (f.home_id, f.away_id) for f in fx)
    world.advance_day()
    world.advance_season()


def test_finance_stub_adds_up():
    s = finance.get_summary(1)
    assert s.income == sum(s.income_breakdown.values())
    assert s.expenses == sum(s.expense_breakdown.values())
    assert s.wage_bill == s.expense_breakdown["wages"]
