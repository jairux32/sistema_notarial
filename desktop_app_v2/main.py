"""Escaner Notarial - PyQt6 Desktop Application"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt6.QtCore import Qt

from ui.styles import DARK_THEME
from ui.login_window import LoginWindow
from ui.scanner_window import ScannerWindow
from ui.documents_window import DocumentsWindow
from services.api_client import APIClient
from services.session_manager import SessionManager
from services.scanner_service import ScannerService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escaner Notarial - Sistema Notarial")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 750)

        self.api = APIClient()
        self.session = SessionManager()
        self.scanner = ScannerService()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_window = LoginWindow(self.api, self.session)
        self.login_window.login_success.connect(self._on_login_success)

        self.stack.addWidget(self.login_window)

        self.scanner_window = None
        self.documents_window = None

    def show_login(self):
        self.stack.setCurrentWidget(self.login_window)

    def _on_login_success(self, user_data, token):
        self.scanner_window = ScannerWindow(self.api, self.scanner, user_data)
        self.scanner_window.back_to_login.connect(self._on_logout)

        self.documents_window = DocumentsWindow(self.api, os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'processed'
        ))
        self.documents_window.back_to_scanner.connect(
            lambda: self.stack.setCurrentWidget(self.scanner_window)
        )

        if self.stack.count() > 1:
            self.stack.removeWidget(self.stack.widget(1))
            self.stack.removeWidget(self.stack.widget(1))

        self.stack.addWidget(self.scanner_window)
        self.stack.addWidget(self.documents_window)
        self.stack.setCurrentWidget(self.scanner_window)

    def _on_logout(self):
        self.session.clear()
        self.api.token = None
        self.api.user = None

        if self.stack.count() > 1:
            self.stack.removeWidget(self.stack.widget(1))
            if self.stack.count() > 1:
                self.stack.removeWidget(self.stack.widget(1))

        self.scanner_window = None
        self.documents_window = None
        self.stack.setCurrentWidget(self.login_window)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    app.setStyle('Fusion')

    window = MainWindow()

    if not window.login_window.try_auto_login():
        window.show_login()

    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
