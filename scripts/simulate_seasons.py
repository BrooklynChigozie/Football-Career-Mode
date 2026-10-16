"""Headless balance run: simulate N seasons and print health metrics (plan section 9 checklist)."""
import shutil
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import development, world as W  # noqa: E402
from services import catalog, database  # noqa: E402


def make_world(seed=20260801, club_id=None):
    tmp = Path(tempfile.mkdtemp())
    tpl = tmp / "t.db"
    catalog.ensure_template(tpl)
    g = tmp / "g.db"
    shutil.copy(tpl, g)
    conn = database.connect(g)
    database.migrate(conn)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('season','1')")
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('seed',?)", (str(seed),))
    conn.commit()
    return W.World(conn, club_id)


def main(seasons=7, seed=20260801):
    w = make_world(seed, 21)
    c = w.conn
    for s in range(1, seasons + 1):
        t0 = time.time()
        w.advance_season()
        dt = time.time() - t0
        fx = c.execute("SELECT home_goals h, away_goals a FROM fixtures WHERE season=? AND played=1 AND stage LIKE 'Matchday%'", (s,)).fetchall()
        n = len(fx)
        goals = sum(r["h"] + r["a"] for r in fx) / n
        hw = sum(r["h"] > r["a"] for r in fx) / n
        dr = sum(r["h"] == r["a"] for r in fx) / n
        ovr = [p.overall for pl in w._players.values() for p in pl]
        sizes = [len(pl) for pl in w._players.values()]
        bal = [r[0] for r in c.execute("SELECT balance FROM clubs")]
        wages = c.execute("SELECT AVG(wage) FROM contracts").fetchone()[0]
        hist = w.history(s)
        # strength vs finish correlation: reputation rank vs position
        print(f"S{s}: {dt:4.1f}s goals/g {goals:.2f} home {hw:.0%} draw {dr:.0%} | ovr mean {st.mean(ovr):.1f} max {max(ovr)} | "
              f"squad {min(sizes)}-{max(sizes)} | bal min {min(bal)/1e6:.0f}m med {st.median(bal)/1e6:.0f}m max {max(bal)/1e6:.0f}m | "
              f"avg wage {wages/1e3:.0f}k | user pos {hist.get('user_position')}")
    print("final state:", w.state())


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
