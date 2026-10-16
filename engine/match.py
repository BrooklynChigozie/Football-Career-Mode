"""Match simulation. Pure Python, no UI or database imports.

Two models share the same team-strength maths so results stay consistent:
  * fast_match: a few weighted draws (Poisson goals). Used for AI-vs-AI games.
  * LiveMatch:  5-minute chunks with a momentum state, shots with xG, fouls, cards, injuries,
                substitutions, mentality changes and shouts. Used for the user's matches.
Both take a random.Random so results can be reproduced from a seed.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from engine import tactics
from engine.lineup import FORMATIONS, _fit

BASE_GOALS = 1.30
GAMMA = 3.2
HOME_ADV = 1.12
AWAY_ADV = 0.92
SHOTS_PER_MATCH = 12.0
SHOT_EXP = 1.6
CHUNKS = 18
MAX_SUBS = 5

DEF_LABELS = {"CB", "LB", "RB"}
MID_LABELS = {"CDM", "CM", "CAM", "LM", "RM"}
SCORER_W = {"ST": 5.0, "LW": 3.4, "RW": 3.4, "CAM": 3.0, "LM": 2.5, "RM": 2.5, "CM": 1.8, "CDM": 0.8,
            "LB": 0.8, "RB": 0.8, "CB": 0.9, "GK": 0.01}
ASSIST_W = {"ST": 1.6, "LW": 3.0, "RW": 3.0, "CAM": 3.6, "LM": 2.8, "RM": 2.8, "CM": 2.4, "CDM": 1.2,
            "LB": 1.5, "RB": 1.5, "CB": 0.6, "GK": 0.05}
FOUL_W = {"CB": 3.0, "CDM": 3.4, "CM": 2.2, "LB": 2.0, "RB": 2.0, "CAM": 1.2, "LM": 1.3, "RM": 1.3,
          "LW": 1.0, "RW": 1.0, "ST": 1.4, "GK": 0.1}


def group_of(label: str) -> str:
    return "GK" if label == "GK" else "DEF" if label in DEF_LABELS else "MID" if label in MID_LABELS else "ATT"


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def injury_weeks(rng: random.Random) -> int:
    return rng.choices([1, 2, 3, 4, 6, 10, 16, 26], [20, 22, 18, 14, 11, 8, 5, 2])[0]


@dataclass
class TeamSetup:
    club_id: int
    name: str
    formation: str
    mentality: str
    pressing: str
    passing: str
    understanding: float
    buy_in: float
    xi: list                      # Player or None, in formation slot order
    bench: list = field(default_factory=list)
    roles: dict = field(default_factory=dict)         # slot index -> role name
    familiarity: dict = field(default_factory=dict)   # (player_id, role name) -> 0-100
    injury_mult: float = 1.0

    @property
    def slots(self):
        return FORMATIONS[self.formation]

    def role_name(self, i: int) -> str:
        return self.roles.get(i) or tactics.default_role(self.slots[i].label)

    def avg_overall(self) -> float:
        ps = [p.overall for p in self.xi if p]
        return sum(ps) / len(ps) if ps else 50.0


@dataclass
class Strengths:
    attack: float
    defence: float
    midfield: float
    gk: float
    ter: float
    on_pitch: int


def compute_strengths(team: TeamSetup, xi: list | None = None, mentality: str | None = None, fatigue: float = 0.0,
                      att_mult: float = 1.0, def_mult: float = 1.0) -> Strengths:
    xi = team.xi if xi is None else xi
    groups = {"GK": [], "DEF": [], "MID": [], "ATT": []}
    att_roles, def_roles, n = 0.0, 0.0, 0
    for i, (slot, p) in enumerate(zip(team.slots, xi)):
        if p is None:
            continue
        n += 1
        role = tactics.get_role(slot.label, team.role_name(i))
        base = _fit(p, slot)
        base = 30.0 if base < 0 else base
        fam = team.familiarity.get((p.id, role.name), 60.0 if p.position in slot.accepts else 35.0)
        eff = base * (0.88 + 0.12 * p.fitness / 100) * tactics.role_fit(p, role) * (0.97 + 0.06 * fam / 100)
        groups[group_of(slot.label)].append(eff)
        att_roles += role.attack
        def_roles += role.defence

    def avg(g, default=40.0):
        return sum(groups[g]) / len(groups[g]) if groups[g] else default

    gk, d, m, a = avg("GK"), avg("DEF"), avg("MID"), avg("ATT")
    ter = tactics.tactical_effectiveness(team.understanding, team.avg_overall(), team.buy_in)
    tm = tactics.ter_multiplier(ter)
    ma, md = tactics.MENTALITY_FX[mentality or team.mentality]
    n = max(n, 1)
    pen = (n / 11) ** 0.7
    fat = 1 - fatigue
    attack = (0.55 * a + 0.35 * m + 0.10 * d) * ma * tm * (1 + 3 * att_roles / n) * att_mult * fat * pen
    defence = (0.42 * d + 0.22 * gk + 0.26 * m + 0.10 * a) * md * tm * (1 + 3 * def_roles / n) * def_mult * fat * pen
    mid = m * tactics.PRESSING_FX[team.pressing][0] * tm * fat
    return Strengths(attack, defence, mid, gk, ter, n)


@dataclass
class Event:
    minute: int
    kind: str          # kickoff, goal, save, miss, yellow, red, injury, sub, momentum, halftime, fulltime, info
    side: str = ""
    text: str = ""
    player_id: int | None = None
    other_id: int | None = None

    @property
    def importance(self) -> int:
        return {"goal": 3, "red": 3, "yellow": 2, "injury": 2, "sub": 1, "save": 1, "momentum": 1}.get(self.kind, 0)


@dataclass
class MatchResult:
    home_goals: int
    away_goals: int
    xg_home: float
    xg_away: float
    stats: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    goals: list = field(default_factory=list)       # (side, scorer_id, minute, assist_id)
    cards: list = field(default_factory=list)       # (side, player_id, 'yellow'|'red', minute)
    injuries: list = field(default_factory=list)    # (side, player_id, weeks)
    minutes: dict = field(default_factory=dict)     # player_id -> minutes played
    sides: dict = field(default_factory=dict)       # player_id -> 'home'|'away'


def _pick(rng, items, weights):
    return rng.choices(items, weights)[0] if items else None


def _pick_scorer(rng, team: TeamSetup, xi: list):
    cands = [(p, SCORER_W[s.label] * (p.shooting / 70) ** 3) for s, p in zip(team.slots, xi) if p]
    return _pick(rng, [c[0] for c in cands], [c[1] for c in cands])


def _pick_assister(rng, team: TeamSetup, xi: list, scorer):
    cands = [(p, ASSIST_W[s.label] * ((p.passing + p.dribbling) / 140) ** 3)
             for s, p in zip(team.slots, xi) if p and p is not scorer]
    return _pick(rng, [c[0] for c in cands], [c[1] for c in cands])


def _lambdas(h: Strengths, a: Strengths, neutral: bool):
    lh = BASE_GOALS * (h.attack / a.defence) ** GAMMA * (1.0 if neutral else HOME_ADV)
    la = BASE_GOALS * (a.attack / h.defence) ** GAMMA * (1.0 if neutral else AWAY_ADV)
    return lh, la


def fast_match(rng: random.Random, home: TeamSetup, away: TeamSetup, neutral: bool = False) -> MatchResult:
    """AI-vs-AI model: Poisson goals from team strengths, scorers and cards by weighted draws."""
    sh, sa = compute_strengths(home), compute_strengths(away)
    lh, la = _lambdas(sh, sa, neutral)
    hg, ag = poisson(rng, lh), poisson(rng, la)
    res = MatchResult(hg, ag, lh, la)
    for side, team, n in (("home", home, hg), ("away", away, ag)):
        for p in team.xi:
            if p:
                res.minutes[p.id], res.sides[p.id] = 90, side
        for _ in range(n):
            scorer = _pick_scorer(rng, team, team.xi)
            if not scorer:
                continue
            assist = _pick_assister(rng, team, team.xi, scorer) if rng.random() < 0.72 else None
            res.goals.append((side, scorer.id, rng.randint(1, 90), assist.id if assist else None))
        load = tactics.PRESSING_FX[team.pressing][1]
        players = [(s.label, p) for s, p in zip(team.slots, team.xi) if p]
        for _ in range(poisson(rng, 1.6 * load)):
            p = _pick(rng, [x[1] for x in players], [FOUL_W[x[0]] for x in players])
            if p:
                res.cards.append((side, p.id, "yellow", rng.randint(5, 90)))
        if rng.random() < 0.03 * load:
            p = _pick(rng, [x[1] for x in players], [FOUL_W[x[0]] for x in players])
            if p:
                res.cards.append((side, p.id, "red", rng.randint(20, 90)))
        if rng.random() < 0.12 * team.injury_mult and players:
            p = _pick(rng, [x[1] for x in players], [120 - x[1].fitness for x in players])
            res.injuries.append((side, p.id, injury_weeks(rng)))
        for b in rng.sample(team.bench, min(2, len(team.bench))):
            res.minutes[b.id], res.sides[b.id] = 20, side
    return res


def extra_time(rng: random.Random, home: TeamSetup, away: TeamSetup, neutral: bool = False) -> tuple[int, int]:
    sh = compute_strengths(home, fatigue=0.04)
    sa = compute_strengths(away, fatigue=0.04)
    lh, la = _lambdas(sh, sa, neutral)
    return poisson(rng, lh / 3), poisson(rng, la / 3)


def shootout(rng: random.Random, home: TeamSetup, away: TeamSetup) -> tuple[int, int]:
    """Weighted penalty shootout: five kicks each, then sudden death. Never ends level."""
    def p_score(team):
        att = [p for p in team.xi if p] or [None]
        avg = sum((p.shooting if p else 60) for p in att) / len(att)
        return min(0.88, max(0.68, 0.76 + (avg - 65) * 0.002))
    ph, pa = p_score(home), p_score(away)
    gh = sum(rng.random() < ph for _ in range(5))
    ga = sum(rng.random() < pa for _ in range(5))
    while gh == ga:
        gh += rng.random() < ph
        ga += rng.random() < pa
    return int(gh), int(ga)


class LiveMatch:
    """Chunked match for the user's games. Call step() for each 5-minute spell; interact in between."""

    def __init__(self, home: TeamSetup, away: TeamSetup, seed: int, user_side: str | None = None,
                 neutral: bool = False, buy_in_bonus: float = 0.0):
        self.rng = random.Random(seed)
        self.teams = {"home": home, "away": away}
        self.user_side = user_side
        self.neutral = neutral
        self.xi = {s: list(t.xi) for s, t in self.teams.items()}
        self.bench = {s: list(t.bench) for s, t in self.teams.items()}
        self.mentality = {s: t.mentality for s, t in self.teams.items()}
        self.shouts: dict[str, list[list]] = {"home": [], "away": []}
        self.subs_used = {"home": 0, "away": 0}
        self.score = {"home": 0, "away": 0}
        self.momentum = 0.0                    # +1 = home dominating, -1 = away dominating
        self.chunk = 0
        self.stats = {s: {"poss": 0.0, "shots": 0, "sot": 0, "xg": 0.0, "fouls": 0, "passes": 0, "pass_ok": 0,
                          "yellow": 0, "red": 0, "corners": 0} for s in self.teams}
        self.events: list[Event] = []
        self.goals, self.cards, self.injuries = [], [], []
        self.yellows: dict[int, int] = {}
        self.start_min = {p.id: 0 for s in self.xi for p in self.xi[s] if p}
        self.end_min: dict[int, int] = {}
        self.sides = {p.id: s for s in self.xi for p in self.xi[s] if p}
        self.history: list[dict] = []
        self.buy_in_delta = buy_in_bonus
        self.log(0, "kickoff", "", f"Kick-off: {home.name} vs {away.name}")

    # ---- queries ----
    @property
    def minute(self) -> int:
        return min(90, self.chunk * 5)

    @property
    def finished(self) -> bool:
        return self.chunk >= CHUNKS

    def lineup(self, side: str):
        return list(zip(self.teams[side].slots, self.xi[side]))

    def on_pitch(self, side: str) -> list:
        return [p for p in self.xi[side] if p]

    def _fatigue(self, side: str) -> float:
        load = tactics.PRESSING_FX[self.teams[side].pressing][1]
        return 0.0022 * self.chunk * load

    def _mods(self, side: str):
        att, de = 1.0, 1.0
        for name, _left in self.shouts[side]:
            if name == "Demand More":
                att *= 1.03 if self.teams[side].buy_in >= 60 else 0.98
            elif name == "Encourage":
                att *= 1.012
                de *= 1.012
            elif name == "Focus":
                de *= 1.03
        return att, de

    def strengths(self, side: str) -> Strengths:
        att, de = self._mods(side)
        return compute_strengths(self.teams[side], self.xi[side], self.mentality[side], self._fatigue(side), att, de)

    def log(self, minute, kind, side, text, pid=None, other=None) -> Event:
        ev = Event(minute, kind, side, text, pid, other)
        self.events.append(ev)
        return ev

    def _name(self, p) -> str:
        return p.name if p else "?"

    # ---- user / AI actions ----
    def set_mentality(self, side: str, m: str) -> None:
        if m in tactics.MENTALITY_FX and m != self.mentality[side]:
            self.mentality[side] = m
            self.log(self.minute, "info", side, f"{self.teams[side].name} change mentality to {m}.")

    def shout(self, side: str, name: str) -> str:
        if name not in tactics.SHOUTS:
            return "Unknown shout."
        if name == "Praise":
            self.buy_in_delta += 0.6
            self.momentum += 0.05 if side == "home" else -0.05
        elif name == "Calm Down":
            self.shouts[side].append([name, 3])
        else:
            self.shouts[side] = [s for s in self.shouts[side] if s[0] != name] + [[name, 3]]
        self.log(self.minute, "info", side, f"Touchline: \"{name}!\"")
        return tactics.SHOUTS[name]

    def substitute(self, side: str, out_id: int, in_id: int) -> tuple[bool, str]:
        if self.subs_used[side] >= MAX_SUBS:
            return False, "No substitutions left."
        xi = self.xi[side]
        idx = next((i for i, p in enumerate(xi) if p and p.id == out_id), None)
        inn = next((p for p in self.bench[side] if p.id == in_id), None)
        if idx is None or inn is None:
            return False, "Invalid substitution."
        if not inn.available:
            return False, f"{inn.name} is not available."
        out = xi[idx]
        self._swap(side, idx, out, inn, "sub")
        return True, f"{inn.name} replaces {out.name}."

    def _swap(self, side, idx, out, inn, why) -> None:
        self.xi[side][idx] = inn
        self.bench[side] = [p for p in self.bench[side] if p.id != inn.id]
        self.subs_used[side] += 1
        m = self.minute
        self.end_min[out.id] = m
        self.start_min[inn.id] = m
        self.sides[inn.id] = side
        club = self.teams[side].name
        self.log(m, "sub", side, f"{m}' Substitution ({club}): {inn.name} on for {out.name}"
                 + (" (injury)." if why == "injury" else "."), inn.id, out.id)

    def _best_sub(self, side: str, idx: int):
        label = self.teams[side].slots[idx].label
        grp = group_of(label)
        cands = [p for p in self.bench[side] if p.available]
        same = [p for p in cands if group_of_pos(p.position) == grp]
        pool = same or ([p for p in cands if p.position != "GK"] if grp != "GK" else [])
        return max(pool, key=lambda p: p.overall, default=None)

    # ---- simulation ----
    def _ai_decisions(self, side: str) -> None:
        other = "away" if side == "home" else "home"
        c = self.chunk
        diff = self.score[side] - self.score[other]
        if c >= 10:
            if diff < 0:
                self.set_mentality(side, "Attacking" if diff <= -2 or c >= 14 else "Positive")
            elif diff > 0 and c >= 14:
                self.set_mentality(side, "Cautious")
        if c in (11, 13, 15) and self.subs_used[side] < 3:
            xi = self.xi[side]
            tired = [(p.fitness - 4 * self.chunk * 0.35, i) for i, p in enumerate(xi) if p and p.position != "GK"]
            if tired:
                _, idx = min(tired)
                inn = self._best_sub(side, idx)
                if inn:
                    self._swap(side, idx, xi[idx], inn, "tactical")

    def step(self) -> list[Event]:
        """Simulate the next 5-minute spell and return its events."""
        if self.finished:
            return []
        start_len = len(self.events)
        for s in ("home", "away"):
            if s != self.user_side:
                self._ai_decisions(s)
        sh, sa = self.strengths("home"), self.strengths("away")
        lh, la = _lambdas(sh, sa, self.neutral)
        chunk_events: list[Event] = []
        mid_sum = sh.midfield + sa.midfield
        poss = {"home": 50 + 110 * (sh.midfield - sa.midfield) / mid_sum + 7 * self.momentum,
                "away": 0.0}
        poss["home"] = max(28.0, min(72.0, poss["home"] + tactics.PASSING_FX[self.teams["home"].passing][0]
                                     - tactics.PASSING_FX[self.teams["away"].passing][0] * 0.5))
        poss["away"] = 100.0 - poss["home"]
        for side, st, other_st, lam in (("home", sh, sa, lh), ("away", sa, sh, la)):
            other = "away" if side == "home" else "home"
            team = self.teams[side]
            ratio = st.attack / other_st.defence
            shots_match = SHOTS_PER_MATCH * ratio ** SHOT_EXP * tactics.PASSING_FX[team.passing][1]
            xg_mean = lam / max(shots_match, 1e-6)
            sign = 1 if side == "home" else -1
            rate = shots_match / CHUNKS * (1 + 0.6 * sign * self.momentum)
            stats = self.stats[side]
            stats["poss"] += poss[side]
            n_pass = round(25 * poss[side] / 50 * (1.15 if team.passing == "Short" else 0.8 if team.passing == "Direct" else 1))
            pass_avg = self._avg_passing(side)
            acc = max(0.55, min(0.93, 0.70 + 0.004 * (pass_avg - 65) + tactics.PASSING_FX[team.passing][2] / 100
                                + self.rng.uniform(-0.02, 0.02)))
            stats["passes"] += n_pass
            stats["pass_ok"] += round(n_pass * acc)
            for _ in range(poisson(self.rng, rate)):
                minute = self.chunk * 5 + self.rng.randint(1, 5)
                xg = max(0.01, min(0.8, self.rng.gammavariate(2.0, xg_mean / 2.0)))
                stats["shots"] += 1
                stats["xg"] += xg
                shooter = _pick_scorer(self.rng, team, self.xi[side])
                if shooter is None:
                    continue
                if self.rng.random() < xg:
                    stats["sot"] += 1
                    assist = _pick_assister(self.rng, team, self.xi[side], shooter) if self.rng.random() < 0.72 else None
                    self.score[side] += 1
                    self.goals.append((side, shooter.id, minute, assist.id if assist else None))
                    txt = f"{minute}' GOAL! {shooter.name} ({team.name}) scores" + (f", set up by {assist.name}." if assist else ".")
                    chunk_events.append(Event(minute, "goal", side, txt, shooter.id, assist.id if assist else None))
                    self.momentum = max(-1, min(1, self.momentum + sign * 0.45))
                elif self.rng.random() < min(0.9, 0.12 + xg * 2.4):
                    stats["sot"] += 1
                    gk = next((p for p in self.xi[other] if p and p.position == "GK"), None)
                    chunk_events.append(Event(minute, "save", side,
                                              f"{minute}' {shooter.name} shoots on target and {self._name(gk)} saves.",
                                              shooter.id))
                else:
                    if self.rng.random() < 0.55:
                        chunk_events.append(Event(minute, "miss", side, f"{minute}' {shooter.name} fires wide.", shooter.id))
                    if self.rng.random() < 0.3:
                        stats["corners"] += 1
            # fouls and cards
            calm = 0.7 if any(s[0] == "Calm Down" for s in self.shouts[side]) else 1.0
            load = tactics.PRESSING_FX[team.pressing][1]
            for _ in range(poisson(self.rng, 0.64 * load * calm)):
                stats["fouls"] += 1
                minute = self.chunk * 5 + self.rng.randint(1, 5)
                players = [(s.label, p) for s, p in zip(team.slots, self.xi[side]) if p]
                p = _pick(self.rng, [x[1] for x in players], [FOUL_W[x[0]] for x in players])
                if p is None:
                    continue
                r = self.rng.random()
                if r < 0.004 * calm:
                    chunk_events.append(self._send_off(side, p, minute, "straight red"))
                elif r < 0.004 + 0.12 * calm:
                    n_y = self.yellows.get(p.id, 0) + 1
                    self.yellows[p.id] = n_y
                    stats["yellow"] += 1
                    self.cards.append((side, p.id, "yellow", minute))
                    chunk_events.append(Event(minute, "yellow", side, f"{minute}' Yellow card for {p.name} ({team.name}).", p.id))
                    if n_y >= 2:
                        chunk_events.append(self._send_off(side, p, minute, "second yellow"))
            # injuries
            if self.rng.random() < 0.0065 * team.injury_mult:
                players = [(i, p) for i, p in enumerate(self.xi[side]) if p]
                if players:
                    idx, p = self.rng.choice(players)
                    minute = self.chunk * 5 + self.rng.randint(1, 5)
                    weeks = injury_weeks(self.rng)
                    self.injuries.append((side, p.id, weeks))
                    chunk_events.append(Event(minute, "injury", side, f"{minute}' {p.name} ({team.name}) is injured and must go off.", p.id))
                    self.end_min[p.id] = minute
                    self.xi[side][idx] = None
                    inn = self._best_sub(side, idx) if self.subs_used[side] < MAX_SUBS else None
                    if inn:
                        self._swap(side, idx, p, inn, "injury")
        # momentum drifts toward the stronger side's pressure, with noise
        signal = max(-1.0, min(1.0, (sh.attack / sa.defence - sa.attack / sh.defence) * 2.2 + self.rng.gauss(0, 0.35)))
        self.momentum = max(-1.0, min(1.0, 0.72 * self.momentum + 0.28 * signal))
        for s in ("home", "away"):
            self.shouts[s] = [[n, left - 1] for n, left in self.shouts[s] if left - 1 > 0]
        self.chunk += 1
        chunk_events.sort(key=lambda e: e.minute)
        self.events.extend(chunk_events)
        if self.chunk == CHUNKS // 2:
            self.log(45, "halftime", "", f"Half-time: {self.teams['home'].name} {self.score['home']}-{self.score['away']} {self.teams['away'].name}")
        if self.finished:
            self.log(90, "fulltime", "", f"Full-time: {self.teams['home'].name} {self.score['home']}-{self.score['away']} {self.teams['away'].name}")
        self.history.append({"minute": self.chunk * 5, "momentum": self.momentum,
                             "xg_home": self.stats["home"]["xg"], "xg_away": self.stats["away"]["xg"],
                             "poss_home": poss["home"]})
        return self.events[start_len:]

    def _avg_passing(self, side: str) -> float:
        ps = [p.passing for p in self.xi[side] if p and p.position != "GK"]
        return sum(ps) / len(ps) if ps else 60.0

    def _send_off(self, side: str, p, minute: int, why: str) -> Event:
        idx = next(i for i, x in enumerate(self.xi[side]) if x and x.id == p.id)
        self.xi[side][idx] = None
        self.end_min[p.id] = minute
        self.stats[side]["red"] += 1
        self.cards.append((side, p.id, "red", minute))
        self.momentum = max(-1, min(1, self.momentum + (-0.3 if side == "home" else 0.3)))
        return Event(minute, "red", side, f"{minute}' RED CARD! {p.name} ({self.teams[side].name}) is sent off ({why}).", p.id)

    def result(self) -> MatchResult:
        end = 90
        minutes = {}
        for pid, st in self.start_min.items():
            minutes[pid] = max(0, self.end_min.get(pid, end) - st)
        stats = {}
        for s in ("home", "away"):
            d = dict(self.stats[s])
            d["poss"] = round(d["poss"] / max(self.chunk, 1), 1)
            d["xg"] = round(d["xg"], 2)
            d["pass_acc"] = round(100 * d["pass_ok"] / d["passes"], 1) if d["passes"] else 0.0
            stats[s] = d
        return MatchResult(self.score["home"], self.score["away"], stats["home"]["xg"], stats["away"]["xg"], stats,
                           list(self.events), list(self.goals), list(self.cards), list(self.injuries), minutes,
                           dict(self.sides))

    def play_to_end(self) -> MatchResult:
        while not self.finished:
            self.step()
        return self.result()


def group_of_pos(position: str) -> str:
    return group_of(position)
