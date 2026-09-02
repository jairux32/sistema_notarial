"""Login window for Escaner Notarial"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class LoginWorker(QThread):
    finished = pyqtSignal(bool, object, str)

    def __init__(self, api_client, username, password):
        super().__init__()
        self.api = api_client
        self.username = username
        self.password = password

    def run(self):
        success, user, error = self.api.login(self.username, self.password)
        self.finished.emit(success, user, error)


class LoginWindow(QWidget):
    login_success = pyqtSignal(object, str)

    def __init__(self, api_client, session_manager):
        super().__init__()
        self.api = api_client
        self.session = session_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        title = QLabel("Sistema Notarial")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Escaner - Inicio de Sesion")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(30)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")
        self.username_input.setMinimumHeight(44)
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contrasena")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(44)
        self.password_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.password_input)

        layout.addSpacing(10)

        self.login_btn = QPushButton("Iniciar Sesion")
        self.login_btn.setObjectName("primary")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _on_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self.status_label.setText("Ingrese usuario y contrasena")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Conectando...")
        self.status_label.setText("")

        self.worker = LoginWorker(self.api, username, password)
        self.worker.finished.connect(self._on_login_result)
        self.worker.start()

    def _on_login_result(self, success, user, error):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Iniciar Sesion")

        if success:
            self.session.save(self.api.token, user)
            self.login_success.emit(user, self.api.token)
        else:
            self.status_label.setText(error)
            self.status_label.setStyleSheet("color: #e74c3c;")

    def try_auto_login(self):
        token, user = self.session.load()
        if token and user:
            self.api.token = token
            self.api.user = user
            if self.api.is_server_available():
                self.login_success.emit(user, token)
                return True
            else:
                self.login_success.emit(user, token)
                return True
        return False
