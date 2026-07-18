from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout


_DIALOG_STYLE = """
QDialog { background: #1E293B; color: #F8FAFC; border: 1px solid #475569; border-radius: 12px; }
QLabel { color: #F8FAFC; font-family: \"Microsoft YaHei UI\"; }
QPushButton { background: #334155; color: #F8FAFC; border: 1px solid #64748B; border-radius: 8px; padding: 8px 14px; font-family: \"Microsoft YaHei UI\"; font-weight: 600; }
QPushButton:hover { background: #475569; }
QPushButton#PrimaryButton { background: #2563EB; border-color: #3B82F6; color: #FFFFFF; }
QPushButton#PrimaryButton:hover { background: #1D4ED8; }
QProgressBar { background: #0F172A; color: #FFFFFF; border: 1px solid #64748B; border-radius: 6px; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #3B82F6; border-radius: 5px; }
"""


class UpdateConfirmDialog(QDialog):
    update_requested = Signal()
    later_requested = Signal()

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setModal(True)
        self.setMinimumWidth(440)
        version = str(update_info.get("latest_version", "")).strip()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        title = QLabel("发现可用更新")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        message = QLabel(f"检测到新版本 {version or '未知版本'}。更新会在确认后下载并校验安装包。")
        message.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(message)
        buttons = QHBoxLayout()
        buttons.addStretch()
        later = QPushButton("稍后")
        update = QPushButton("现在更新")
        update.setObjectName("PrimaryButton")
        later.clicked.connect(self._choose_later)
        update.clicked.connect(self._choose_update)
        buttons.addWidget(later)
        buttons.addWidget(update)
        layout.addLayout(buttons)
        self.setStyleSheet(_DIALOG_STYLE)

    def _choose_update(self):
        self.update_requested.emit()
        self.accept()

    def _choose_later(self):
        self.later_requested.emit()
        self.reject()


class UpdateProgressDialog(QDialog):
    retry_requested = Signal()
    close_requested = Signal()
    restart_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在准备更新")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        self.title_label = QLabel("正在准备更新")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.message_label = QLabel("正在等待更新任务开始...")
        self.message_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.retry_button = QPushButton("重试")
        self.close_button = QPushButton("关闭")
        self.restart_button = QPushButton("确认并重启")
        self.restart_button.setObjectName("PrimaryButton")
        self.retry_button.setVisible(False)
        self.restart_button.setVisible(False)
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.close_button.clicked.connect(self._close)
        self.restart_button.clicked.connect(self.restart_requested.emit)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.restart_button)
        layout.addLayout(buttons)
        self.setStyleSheet(_DIALOG_STYLE)

    def show_progress(self, event):
        message = str(event.get("message", "正在准备更新..."))
        downloaded = event.get("downloaded_bytes")
        total = event.get("total_bytes")
        self.title_label.setText("正在准备更新")
        self.message_label.setText(message)
        self.retry_button.setVisible(False)
        self.restart_button.setVisible(False)
        self.close_button.setText("关闭")
        if total is None or not isinstance(total, int) or total <= 0:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setTextVisible(False)
            return
        downloaded = max(0, int(downloaded or 0))
        percent = min(100, round(downloaded * 100 / total))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat(f"{percent}%")

    def show_result(self, result):
        message = str(result.get("message", "更新任务已结束。"))
        if result.get("ok"):
            self.title_label.setText("更新已准备完成")
            self.message_label.setText(message)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat("100%")
            self.retry_button.setVisible(False)
            self.restart_button.setVisible(True)
            self.close_button.setText("关闭")
            return
        self.title_label.setText("更新准备失败")
        self.message_label.setText(message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("失败")
        self.retry_button.setVisible(True)
        self.restart_button.setVisible(False)
        self.close_button.setText("关闭")

    def _close(self):
        self.close_requested.emit()
        self.reject()
