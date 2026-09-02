"""Dark theme for PyQt6 Escáner Notarial"""

DARK_THEME = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QLabel {
    color: #e0e0e0;
    background: transparent;
}

QLabel#title {
    font-size: 24px;
    font-weight: bold;
    color: #00d4ff;
}

QLabel#subtitle {
    font-size: 12px;
    color: #888;
}

QLineEdit {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 10px 14px;
    color: #e0e0e0;
    font-size: 14px;
    min-height: 20px;
}

QLineEdit:focus {
    border: 1px solid #00d4ff;
}

QLineEdit::placeholder {
    color: #555;
}

QPushButton {
    background-color: #0f3460;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    color: #e0e0e0;
    font-size: 14px;
    font-weight: bold;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #1a4a8a;
}

QPushButton:pressed {
    background-color: #0a2540;
}

QPushButton:disabled {
    background-color: #2a2a3e;
    color: #555;
}

QPushButton#primary {
    background-color: #00d4ff;
    color: #1a1a2e;
}

QPushButton#primary:hover {
    background-color: #00b8e6;
}

QPushButton#danger {
    background-color: #e74c3c;
    color: white;
}

QPushButton#danger:hover {
    background-color: #c0392b;
}

QPushButton#success {
    background-color: #27ae60;
    color: white;
}

QPushButton#success:hover {
    background-color: #219a52;
}

QComboBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 13px;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid #00d4ff;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #888;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #0f3460;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    padding: 4px;
}

QProgressBar {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    text-align: center;
    color: #e0e0e0;
    min-height: 20px;
}

QProgressBar::chunk {
    background-color: #00d4ff;
    border-radius: 5px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #0f3460;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #1a4a8a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1a1a2e;
    height: 10px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #0f3460;
    border-radius: 5px;
    min-width: 30px;
}

QFrame#sidebar {
    background-color: #16213e;
    border-right: 1px solid #0f3460;
}

QFrame#card {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 8px;
}

QSpinBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 13px;
    min-height: 20px;
}

QSpinBox:focus {
    border: 1px solid #00d4ff;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #0f3460;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #1a4a8a;
}

QSpinBox::up-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #888;
}

QSpinBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888;
}

QToolTip {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #00d4ff;
    border-radius: 4px;
    padding: 6px;
}

QStatusBar {
    background-color: #16213e;
    color: #888;
    border-top: 1px solid #0f3460;
}
"""
