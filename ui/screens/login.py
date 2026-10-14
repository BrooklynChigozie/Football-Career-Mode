from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from services import auth


class LoginScreen(QWidget):
    """Login and sign-up in one card. Emits logged_in(User) on success."""

    logged_in = Signal(object)

    def __init__(self, app_conn, parent=None):
        super().__init__(parent)
        self._conn = app_conn
        self._register_mode = False

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(380)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 32, 32, 28)
        lay.setSpacing(12)

        self._title = QLabel()
        self._title.setObjectName("loginTitle")
        sub = QLabel("Football Career Mode Simulator")
        sub.setObjectName("muted")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("Confirm password")
        self.confirm.setEchoMode(QLineEdit.Password)
        self.message = QLabel("")
        self.message.setObjectName("error")
        self.message.setWordWrap(True)
        self.submit = QPushButton()
        self.submit.setObjectName("primary")
        self.toggle = QPushButton()
        self.toggle.setObjectName("link")

        for w in (self._title, sub, self.username, self.password, self.confirm,
                  self.message, self.submit, self.toggle):
            lay.addWidget(w)
        outer.addWidget(card)

        self.submit.clicked.connect(self._submit)
        self.toggle.clicked.connect(lambda: self.set_register_mode(not self._register_mode))
        for field in (self.username, self.password, self.confirm):
            field.returnPressed.connect(self._submit)
        self.set_register_mode(False)

    def set_register_mode(self, on: bool) -> None:
        self._register_mode = on
        self._title.setText("Create account" if on else "Welcome back")
        self.submit.setText("Sign up" if on else "Log in")
        self.toggle.setText("Already have an account? Log in" if on else "New here? Create an account")
        self.confirm.setVisible(on)
        self.message.setText("")

    def reset(self) -> None:
        self.password.clear()
        self.confirm.clear()
        self.message.setText("")
        self.set_register_mode(False)

    def _submit(self) -> None:
        user, pw = self.username.text(), self.password.text()
        try:
            if self._register_mode:
                if pw != self.confirm.text():
                    raise auth.AuthError("Passwords do not match.")
                result = auth.register(self._conn, user, pw)
            else:
                result = auth.login(self._conn, user, pw)
        except auth.AuthError as e:
            self.message.setText(str(e))
            return
        self.password.clear()
        self.confirm.clear()
        self.message.setText("")
        self.logged_in.emit(result)
