"""End-of-season processing and the transfer market, as World mixins."""
from __future__ import annotations

import json

from engine import development, economy, schedule
from engine.models import Player

WINDOW_EARLY = 6
WINDOW_LATE = (19, 22)
MAX_SQUAD = 30
MIN_SQUAD_SELL = 18


class MarketError(Exception):
    pass


class MarketMixin:
    def window_open(self) -> bool:
        m = self.matchday
        return m <= WINDOW_EARLY or WINDOW_LATE[0] <= m <= WINDOW_LATE[1] or m >= schedule.LAST_SLOT

    def _row_to_player(self, pid: int) -> Player | None:
        r = self.conn.execute(self_sql(), (pid,)).fetchone()
        from engine.world import _now_player
        return _now_player(r) if r else None

    def market_search(self, position: str | None = None, max_age: int | None = None, min_overall: int = 0,
                      max_value: float | None = None, free_agents: bool = False, limit: int = 60) -> list[Player]:
        out = []
        if free_agents:
            for r in self.conn.execute(self_sql() + "", ()) if False else self.conn.execute(
                    "SELECT p.*, 0 AS wage, 0 AS expires FROM players p WHERE p.club_id IS NULL AND p.retired=0"):
                from engine.world import _now_player
                out.append(_now_player(r))
        else:
            for cid, plist in self._players.items():
                if cid != self.user_club_id:
                    out += plist
        out = [p for p in out if (not position or p.position == position) and (max_age is None or p.age <= max_age)
               and p.overall >= min_overall and (max_value is None or p.value <= max_value)]
        out.sort(key=lambda p: (-p.overall, p.value))
        return out[:limit]

    def asking_price(self, p: Player) -> float:
        return round(p.value * 1.15, -3) if p.club_id else 0.0

    def buy_player(self, player_id: int) -> dict:
        uc = self.user_club_id
        if not self.window_open():
            raise MarketError("The transfer window is closed (open early season and around matchdays 19–22).")
        p = self._find(player_id)
        if p is None or p.club_id == uc:
            raise MarketError("Player not available.")
        if len(self._players.get(uc, [])) >= MAX_SQUAD:
            raise MarketError(f"Your squad is full ({MAX_SQUAD}).")
        fee = self.asking_price(p)
        club = self.conn.execute("SELECT * FROM clubs WHERE id=?", (uc,)).fetchone()
        if fee > club["transfer_budget"]:
            raise MarketError("That is over your transfer budget.")
        wage = development.wage_for(p.value, p.overall)
        bill = self.conn.execute("SELECT COALESCE(SUM(wage),0) FROM contracts WHERE club_id=?", (uc,)).fetchone()[0]
        if club["wage_budget"] and bill + wage > club["wage_budget"]:
            raise MarketError("That would break your wage budget.")
        self._move(p, uc, fee, wage)
        self.news(f"Signed {p.name} for €{fee / 1e6:.1f}m.", "transfer")
        self.conn.commit()
        return {"fee": fee, "wage": wage}

    def sell_player(self, player_id: int) -> dict:
        uc = self.user_club_id
        if not self.window_open():
            raise MarketError("The transfer window is closed.")
        p = self._find(player_id)
        if p is None or p.club_id != uc:
            raise MarketError("Not your player.")
        if len(self._players.get(uc, [])) <= MIN_SQUAD_SELL:
            raise MarketError(f"You need at least {MIN_SQUAD_SELL} players.")
        fee = round(p.value * 0.9, -3)
        buyers = sorted((c for c in self._clubs.values() if c["id"] != uc and c["balance"] > fee * 1.5),
                        key=lambda c: -c["reputation"])
        if not buyers:
            raise MarketError("No club can afford him right now.")
        buyer = buyers[(player_id + self.matchday) % min(len(buyers), 8)]
        self._move(p, buyer["id"], fee, development.wage_for(p.value, p.overall), from_user=True)
        self.news(f"Sold {p.name} to {buyer['name']} for €{fee / 1e6:.1f}m.", "transfer")
        self.conn.commit()
        return {"fee": fee, "club": buyer["name"]}

    def _find(self, pid: int) -> Player | None:
        for plist in self._players.values():
            for p in plist:
                if p.id == pid:
                    return p
        r = self.conn.execute("SELECT p.*, 0 AS wage, 0 AS expires FROM players p WHERE p.id=? AND p.retired=0", (pid,)).fetchone()
        if r:
            from engine.world import _now_player
            return _now_player(r)
        return None

    def _move(self, p: Player, to_club: int, fee: float, wage: float, from_user: bool = False) -> None:
        old = p.club_id
        if old:
            self._players[old] = [x for x in self._players[old] if x.id != p.id]
            economy.book(self.conn, old, self.season, self.matchday, "transfer_in", fee, f"Sold {p.name}")
        economy.book(self.conn, to_club, self.season, self.matchday, "transfer_out", -fee, f"Bought {p.name}")
        p.club_id, p.wage = to_club, wage
        p.contract_expires = self.season + 3
        self._players.setdefault(to_club, []).append(p)
        self.conn.execute("UPDATE players SET club_id=? WHERE id=?", (to_club, p.id))
        self.conn.execute("INSERT INTO contracts (player_id, club_id, wage, expires_season) VALUES (?,?,?,?) "
                          "ON CONFLICT(player_id) DO UPDATE SET club_id=excluded.club_id, wage=excluded.wage, "
                          "expires_season=excluded.expires_season", (p.id, to_club, wage, self.season + 3))
        self.conn.execute("INSERT INTO transfers (season, player_id, from_club_id, to_club_id, fee) VALUES (?,?,?,?,?)",
                          (self.season, p.id, old, to_club, fee))
        economy.sync_budget(self.conn)
        for cid in (old, to_club):
            if cid:
                self._cs_xi_clear(cid)
        self._clubs = {r["id"]: r for r in self.conn.execute("SELECT * FROM clubs")}
        self._ai_xi = {}

    def _cs_xi_clear(self, cid: int) -> None:
        keep = [x for x in json.loads(self._cs[cid]["xi"]) if x is None or any(
            q.id == x for q in self._players.get(cid, []))]
        self._cs[cid]["xi"] = json.dumps(keep)


def self_sql() -> str:
    from engine.world import PLAYER_SQL
    return PLAYER_SQL + " WHERE p.id=?"


class OffseasonMixin:
    def advance_season(self) -> None:
        """Play out the remaining calendar, then run the end-of-season process and start the next season."""
        if self.season > self.MAX_SEASONS:
            return
        while self.matchday < schedule.LAST_SLOT:
            self.advance_day()
        self._close_season()
        if self.season >= self.MAX_SEASONS:
            self.set_meta("season", self.season + 1)       # CAREER_OVER
            self.conn.commit()
            return
        self._new_season()

    # ----- helpers
    def final_positions(self, season: int | None = None) -> dict[int, list[int]]:
        out = {}
        for lid in {c["league_id"] for c in self._clubs.values()}:
            comp = self.comp_of("league", lid)
            out[lid] = [t.club_id for t in self.get_table(comp["id"], season)]
        return out

    def _knockout_result(self, comp, name):
        rows = self.conn.execute("SELECT * FROM fixtures WHERE competition_id=? AND season=? AND stage=? ORDER BY leg DESC",
                                 (comp["id"], self.season, name)).fetchall()
        if not rows:
            return None
        r = rows[0]
        return r["winner_id"], (r["home_id"] if r["winner_id"] == r["away_id"] else r["away_id"])

    def _close_season(self) -> None:
        s, rng = self.season, self.rng_for("offseason", self.season)
        tables = self.final_positions()
        champs = {lid: order[0] for lid, order in tables.items()}
        history = {"tables": {str(k): v for k, v in tables.items()}, "champions": {str(k): v for k, v in champs.items()}}
        # prizes
        for lid, order in tables.items():
            for pos, cid in enumerate(order, start=1):
                economy.book(self.conn, cid, s, self.matchday, "prize", economy.league_prize(pos, len(order)), "League prize money")
        cl = self.comp_of("champions_league")
        reached = {}
        for stage in ["Group", "Round of 16", "Quarter-final", "Semi-final", "Final"]:
            like = "Group%" if stage == "Group" else stage
            for r in self.conn.execute("SELECT DISTINCT home_id h, away_id a FROM fixtures WHERE competition_id=? AND season=? AND stage LIKE ?",
                                       (cl["id"], s, like)):
                reached[r["h"]] = stage
                reached[r["a"]] = stage
        final = self._knockout_result(cl, "Final")
        if final:
            history["cl_winner"], history["cl_runner_up"] = final
            reached[final[0]] = "Winner"
        for cid, stage in reached.items():
            economy.book(self.conn, cid, s, self.matchday, "prize", economy.CL_PRIZE[stage], f"Champions League: {stage}")
        history["cups"] = {}
        for c in [c for c in self._comps.values() if c["kind"] == "cup"]:
            f = self._knockout_result(c, "Final")
            if f:
                history["cups"][str(c["league_id"])] = f[0]
                economy.book(self.conn, f[0], s, self.matchday, "prize", economy.CUP_PRIZE["Winner"], "Cup winners")
                economy.book(self.conn, f[1], s, self.matchday, "prize", economy.CUP_PRIZE["Final"], "Cup finalist")
        scorer = self.conn.execute(
            "SELECT p.name, ps.goals FROM player_stats ps JOIN players p ON p.id=ps.player_id WHERE ps.season=? "
            "ORDER BY ps.goals DESC LIMIT 1", (s,)).fetchone()
        history["top_scorer"] = [scorer["name"], scorer["goals"]] if scorer else None
        uc = self.user_club_id
        if uc:
            order = tables[self.league_of(uc)]
            history["user_position"] = order.index(uc) + 1
            history["user_cl"] = reached.get(uc)
            self.news(f"Season {s} finished: {self.club_name(uc)} placed {order.index(uc) + 1}.", "season")
            self._sponsor_bonuses(uc, order.index(uc) + 1)
        self.conn.execute("INSERT OR REPLACE INTO season_history (season, data) VALUES (?,?)", (s, json.dumps(history)))
        self.conn.commit()
        self._develop_and_refresh(rng)

    def _sponsor_bonuses(self, uc: int, pos: int) -> None:
        for r in self.conn.execute("SELECT * FROM sponsorships WHERE club_id=? AND active=1 AND bonus_amount>0 AND start_season<=? AND end_season>=?",
                                   (uc, self.season, self.season)).fetchall():
            cond = (r["bonus_condition"] or "").lower()
            top = {"top 4": 4, "top 6": 6, "top 10": 10, "top half": 10}
            for k, n in top.items():
                if k in cond and pos <= n:
                    economy.book(self.conn, uc, self.season, self.matchday, "sponsor_bonus", r["bonus_amount"], f"{r['sponsor']} bonus")
                    break

    def _develop_and_refresh(self, rng) -> None:
        season = self.season
        rows = self.conn.execute("SELECT id FROM players WHERE retired=0").fetchall()
        by_id = {p.id: p for plist in self._players.values() for p in plist}
        free = self.conn.execute("SELECT p.*, 0 AS wage, 0 AS expires FROM players p WHERE p.club_id IS NULL AND p.retired=0").fetchall()
        from engine.world import _now_player
        for r in free:
            by_id[r["id"]] = _now_player(r)
        for pid, p in by_id.items():
            if development.retires(p.age, p.overall, rng):
                p.retired = True
                self.conn.execute("UPDATE players SET retired=1, club_id=NULL WHERE id=?", (pid,))
                self.conn.execute("DELETE FROM contracts WHERE player_id=?", (pid,))
                if p.club_id == self.user_club_id:
                    self.news(f"{p.name} has retired from football.", "retire")
                continue
            development.develop(p, rng)
            p.fitness, p.injured_weeks, p.suspended_games, p.yellow_cards = 100, 0, 0, 0
            p.morale = 70
            self.conn.execute(
                "UPDATE players SET age=?, overall=?, potential=?, value=?, pace=?, shooting=?, passing=?, dribbling=?, "
                "defending=?, physical=?, fitness=100, injured_weeks=0, suspended_games=0, yellow_cards=0, morale=70, form=6.5 WHERE id=?",
                (p.age, p.overall, p.potential, p.value, p.pace, p.shooting, p.passing, p.dribbling, p.defending,
                 p.physical, pid))
            c = self.conn.execute("SELECT * FROM contracts WHERE player_id=?", (pid,)).fetchone()
            if c and c["expires_season"] <= season:
                if p.club_id and (p.overall >= 55 or p.age < 25):          # renew
                    w = development.wage_for(p.value, p.overall)
                    self.conn.execute("UPDATE contracts SET wage=?, expires_season=? WHERE player_id=?", (w, season + 1 + rng.randint(1, 3), pid))
                else:                                                      # released
                    self.conn.execute("UPDATE players SET club_id=NULL WHERE id=?", (pid,))
                    self.conn.execute("DELETE FROM contracts WHERE player_id=?", (pid,))
                    if p.club_id == self.user_club_id:
                        self.news(f"{p.name}'s contract ended and he left the club.", "contract")
        self.conn.commit()

    def _new_season(self) -> None:
        rng = self.rng_for("newseason", self.season)
        self.reload()
        self._ai_transfers(rng)
        self._fill_squads(rng)
        self._wage_control()
        self.set_meta("season", self.season + 1)
        self.set_meta("matchday", 0)
        for cs in self._cs.values():
            cs["xi"] = "[]"
            cs["understanding"] = max(35.0, cs["understanding"] * 0.92)
        self.conn.execute("UPDATE club_state SET xi='[]'")
        self.reload()
        self.season_setup(self.season)
        for cid, cs in self._cs.items():
            cs["buy_in"] = 70.0
        self._flush()
        economy.sync_budget(self.conn)
        self.news(f"Season {self.season} begins.", "season", slot=0)
        self.conn.commit()

    def _ai_transfers(self, rng) -> None:
        uc = self.user_club_id
        clubs = sorted((c for c in self._clubs.values() if c["id"] != uc), key=lambda c: -c["balance"])
        for c in clubs[:max(1, len(clubs) // 4)]:
            sq = self._players.get(c["id"], [])
            if len(sq) >= MAX_SQUAD - 2 or c["balance"] < 30e6:
                continue
            weakest = min(development.TARGET_SQUAD, key=lambda pos: max((p.overall for p in sq if p.position == pos), default=0))
            pool = [p for cid, pl in self._players.items() if cid not in (c["id"], uc) for p in pl
                    if p.position == weakest and p.value * 1.1 < c["balance"] * 0.3
                    and p.overall > max((q.overall for q in sq if q.position == weakest), default=0)
                    and self._clubs[cid]["reputation"] <= c["reputation"] + 5]
            if pool:
                p = max(pool, key=lambda q: q.overall)
                self._move(p, c["id"], round(p.value * 1.1, -3), development.wage_for(p.value, p.overall))
        self.conn.commit()

    def _fill_squads(self, rng) -> None:
        next_id = self.conn.execute("SELECT COALESCE(MAX(id),0) FROM players").fetchone()[0] + 1
        # free agents fill gaps first
        for cid, club in self._clubs.items():
            sq = self._players.get(cid, [])
            counts = {}
            for p in sq:
                counts[p.position] = counts.get(p.position, 0) + 1
            for pos, need in development.TARGET_SQUAD.items():
                for _ in range(max(0, need - counts.get(pos, 0))):
                    d = development.new_player(pos, club["reputation"], rng)
                    wage = development.wage_for(d["value"], d["overall"])
                    self.conn.execute(
                        "INSERT INTO players (id, name, age, nationality, position, overall, potential, value, club_id, "
                        "pace, shooting, passing, dribbling, defending, physical, youth) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                        (next_id, d["name"], d["age"], d["nationality"], pos, d["overall"], d["potential"], d["value"], cid,
                         d["pace"], d["shooting"], d["passing"], d["dribbling"], d["defending"], d["physical"]))
                    self.conn.execute("INSERT INTO contracts (player_id, club_id, wage, expires_season) VALUES (?,?,?,?)",
                                      (next_id, cid, wage, self.season + 3))
                    next_id += 1
        self.conn.commit()
        self.reload()

    def _wage_control(self) -> None:
        for cid, c in self._clubs.items():
            bill = self.conn.execute("SELECT COALESCE(SUM(wage),0) FROM contracts WHERE club_id=?", (cid,)).fetchone()[0]
            self.conn.execute("UPDATE clubs SET wage_budget=? WHERE id=?", (max(c["wage_budget"], bill * 1.1), cid))
