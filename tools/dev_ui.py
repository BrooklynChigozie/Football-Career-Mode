"""Try your screens without Prosper's shell:  python tools/dev_ui.py
Run from the project root (it must be a Sources Root in PyCharm)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from engine.sample_data import make_sample_world
from ui.screens import ENGINE_SCREENS


def main():
    app = QApplication(sys.argv)
    world = make_sample_world(seed=1, user_club="Arsenal")
    window = QMainWindow()
    window.setWindowTitle("Football Manager - dev view")
    tabs = QTabWidget()
    screens = [cls(world) for cls in ENGINE_SCREENS]
    for s in screens:
        tabs.addTab(s, s.title)
        s.changed.connect(lambda: screens[tabs.currentIndex()].refresh())
    tabs.currentChanged.connect(lambda i: screens[i].refresh())
    window.setCentralWidget(tabs)
    window.resize(1100, 720)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()