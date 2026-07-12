from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class SilentDialog(QDialog):
    def __init__(self, parent, title, message, kind="info"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(460, 230)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(16)

        row = QHBoxLayout()
        icon = QLabel("✓" if kind == "info" else "!")
        icon.setObjectName("DialogIconInfo" if kind == "info" else "DialogIconWarn")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(48, 48)

        text = QLabel(message)
        text.setWordWrap(True)
        text.setObjectName("DialogText")

        row.addWidget(icon)
        row.addSpacing(14)
        row.addWidget(text, 1)
        root.addLayout(row, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        ok.setFixedWidth(118)
        button_row.addWidget(ok)
        root.addLayout(button_row)

        self.setStyleSheet("""
        QDialog { background: white; border-radius: 16px; }
        #DialogText { color: #111827; font-family: "Microsoft YaHei UI"; font-size: 14px; line-height: 150%; }
        #DialogIconInfo { background: #6D5DF6; color: white; border-radius: 24px; font-size: 24px; font-weight: 900; }
        #DialogIconWarn { background: #F59E0B; color: white; border-radius: 24px; font-size: 24px; font-weight: 900; }
        QPushButton { background: #6D5DF6; color: white; border: none; border-radius: 10px; padding: 10px 16px; font-weight: 700; font-family: "Microsoft YaHei UI"; }
        QPushButton:hover { background: #5B4CE0; }
        """)


def show_info(parent, title, message):
    return SilentDialog(parent, title, message, "info").exec()


def show_warning(parent, title, message):
    return SilentDialog(parent, title, message, "warning").exec()
