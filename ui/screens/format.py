"""Small text helpers shared by screens."""


def score_text(result) -> str:
    if result is None:
        return "-"
    return f"{result.home_goals} - {result.away_goals}"


def result_note(result) -> str:
    if result is None:
        return ""
    if result.pens:
        return f"a.e.t., pens {result.pens[0]}-{result.pens[1]}"
    return "a.e.t." if result.aet else ""


def event_lines(world, result):
    """Turn a MatchResult's events into readable commentary lines."""
    lines = []
    for e in sorted(result.events, key=lambda e: e.minute):
        p = world.players.get(e.player_id)
        club = world.clubs[e.club_id].name
        name = p.name if p else "Unknown"
        if e.kind == "goal":
            assist = world.players.get(e.assist_id) if e.assist_id else None
            extra = f" (assist: {assist.name})" if assist else ""
            lines.append(f"{e.minute:>3}'  GOAL  {name}, {club}{extra}")
        elif e.kind == "yellow":
            lines.append(f"{e.minute:>3}'  Yellow card  {name}, {club}")
        elif e.kind == "red":
            lines.append(f"{e.minute:>3}'  RED CARD  {name}, {club}")
        elif e.kind == "injury":
            lines.append(f"{e.minute:>3}'  Injury  {name}, {club}")
    return lines