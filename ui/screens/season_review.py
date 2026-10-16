"""End-of-season summary of the most recently completed season."""
from PySide6.QtWidgets import QMessageBox, QPushButton, QTextBrowser, QVBoxLayout

from ui.screens.base_screen import BaseScreen


class SeasonReviewScreen(BaseScreen):
    title = "Season Review"

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(world, navigate, parent)
        layout = QVBoxLayout(self)
        self.view = QTextBrowser()
        layout.addWidget(self.view, 1)
        self.btn = QPushButton("Start next season")
        self.btn.clicked.connect(self.next_season)
        layout.addWidget(self.btn)
        self.refresh()

    def next_season(self):
        try:
            self.world.start_next_season()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Season", str(exc))
            return
        self.changed.emit()
        self.refresh()

    def refresh(self):
        w = self.world
        self.btn.setEnabled(w.phase == "offseason")
        hist = w.get_history()
        if not hist:
            self.view.setHtml("<h2>No completed seasons yet</h2><p>Finish a season to see the review here.</p>")
            return
        s = hist[-1]
        name = lambda cid: w.clubs[cid].name if cid is not None else "-"
        pos = s["league_positions"].get(w.user_club_id)
        html = [f"<h2>Season {s['season']}/{str(s['season'] + 1)[-2:]} review</h2>",
                f"<p><b>Your club:</b> {w.user_club.name} finished <b>{pos}</b> in the {w.user_club.league}.</p>",
                "<h3>League champions</h3><ul>"]
        html += [f"<li>{lg}: {name(cid)}</li>" for lg, cid in s["champions"].items()]
        html += ["</ul><h3>Cup winners</h3><ul>"]
        html += [f"<li>{lg}: {name(cid)}</li>" for lg, cid in s["cup_winners"].items()]
        html += [f"</ul><h3>Champions League</h3><p>{name(s['cl_winner'])}</p><h3>Golden boots</h3><ul>"]
        html += [f"<li>{lg}: {n} ({g} goals)</li>" for lg, (_, n, g) in s["top_scorers"].items()]
        html.append("</ul>")
        if w.phase == "finished":
            html.append("<h2>Your career is complete.</h2>")
        self.view.setHtml("".join(html))