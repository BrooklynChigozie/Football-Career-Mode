import pytest

from services import auth, database, importer, saves


@pytest.fixture
def app(tmp_path):
    return database.init_app_db(tmp_path / "app.db")


def test_register_and_login(app):
    u = auth.register(app, "prosper_1", "supersecret")
    assert auth.login(app, "PROSPER_1", "supersecret").id == u.id
    stored = app.execute("SELECT password_hash FROM users").fetchone()[0]
    assert b"supersecret" not in stored


def test_auth_validation_and_errors(app):
    with pytest.raises(auth.AuthError):
        auth.register(app, "ab", "supersecret")
    with pytest.raises(auth.AuthError):
        auth.register(app, "valid_name", "short")
    auth.register(app, "valid_name", "supersecret")
    with pytest.raises(auth.AuthError, match="taken"):
        auth.register(app, "VALID_NAME", "supersecret")
    with pytest.raises(auth.AuthError, match="Invalid"):
        auth.login(app, "valid_name", "wrongpass1")
    with pytest.raises(auth.AuthError, match="Invalid"):
        auth.login(app, "nobody", "supersecret")


def test_save_slots_roundtrip(app, tmp_path):
    u = auth.register(app, "player_one", "supersecret")
    d = tmp_path / "saves"
    g = saves.new_game(app, u.id, 1, 7, "Test FC", d)
    g.execute("INSERT INTO leagues (id, name) VALUES (1, 'L')")
    saves.save_game(app, u.id, 1, 2, "2026-08-01", g, d)
    g.close()
    g2 = saves.load_game(app, u.id, 1, d)
    assert g2.execute("SELECT name FROM leagues").fetchone()[0] == "L"
    row = saves.list_saves(app, u.id)[0]
    assert (row["club_name"], row["season"]) == ("Test FC", 2)
    with pytest.raises(saves.SaveError):
        saves.load_game(app, u.id, 2, d)
    saves.delete_save(app, u.id, 1, d)
    assert saves.list_saves(app, u.id) == []


def test_saves_are_per_user(app, tmp_path):
    a = auth.register(app, "user_a", "supersecret")
    b = auth.register(app, "user_b", "supersecret")
    saves.new_game(app, a.id, 1, 1, "A FC", tmp_path)
    assert saves.list_saves(app, b.id) == []


CSV = """short_name,age,nationality_name,player_positions,overall,potential,value_eur,wage_eur,club_name,league_name
A Striker,24,England,"ST, CF",85,88,50000000,150000,Arsenal,English Premier League
A Striker,24,England,"ST, CF",85,88,50000000,150000,Arsenal,English Premier League
No Pos,30,Spain,,70,70,1000000,20000,  Real  Madrid ,Spain Primera Division
Bad Row,0,Spain,GK,70,70,1,1,Real Madrid,Spain Primera Division
Elsewhere,25,Brazil,CM,80,80,1,1,Flamengo,Brazilian Serie A
"""


def test_importer_cleans(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text(CSV)
    g = database.init_game_db(tmp_path / "g.db")
    s = importer.import_players_csv(f, g)
    assert s["players"] == 2 and s["duplicates"] == 1 and s["bad_rows"] == 1
    assert s["skipped_league"] == 1 and s["clubs"] == 2 and s["fixed_positions"] == 1
    assert g.execute("SELECT name FROM clubs WHERE name='Real Madrid'").fetchone()
    assert g.execute("SELECT position FROM players WHERE name='No Pos'").fetchone()[0] == "CM"
    assert g.execute("SELECT wage FROM contracts WHERE wage=7800000").fetchone()
