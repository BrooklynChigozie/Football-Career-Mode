"""The world engine: calendar, matches, standings, knockouts, tactics, training, finance flow.

Public contract (see docs/API_CONTRACT.md). Call `bind(conn, user_club_id)` once a game is loaded;
until then the module-level functions fall back to fake data so the UI can be developed without a game.
The engine only uses the stdlib (sqlite3) and never imports the UI or services.
"""
from __future__ import annotations

import json
import random
import sqlite3

from engine import _stubs, economy, lineup, match, schedule, tactics
from engine.offseason import MarketMixin, OffseasonMixin
from engine.models import Club, Fixture, Player, TableRow
from engine.state import GameState

MAX_SEASONS = 7
MIN_SQUAD = 22
GROUP_PREFIX = "Group "
LEAGUE_PREFIX = "Matchday "


def _now_player(r) -> Player:
    return Player(
        id=r["id"], name=r["name"], age=r["age"], position=r["position"], overall=r["overall"],
        potential=r["potential"], nationality=r["nationality"] or "", value=r["value"], club_id=r["club_id"],
        wage=r["wage"] or 0.0, contract_expires=r["expires"] or 0, morale=r["morale"], fitness=r["fitness"],
        retired=bool(r["retired"]), pace=r["pace"], shooting=r["shooting"], passing=r["passing"],
        dribbling=r["dribbling"], defending=r["defending"], physical=r["physical"],
        injured_weeks=r["injured_weeks"], suspended_games=r["suspended_games"], yellow_cards=r["yellow_cards"],
        form=r["form"])


def _fixture(r) -> Fixture:
    return Fixture(id=r["id"], competition_id=r["competition_id"], season=r["season"], matchday=r["matchday"],
                   home_id=r["home_id"], away_id=r["away_id"], home_goals=r["home_goals"], away_goals=r["away_goals"],
                   played=bool(r["played"]), stage=r["stage"], leg=r["leg"], winner_id=r["winner_id"],
                   extra_time=bool(r["extra_time"]), pens_home=r["pens_home"], pens_away=r["pens_away"],
                   neutral=bool(r["neutral"]))


PLAYER_SQL = """SELECT p.*, c.wage AS wage, c.expires_season AS expires
                FROM players p LEFT JOIN contracts c ON c.player_id = p.id"""


class World(OffseasonMixin, MarketMixin):
    MAX_SEASONS = MAX_SEASONS

    def __init__(self, conn: sqlite3.Connection, user_club_id: int | None):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.user_club_id = user_club_id
        if self.meta("seed") is None:
            self.set_meta("seed", 20260801)
        self._players: dict[int, list[Player]] = {}
        self._cs: dict[int, dict] = {}
        self._dirty: set[int] = set()
        self._fam: dict[tuple, float] = {}
        self._ai_xi: dict[int, list] = {}
        self.reload()
        if self.meta("setup_done_season") != self.season:
            self.season_setup(self.season)

    # ------------------------------------------------------------------ meta / basics
    def meta(self, key, default=None):
        r = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_meta(self, key, value) -> None:
        self.conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (key, json.dumps(value)))

    @property
    def season(self) -> int:
        return self.meta("season", 1)

    @property
    def matchday(self) -> int:
        return self.meta("matchday", 0)

    def rng_for(self, *parts) -> random.Random:
        """Deterministic RNG per (seed, purpose): same save + same actions = same results."""
        return random.Random(f"{self.meta('seed')}|" + "|".join(str(p) for p in parts))

    def reload(self) -> None:
        """Reload per-slot caches from the database."""
        rows = self.conn.execute(PLAYER_SQL + " WHERE p.retired=0 AND p.club_id IS NOT NULL").fetchall()
        self._players = {}
        for r in rows:
            self._players.setdefault(r["club_id"], []).append(_now_player(r))
        self._clubs = {r["id"]: r for r in self.conn.execute("SELECT * FROM clubs")}
        self._comps = {r["id"]: r for r in self.conn.execute("SELECT * FROM competitions")}
        self._cs = {r["club_id"]: dict(r) for r in self.conn.execute("SELECT * FROM club_state")}
        self._dirty = set()
        if self.user_club_id is not None:
            self._fam = {(r["player_id"], r["role"]): r["value"] for r in self.conn.execute(
                "SELECT f.* FROM familiarity f JOIN players p ON p.id=f.player_id WHERE p.club_id=?", (self.user_club_id,))}
        else:
            self._fam = {}
        self._ai_xi = {}

    def state(self) -> GameState:
        if self.season > MAX_SEASONS:
            return GameState.CAREER_OVER
        if self.matchday >= schedule.LAST_SLOT:
            return GameState.SEASON_END
        if self.meta("live_match"):
            return GameState.MATCH_DAY
        return GameState.PRE_SEASON if self.matchday == 0 else GameState.IN_SEASON

    def comp_of(self, kind: str, league_id: int | None = None):
        for c in self._comps.values():
            if c["kind"] == kind and (league_id is None or c["league_id"] == league_id):
                return c
        return None

    def league_of(self, club_id: int) -> int:
        return self._clubs[club_id]["league_id"]

    def club_name(self, club_id: int) -> str:
        return self._clubs[club_id]["name"] if club_id in self._clubs else f"Club {club_id}"

    def news(self, text: str, kind: str = "info", slot: int | None = None) -> None:
        self.conn.execute("INSERT INTO news (season, slot, kind, text) VALUES (?,?,?,?)",
                          (self.season, self.matchday if slot is None else slot, kind, text))

    # ------------------------------------------------------------------ season setup
    def _add_fixture(self, comp_id, season, slot, home, away, stage, leg=1, tie=0, neutral=0) -> None:
        self.conn.execute(
            "INSERT INTO fixtures (competition_id, season, matchday, home_id, away_id, stage, leg, tie, neutral) "
            "VALUES (?,?,?,?,?,?,?,?,?)", (comp_id, season, slot, home, away, stage, leg, tie, neutral))

    def season_setup(self, season: int) -> None:
        """Create the league calendar, Champions League groups and first cup round, and default tactics."""
        rng = self.rng_for("setup", season)
        by_league: dict[int, list[int]] = {}
        for c in self._clubs.values():
            by_league.setdefault(c["league_id"], []).append(c["id"])
        for lid, ids in by_league.items():
            comp = self.comp_of("league", lid)
            for md, rnd in enumerate(schedule.round_robin(ids, rng), start=1):
                for h, a in rnd:
                    self._add_fixture(comp["id"], season, md, h, a, f"{LEAGUE_PREFIX}{md}")
            # domestic cup
            cup = self.comp_of("cup", lid)
            ranked = sorted(ids, key=lambda i: -self._clubs[i]["reputation"])
            playing, byes = schedule.cup_prelim_teams(ranked)
            if playing:
                for h, a in schedule.pair_random(playing, rng):
                    self._add_fixture(cup["id"], season, schedule.CUP_ROUNDS[0][1], h, a, schedule.CUP_ROUNDS[0][0])
            else:
                for h, a in schedule.pair_random(byes, rng):
                    self._add_fixture(cup["id"], season, schedule.CUP_ROUNDS[1][1], h, a, schedule.CUP_ROUNDS[1][0])
        # Champions League: top 4 of each league last season + best remaining by reputation
        cl = self.comp_of("champions_league")
        quals = self._cl_qualifiers(season)
        for gi, grp in enumerate(schedule.draw_groups(quals, rng)):
            letter = chr(ord("A") + gi)
            for md, rnd in enumerate(schedule.round_robin(grp, rng)):
                for h, a in rnd:
                    self._add_fixture(cl["id"], season, schedule.CL_GROUP_SLOTS[md], h, a, f"{GROUP_PREFIX}{letter}")
        # club state defaults
        for cid, c in self._clubs.items():
            if cid not in self._cs:
                sq = self._players.get(cid, [])
                fm = lineup.best_formation(sq) if len(sq) >= 11 else "4-3-3"
                self.conn.execute(
                    "INSERT INTO club_state (club_id, formation, understanding, buy_in, training) VALUES (?,?,?,?,?)",
                    (cid, fm, round(52 + c["reputation"] * 0.28, 1), 70.0, json.dumps(tactics.DEFAULT_PLAN)))
        self.set_meta("setup_done_season", season)
        self.set_meta("matchday", 0)
        self.set_meta("live_match", False)
        self.conn.commit()
        self._cs = {r["club_id"]: dict(r) for r in self.conn.execute("SELECT * FROM club_state")}

    def _cl_qualifiers(self, season: int) -> list[int]:
        rep = lambda i: -self._clubs[i]["reputation"]  # noqa: E731
        prev = self.history(season - 1)
        chosen: list[int] = []
        if prev:
            for lid, order in prev["tables"].items():
                chosen += [c for c in order[:4] if c in self._clubs]
        rest = sorted((i for i in self._clubs if i not in chosen), key=rep)
        chosen += rest[:32 - len(chosen)]
        return sorted(chosen, key=rep)[:32]

    # ------------------------------------------------------------------ queries
    def history(self, season: int):
        r = self.conn.execute("SELECT data FROM season_history WHERE season=?", (season,)).fetchone()
        return json.loads(r[0]) if r else None

    def fixtures_for_slot(self, slot: int, season: int | None = None) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM fixtures WHERE season=? AND matchday=? ORDER BY id",
                                 (season or self.season, slot)).fetchall()

    def get_fixtures(self, club_id: int, season: int | None = None) -> list[Fixture]:
        rows = self.conn.execute(
            "SELECT * FROM fixtures WHERE season=? AND (home_id=? OR away_id=?) ORDER BY matchday, id",
            (season or self.season, club_id, club_id)).fetchall()
        return [_fixture(r) for r in rows]

    def pending_user_fixtures(self) -> list[Fixture]:
        """The user's unplayed fixtures in the next slot."""
        if self.user_club_id is None or self.matchday >= schedule.LAST_SLOT:
            return []
        return [_fixture(r) for r in self.fixtures_for_slot(self.matchday + 1)
                if not r["played"] and self.user_club_id in (r["home_id"], r["away_id"])]

    def comp_name(self, comp_id: int) -> str:
        return self._comps[comp_id]["name"]

    def get_squad(self, club_id: int) -> list[Player]:
        return sorted(self._players.get(club_id, []), key=lambda p: -p.overall)

    def get_clubs(self, league_id: int | None = None) -> list[Club]:
        out = []
        for c in self._clubs.values():
            if league_id and c["league_id"] != league_id:
                continue
            r = self.conn.execute("SELECT * FROM clubs WHERE id=?", (c["id"],)).fetchone()
            out.append(Club(r["id"], r["name"], r["league_id"], r["stadium_capacity"], r["reputation"],
                            r["balance"], r["transfer_budget"], r["wage_budget"]))
        return sorted(out, key=lambda c: (-c.reputation, c.name))

    def get_table(self, competition_id: int, season: int | None = None) -> list[TableRow]:
        """Standings for a league, or the group stage of the Champions League (rows carry their group)."""
        season = season or self.season
        comp = self._comps[competition_id]
        rows = self.conn.execute(
            "SELECT * FROM fixtures WHERE competition_id=? AND season=? AND (stage LIKE 'Matchday%' OR stage LIKE 'Group%')",
            (competition_id, season)).fetchall()
        tab: dict[tuple, TableRow] = {}
        for r in rows:
            grp = r["stage"] if r["stage"].startswith(GROUP_PREFIX) else ""
            for cid in (r["home_id"], r["away_id"]):
                tab.setdefault((grp, cid), TableRow(cid, self.club_name(cid)))
            if not r["played"]:
                continue
            for cid, gf, ga in ((r["home_id"], r["home_goals"], r["away_goals"]), (r["away_id"], r["away_goals"], r["home_goals"])):
                t = tab[(grp, cid)]
                t.played += 1
                t.goals_for += gf
                t.goals_against += ga
                if gf > ga:
                    t.won += 1
                elif gf == ga:
                    t.drawn += 1
                else:
                    t.lost += 1
        out = []
        for (grp, _cid), t in tab.items():
            t.group = grp
            out.append(t)
        out.sort(key=lambda t: (t.group, -t.points, -t.goal_difference, -t.goals_for, t.club_name))
        return out

    def cup_rounds(self, competition_id: int, season: int | None = None) -> list[tuple[str, list[Fixture]]]:
        rows = self.conn.execute("SELECT * FROM fixtures WHERE competition_id=? AND season=? ORDER BY matchday, tie, id",
                                 (competition_id, season or self.season)).fetchall()
        rounds: dict[str, list[Fixture]] = {}
        for r in rows:
            if not (r["stage"].startswith(LEAGUE_PREFIX) or r["stage"].startswith(GROUP_PREFIX)):
                rounds.setdefault(r["stage"], []).append(_fixture(r))
        return list(rounds.items())

    # ------------------------------------------------------------------ tactics / lineup
    def tactics_of(self, club_id: int) -> dict:
        cs = self._cs[club_id]
        return {"formation": cs["formation"], "mentality": cs["mentality"], "pressing": cs["pressing"],
                "passing": cs["passing"], "understanding": cs["understanding"], "buy_in": cs["buy_in"],
                "roles": {int(k): v for k, v in json.loads(cs["roles"]).items()},
                "training": json.loads(cs["training"])}

    def _save_cs(self, club_id: int) -> None:
        cs = self._cs[club_id]
        self.conn.execute(
            "UPDATE club_state SET formation=?, mentality=?, pressing=?, passing=?, understanding=?, buy_in=?, "
            "xi=?, roles=?, training=? WHERE club_id=?",
            (cs["formation"], cs["mentality"], cs["pressing"], cs["passing"], cs["understanding"], cs["buy_in"],
             cs["xi"], cs["roles"], cs["training"], club_id))

    def set_tactics(self, club_id: int | None = None, formation=None, mentality=None, pressing=None, passing=None) -> None:
        club_id = club_id or self.user_club_id
        cs = self._cs[club_id]
        if formation and formation != cs["formation"]:
            if formation not in lineup.FORMATIONS:
                raise ValueError("Unknown formation")
            cs["formation"] = formation
            cs["xi"] = "[]"
            cs["roles"] = "{}"
            cs["understanding"] = max(25.0, cs["understanding"] * 0.85)   # learning a new shape costs understanding
        if mentality in tactics.MENTALITY_FX:
            cs["mentality"] = mentality
        if pressing in tactics.PRESSING_FX:
            cs["pressing"] = pressing
        if passing in tactics.PASSING_FX:
            cs["passing"] = passing
        self._save_cs(club_id)
        self.conn.commit()

    def lineup_of(self, club_id: int) -> list[tuple]:
        """[(slot, player or None)] for the current XI, filling unavailable players automatically."""
        setup = self.team_setup(club_id)
        return list(zip(setup.slots, setup.xi))

    def set_xi(self, player_ids: list[int | None], club_id: int | None = None) -> None:
        club_id = club_id or self.user_club_id
        self._cs[club_id]["xi"] = json.dumps(player_ids)
        self._save_cs(club_id)
        self.conn.commit()

    def set_role(self, slot_index: int, role: str, club_id: int | None = None) -> None:
        club_id = club_id or self.user_club_id
        cs = self._cs[club_id]
        roles = json.loads(cs["roles"])
        roles[str(slot_index)] = role
        cs["roles"] = json.dumps(roles)
        self._save_cs(club_id)
        self.conn.commit()

    def auto_assign(self, club_id: int | None = None) -> None:
        club_id = club_id or self.user_club_id
        avail = [p for p in self._players.get(club_id, []) if p.available]
        xi = lineup.complete_xi(self._cs[club_id]["formation"], [], avail)
        self.set_xi([p.id if p else None for p in xi], club_id)

    def set_training_plan(self, plan: list[str]) -> None:
        if len(plan) != len(tactics.PLAN_DAYS) or any(k not in tactics.TRAINING_BLOCKS for k in plan):
            raise ValueError("Training plan needs one valid block per day.")
        self._cs[self.user_club_id]["training"] = json.dumps(plan)
        self._save_cs(self.user_club_id)
        self.conn.commit()

    def familiarity(self, player: Player, role: str, slot_label: str | None = None) -> float:
        key = (player.id, role)
        if key in self._fam:
            return self._fam[key]
        natural = slot_label is None or player.position in lineup.FORMATIONS and True
        return 60.0 if natural and self._natural(player, role) else 35.0

    @staticmethod
    def _natural(player: Player, role: str) -> bool:
        for label, group in tactics._LABEL_GROUP.items():
            if label == player.position and any(r.name == role for r in tactics.ROLES[group]):
                return True
        return False

    def team_setup(self, club_id: int) -> match.TeamSetup:
        cs = self._cs[club_id]
        players = self._players.get(club_id, [])
        avail = [p for p in players if p.available]
        formation = cs["formation"]
        by_id = {p.id: p for p in avail}
        saved = json.loads(cs["xi"])
        if club_id != self.user_club_id and club_id in self._ai_xi and all(
                p is None or p.available for p in self._ai_xi[club_id]):
            xi = self._ai_xi[club_id]
        else:
            current = [by_id.get(pid) if pid else None for pid in saved]
            xi = lineup.complete_xi(formation, current, avail)
            if club_id != self.user_club_id:
                self._ai_xi[club_id] = xi
        used = {p.id for p in xi if p}
        rest = sorted((p for p in avail if p.id not in used), key=lambda p: -p.overall)
        gk = next((p for p in rest if p.position == "GK"), None)
        bench = ([gk] if gk else []) + [p for p in rest if p is not gk][:6]
        roles = {int(k): v for k, v in json.loads(cs["roles"]).items()}
        fam = {}
        if club_id == self.user_club_id:
            for i, (slot, p) in enumerate(zip(lineup.FORMATIONS[formation], xi)):
                if p:
                    role = roles.get(i) or tactics.default_role(slot.label)
                    fam[(p.id, role)] = self.familiarity(p, role)
        plan = json.loads(cs["training"])
        return match.TeamSetup(club_id, self.club_name(club_id), formation, cs["mentality"], cs["pressing"],
                               cs["passing"], cs["understanding"], cs["buy_in"], xi, bench, roles, fam,
                               tactics.injury_risk_multiplier(plan))

    def tactical_report(self, club_id: int | None = None) -> dict:
        club_id = club_id or self.user_club_id
        t = self.team_setup(club_id)
        s = match.compute_strengths(t)
        return {"ter": s.ter, "attack": s.attack, "defence": s.defence, "midfield": s.midfield,
                "understanding": t.understanding, "buy_in": t.buy_in, "ability": t.avg_overall()}

    # ------------------------------------------------------------------ running the calendar
    def _pre_slot_week(self) -> None:
        """Weekly training and recovery for every club, before the matches."""
        rng = self.rng_for("week", self.season, self.matchday)
        for cid, cs in self._cs.items():
            plan = json.loads(cs["training"]) if cid == self.user_club_id else tactics.DEFAULT_PLAN
            fdelta = tactics.weekly_fitness_change(plan)
            for p in self._players.get(cid, []):
                if p.injured_weeks > 0:
                    p.injured_weeks -= 1
                    self._dirty.add(p.id)
                new_fit = max(20, min(100, round(p.fitness + fdelta)))
                if new_fit != p.fitness:
                    p.fitness = new_fit
                    self._dirty.add(p.id)
            gain = sum(tactics.TRAINING_BLOCKS[k].understanding for k in plan)
            cs["understanding"] = max(20.0, min(98.0, cs["understanding"]
                                                + gain * (1 - cs["understanding"] / 125) * (0.6 + 0.4 * cs["buy_in"] / 100)
                                                - 0.02 * cs["understanding"]))
            cs["buy_in"] = max(20.0, min(100.0, cs["buy_in"] + (70 - cs["buy_in"]) * 0.03
                                         + sum(tactics.TRAINING_BLOCKS[k].buy_in for k in plan)))
            if cid == self.user_club_id:
                self._user_training(plan, rng)

    def _user_training(self, plan, rng) -> None:
        squad = self._players.get(self.user_club_id, [])
        for key in plan:
            block = tactics.TRAINING_BLOCKS[key]
            if block.attr:
                for p in squad:
                    if p.age < 30 and rng.random() < 0.012 and getattr(p, block.attr) < 97:
                        setattr(p, block.attr, getattr(p, block.attr) + 1)
                        self._dirty.add(p.id)
            if key == "cohesion":
                setup = self.team_setup(self.user_club_id)
                for i, p in enumerate(setup.xi):
                    if p:
                        role = setup.role_name(i)
                        self._fam[(p.id, role)] = min(100.0, self.familiarity(p, role) + 0.4)

    def advance_day(self) -> None:
        """Play every unplayed fixture of the next matchday (the user's too, with the fast model) and move on."""
        slot = self.matchday + 1
        if slot > schedule.LAST_SLOT or self.season > MAX_SEASONS:
            return
        rng = self.rng_for("slot", self.season, slot)
        if not self.meta(f"week_done_{self.season}_{slot}"):
            self._pre_slot_week()
            self.set_meta(f"week_done_{self.season}_{slot}", True)
        rows = [r for r in self.fixtures_for_slot(slot) if not r["played"]]
        for r in rows:
            home, away = self.team_setup(r["home_id"]), self.team_setup(r["away_id"])
            res = match.fast_match(rng, home, away, bool(r["neutral"]))
            self._commit(r, res, home, away, rng)
        self.finish_slot(slot)

    def finish_slot(self, slot: int) -> None:
        economy.weekly_tick(self.conn, self.season)
        self.set_meta("matchday", slot)
        self.set_meta("live_match", False)
        self._progress_competitions()
        self._flush()
        self.reload_fast()

    def reload_fast(self) -> None:
        """Keep caches; just refresh club rows (balances changed)."""
        self._clubs = {r["id"]: r for r in self.conn.execute("SELECT * FROM clubs")}
        self._ai_xi = {}

    def _flush(self) -> None:
        if self._dirty:
            ids = self._dirty
            rows = []
            for plist in self._players.values():
                for p in plist:
                    if p.id in ids:
                        rows.append((p.fitness, p.injured_weeks, p.suspended_games, p.yellow_cards, round(p.form, 2),
                                     p.pace, p.shooting, p.passing, p.dribbling, p.defending, p.physical, p.id))
            self.conn.executemany(
                "UPDATE players SET fitness=?, injured_weeks=?, suspended_games=?, yellow_cards=?, form=?, "
                "pace=?, shooting=?, passing=?, dribbling=?, defending=?, physical=? WHERE id=?", rows)
            self._dirty = set()
        for cid, cs in self._cs.items():
            self._save_cs(cid)
        if self._fam and self.user_club_id is not None:
            self.conn.executemany(
                "INSERT INTO familiarity (player_id, role, value) VALUES (?,?,?) "
                "ON CONFLICT(player_id, role) DO UPDATE SET value=excluded.value",
                [(pid, role, v) for (pid, role), v in self._fam.items()])
        self.conn.commit()

    # ------------------------------------------------------------------ commit a finished match
    def _is_two_legged(self, comp, stage: str) -> bool:
        return comp["kind"] == "champions_league" and stage in ("Round of 16", "Quarter-final", "Semi-final")

    def _commit(self, fx: sqlite3.Row, res: match.MatchResult, home: match.TeamSetup, away: match.TeamSetup,
                rng: random.Random) -> dict:
        comp = self._comps[fx["competition_id"]]
        stage = fx["stage"]
        hg, ag = res.home_goals, res.away_goals
        et, pens, winner = 0, (None, None), None
        knockout = not (stage.startswith(LEAGUE_PREFIX) or stage.startswith(GROUP_PREFIX))
        if knockout:
            two = self._is_two_legged(comp, stage)
            if not two or fx["leg"] == 2:
                agg_h, agg_a = hg, ag
                if two:
                    first = self.conn.execute(
                        "SELECT * FROM fixtures WHERE competition_id=? AND season=? AND tie=? AND leg=1",
                        (fx["competition_id"], fx["season"], fx["tie"])).fetchone()
                    agg_h += first["away_goals"]
                    agg_a += first["home_goals"]
                if agg_h == agg_a:
                    eh, ea = match.extra_time(rng, home, away, bool(fx["neutral"]))
                    hg, ag, agg_h, agg_a, et = hg + eh, ag + ea, agg_h + eh, agg_a + ea, 1
                    if agg_h == agg_a:
                        pens = match.shootout(rng, home, away)
                        winner = fx["home_id"] if pens[0] > pens[1] else fx["away_id"]
                if winner is None:
                    winner = fx["home_id"] if agg_h > agg_a else fx["away_id"]
        self.conn.execute(
            "UPDATE fixtures SET home_goals=?, away_goals=?, played=1, winner_id=?, extra_time=?, pens_home=?, pens_away=?, "
            "xg_home=?, xg_away=? WHERE id=?",
            (hg, ag, winner, et, pens[0], pens[1], round(res.xg_home, 2), round(res.xg_away, 2), fx["id"]))
        if self.user_club_id in (fx["home_id"], fx["away_id"]) and res.events:
            self.conn.executemany(
                "INSERT INTO match_events (fixture_id, minute, kind, player_id, club_id) VALUES (?,?,?,?,?)",
                [(fx["id"], e.minute, e.kind, e.player_id,
                  fx["home_id"] if e.side == "home" else fx["away_id"] if e.side == "away" else None)
                 for e in res.events if e.kind in ("goal", "yellow", "red", "injury", "sub")])
        self._apply_effects(fx, res, home, away, hg, ag, comp)
        return {"home_goals": hg, "away_goals": ag, "winner_id": winner, "extra_time": bool(et), "pens": pens}

    def _apply_effects(self, fx, res, home, away, hg, ag, comp) -> None:
        by_id = {p.id: p for plist in self._players.values() for p in plist}
        stats: dict[int, list] = {}

        def st(pid, club):
            return stats.setdefault(pid, [club, 0, 0, 0, 0, 0])      # club, apps, goals, assists, yellows, reds

        for side, team, cid, gf, ga in (("home", home, fx["home_id"], hg, ag), ("away", away, fx["away_id"], ag, hg)):
            squad = self._players.get(cid, [])
            for p in squad:                         # a suspension is served by missing this match
                if p.suspended_games > 0:
                    p.suspended_games -= 1
                    self._dirty.add(p.id)
            load = tactics.PRESSING_FX[team.pressing][1]
            for pid, minutes in res.minutes.items():
                if res.sides.get(pid) != side or pid not in by_id or minutes <= 0:
                    continue
                p = by_id[pid]
                p.fitness = max(25, round(p.fitness - 10 * (minutes / 90) * load * (1.2 if p.age > 31 else 1.0)))
                st(pid, cid)[1] += 1
                self._dirty.add(pid)
            cs = self._cs[cid]
            cs["buy_in"] = max(20.0, min(100.0, cs["buy_in"] + (1.5 if gf > ga else 0.2 if gf == ga else -2.0)))
            cs["understanding"] = min(98.0, cs["understanding"] + 0.25)
            if cid == self.user_club_id:
                for i, p in enumerate(team.xi):
                    if p:
                        role = team.role_name(i)
                        self._fam[(p.id, role)] = min(100.0, self.familiarity(p, role) + 1.5)
        for side, scorer, minute, assist in res.goals:
            if scorer in by_id:
                st(scorer, by_id[scorer].club_id)[2] += 1
                p = by_id[scorer]
                p.form = min(10.0, p.form + 0.5)
            if assist and assist in by_id:
                st(assist, by_id[assist].club_id)[3] += 1
        for side, pid, kind, minute in res.cards:
            if pid not in by_id:
                continue
            p = by_id[pid]
            if kind == "yellow":
                st(pid, p.club_id)[4] += 1
                p.yellow_cards += 1
                if p.yellow_cards >= 5:
                    p.suspended_games += 1
                    p.yellow_cards = 0
            else:
                st(pid, p.club_id)[5] += 1
                p.suspended_games += 1
            self._dirty.add(pid)
        for side, pid, weeks in res.injuries:
            if pid in by_id:
                by_id[pid].injured_weeks = max(by_id[pid].injured_weeks, weeks)
                self._dirty.add(pid)
                if by_id[pid].club_id == self.user_club_id:
                    self.news(f"{by_id[pid].name} is injured for {weeks} week{'s' if weeks != 1 else ''}.", "injury")
        for p in by_id.values():
            if p.id in stats:
                p.form = max(4.0, min(10.0, 0.85 * p.form + 0.15 * 6.5))
        self.conn.executemany(
            "INSERT INTO player_stats (season, player_id, club_id, apps, goals, assists, yellows, reds) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(season, player_id) DO UPDATE SET apps=apps+excluded.apps, goals=goals+excluded.goals, "
            "assists=assists+excluded.assists, yellows=yellows+excluded.yellows, reds=reds+excluded.reds, club_id=excluded.club_id",
            [(self.season, pid, v[0], v[1], v[2], v[3], v[4], v[5]) for pid, v in stats.items()])
        if self.user_club_id in (fx["home_id"], fx["away_id"]):
            self.news(f"{comp['name']}: {self.club_name(fx['home_id'])} {hg}-{ag} {self.club_name(fx['away_id'])}", "result")

    # ------------------------------------------------------------------ live matches (the user's games)
    def begin_match_day(self) -> list[Fixture]:
        fixtures = self.pending_user_fixtures()
        if fixtures:
            self.set_meta("live_match", True)
            self.conn.commit()
        return fixtures

    def start_live_match(self, fixture_id: int) -> match.LiveMatch:
        """Prepare the weekly training/recovery (once) and build a LiveMatch for one of the user's fixtures."""
        slot = self.matchday + 1
        if not self.meta(f"week_done_{self.season}_{slot}"):
            self._pre_slot_week()
            self.set_meta(f"week_done_{self.season}_{slot}", True)
        r = self.conn.execute("SELECT * FROM fixtures WHERE id=?", (fixture_id,)).fetchone()
        home, away = self.team_setup(r["home_id"]), self.team_setup(r["away_id"])
        side = "home" if r["home_id"] == self.user_club_id else "away"
        seed = self.rng_for("live", self.season, fixture_id).randrange(1 << 30)
        return match.LiveMatch(home, away, seed, side, bool(r["neutral"]))

    def commit_live_match(self, fixture_id: int, live: match.LiveMatch) -> dict:
        r = self.conn.execute("SELECT * FROM fixtures WHERE id=?", (fixture_id,)).fetchone()
        res = live.result()
        rng = self.rng_for("decide", self.season, fixture_id)
        out = self._commit(r, res, live.teams["home"], live.teams["away"], rng)
        cs = self._cs[self.user_club_id]
        cs["buy_in"] = max(20.0, min(100.0, cs["buy_in"] + live.buy_in_delta))
        out["result"] = res
        self._flush()
        if not self.pending_user_fixtures():
            self.set_meta("live_match", False)
        self.conn.commit()
        return out

    # ------------------------------------------------------------------ knockouts
    def _progress_competitions(self) -> None:
        for comp in list(self._comps.values()):
            if comp["kind"] == "cup":
                self._progress_cup(comp)
            elif comp["kind"] == "champions_league":
                self._progress_cl(comp)

    def _stage_rows(self, comp_id: int, stage: str):
        return self.conn.execute("SELECT * FROM fixtures WHERE competition_id=? AND season=? AND stage=? ORDER BY id",
                                 (comp_id, self.season, stage)).fetchall()

    def _progress_cup(self, comp) -> None:
        names = [n for n, _ in schedule.CUP_ROUNDS]
        for i, name in enumerate(names[:-1]):
            rows = self._stage_rows(comp["id"], name)
            if not rows or not all(r["played"] for r in rows):
                continue
            nxt_name, nxt_slot = schedule.CUP_ROUNDS[i + 1]
            if self._stage_rows(comp["id"], nxt_name):
                continue
            winners = [r["winner_id"] for r in rows]
            if name == "Preliminary round":
                playing = {r["home_id"] for r in rows} | {r["away_id"] for r in rows}
                winners += [c for c, v in self._clubs.items() if v["league_id"] == comp["league_id"] and c not in playing]
            rng = self.rng_for("cup", self.season, comp["id"], name)
            for h, a in schedule.pair_random(winners, rng):
                self._add_fixture(comp["id"], self.season, nxt_slot, h, a, nxt_name)

    def _progress_cl(self, comp) -> None:
        cid = comp["id"]
        stage_names = [n for n, _ in schedule.CL_KNOCKOUT]
        group_rows = self.conn.execute(
            "SELECT * FROM fixtures WHERE competition_id=? AND season=? AND stage LIKE 'Group%'", (cid, self.season)).fetchall()
        if group_rows and all(r["played"] for r in group_rows) and not self._stage_rows(cid, "Round of 16"):
            table = self.get_table(cid)
            winners, runners = [], []
            for g in sorted({t.group for t in table}):
                rows = [t for t in table if t.group == g]
                winners.append((rows[0].club_id, g))
                runners.append((rows[1].club_id, g))
            rng = self.rng_for("cl", self.season, "r16")
            slots = schedule.CL_KNOCKOUT[0][1]
            for tie, (w, r) in enumerate(schedule.pair_winners_runners(winners, runners, rng)):
                self._add_fixture(cid, self.season, slots[0], r, w, "Round of 16", 1, tie)
                self._add_fixture(cid, self.season, slots[1], w, r, "Round of 16", 2, tie)
            return
        for i, name in enumerate(stage_names[:-1]):
            rows = self._stage_rows(cid, name)
            if not rows or not all(r["played"] for r in rows):
                continue
            nxt, nxt_slots = schedule.CL_KNOCKOUT[i + 1]
            if self._stage_rows(cid, nxt):
                continue
            winners = [r["winner_id"] for r in rows if r["leg"] == 2]
            rng = self.rng_for("cl", self.season, nxt)
            pairs = schedule.pair_random(winners, rng)
            for tie, (h, a) in enumerate(pairs):
                if nxt == "Final":
                    self._add_fixture(cid, self.season, nxt_slots[0], h, a, nxt, 1, tie, neutral=1)
                else:
                    self._add_fixture(cid, self.season, nxt_slots[0], h, a, nxt, 1, tie)
                    self._add_fixture(cid, self.season, nxt_slots[1], a, h, nxt, 2, tie)


# ---------------------------------------------------------------------- module-level contract
_world: World | None = None


def bind(conn: sqlite3.Connection, user_club_id: int | None) -> World:
    """Attach the engine to a loaded game database."""
    global _world
    _world = World(conn, user_club_id)
    return _world


def unbind() -> None:
    global _world
    _world = None


def current() -> World | None:
    return _world


def advance_day() -> None:
    _world.advance_day() if _world else _stubs.stub_advance_day()


def advance_season() -> None:
    _world.advance_season() if _world else _stubs.stub_advance_season()


def get_clubs(league_id: int | None = None):
    return _world.get_clubs(league_id) if _world else _stubs.stub_get_clubs(league_id)


def get_squad(club_id: int):
    return _world.get_squad(club_id) if _world else _stubs.stub_get_squad(club_id)


def get_table(competition_id: int):
    return _world.get_table(competition_id) if _world else _stubs.stub_get_table(competition_id)


def get_fixtures(club_id: int):
    return _world.get_fixtures(club_id) if _world else _stubs.stub_get_fixtures(club_id)
