from PySide6.QtCore import QThread, Signal

from engine import world


class AdvanceWorker(QThread):
    """Runs a (possibly slow) engine call off the UI thread. The engine must not touch Qt or our
    sqlite connection from here; state we own is updated on the UI thread after `done`."""

    done = Signal()
    failed = Signal(str)

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind

    def run(self) -> None:
        try:
            if self.kind == "season":
                world.advance_season()
            else:
                world.advance_day()
        except Exception as e:          # surface engine errors in the UI instead of crashing the thread
            self.failed.emit(str(e))
            return
        self.done.emit()
