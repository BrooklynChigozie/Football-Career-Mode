"""Base class for every screen. Prosper's shell creates screens as Screen(world, navigate)."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from ui.workers import WorldWorker


class BaseScreen(QWidget):
    title = "Screen"
    changed = Signal()   # emitted after the game state changed; the shell refreshes other screens

    def __init__(self, world, navigate=None, parent=None):
        super().__init__(parent)
        self.world = world
        self.navigate = navigate     # optional callback: navigate("screen_name")
        self._worker = None

    def set_world(self, world):
        """Call when a different save is loaded."""
        self.world = world
        self.refresh()

    def refresh(self):
        """Rebuild the screen from the current world state. Override in each screen."""

    def run_task(self, func, on_done, *args, busy=None):
        """Run func(*args) in a background thread, then call on_done(result) on the UI thread."""
        if busy:
            busy(True)
        self._worker = WorldWorker(func, *args)

        def done(result):
            if busy:
                busy(False)
            on_done(result)

        def failed(message):
            if busy:
                busy(False)
            QMessageBox.warning(self, "Error", message)

        self._worker.finished_ok.connect(done)
        self._worker.failed.connect(failed)
        self._worker.start()