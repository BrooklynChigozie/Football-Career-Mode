"""Run slow engine calls (advance a week / a season) off the UI thread so the window never freezes."""
from PySide6.QtCore import QThread, Signal


class WorldWorker(QThread):
    finished_ok = Signal(object)   # carries the function's return value
    failed = Signal(str)

    def __init__(self, func, *args, parent=None):
        super().__init__(parent)
        self._func, self._args = func, args

    def run(self):
        try:
            self.finished_ok.emit(self._func(*self._args))
        except Exception as exc:  # report errors on the UI thread instead of crashing the thread
            self.failed.emit(str(exc))