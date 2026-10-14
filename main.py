import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, load_theme


def main() -> int:
    app = QApplication(sys.argv)
    load_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
