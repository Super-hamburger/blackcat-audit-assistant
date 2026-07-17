import sys
import time
from pathlib import Path
from core.path_manager import PathManager

from PySide6.QtCore import QEvent, Qt, QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QCheckBox, QSpinBox, QTextEdit, QProgressBar,
    QFrame, QGridLayout, QStackedWidget, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QInputDialog, QDialog, QComboBox,
    QApplication, QMenu, QMessageBox, QSystemTrayIcon
)

from core.config_manager import ConfigManager
from core.app_logger import AppLogger
from core.sound_engine import SoundEngine
from core.task_manager import TaskManager
from core.modules.module_registry import ModuleRegistry
from core.data_manager import DataManager
from core.changelog_manager import ChangelogManager
from core.resource_manager import ResourceManager
from core.version_manager import VersionManager
from core.plugin_manager import PluginManager
from core.i18n_manager import I18nManager
from core.update_manager import UpdateManager
from core.update_installer import UpdateInstaller
from core.update_notification import UpdateCheckWorker, UpdateNotificationState
from ui.widgets.silent_dialog import show_info, show_warning
from modules.scan_check.module import ScanCheckService


APP_TITLE = "黑猫审单助手"
APP_VERSION = "4.4.3"
APP_BRAND = "MADE IN チュウ ビョ"
SCAN_AUTO_SUBMIT_DELAY_MS = 150
SCAN_AUTO_SUBMIT_MIN_LENGTH = 4
SCAN_AUTO_SUBMIT_MAX_DURATION_MS = 1000


def activate_english_keyboard_layout():
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        layout = user32.LoadKeyboardLayoutW("00000409", 1)
        return bool(layout and user32.ActivateKeyboardLayout(layout, 0))
    except (AttributeError, OSError):
        return False


def file_paste_success_message(result):
    output_paths = result.get("output_paths", [])
    names = "\n".join(f"- {Path(path).name}" for path in output_paths)
    return (
        "黑猫上传表生成完成。"
        f"\n识别格式：{result.get('source_type', '')}"
        f"\n生成行数：{result['row_count']}"
        f"\n生成文件：{result.get('file_count', len(output_paths))} 份"
        f"\n输出文件夹：{result.get('output_dir', result.get('output_path', ''))}"
        f"\n黄色标记地址拆分：{result.get('split_count', 0)} 行"
        f"\n红色标记字段为空：{result.get('missing_count', 0)} 行"
        f"\n地址超长已放入O列：{result.get('address_overflow_count', 0)} 行"
        f"\nSKU数量待确认：{result.get('quantity_issue_count', 0)} 行"
        f"\n\n生成文件：\n{names}"
        "\n\n已自动打开输出文件夹。"
    )


class ExcelConversionWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, module_registry, context):
        super().__init__()
        self.module_registry = module_registry
        self.context = context

    def run(self):
        from modules.file_paste.converter import ConversionCancelled

        try:
            context = {**self.context, "progress_callback": self.progress.emit}
            module_result = self.module_registry.run("file_paste", context)
            if not module_result.ok or not module_result.data:
                raise RuntimeError(module_result.message)
            self.finished.emit(module_result.data)
        except ConversionCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))


class LabelPrintingWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, module_registry, context):
        super().__init__()
        self.module_registry = module_registry
        self.context = context

    def run(self):
        try:
            context = {**self.context, "progress_callback": self.progress.emit}
            module_result = self.module_registry.run("label_printing", context)
            if not module_result.ok or not module_result.data:
                raise RuntimeError(module_result.message)
            self.finished.emit(module_result.data)
        except Exception as error:
            self.failed.emit(str(error))


class ExcelProgressDialog(QDialog):
    """Keeps the task controls visible when the user presses Escape."""

    def reject(self):
        return


class ScrollPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("PageScroll")

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 8, 0)
        self.content_layout.setSpacing(14)
        self.setWidget(self.content)

    def layout(self):
        return self.content_layout


class ScanInputController(QObject):
    def __init__(self, input_widget, submit_callback):
        super().__init__(input_widget)
        self.input_widget = input_widget
        self.submit_callback = submit_callback
        self.input_widget.setInputMethodHints(Qt.ImhLatinOnly | Qt.ImhPreferLowercase)
        self.first_input_at = None
        self.last_input_at = None
        self.auto_submit_timer = QTimer(self)
        self.auto_submit_timer.setSingleShot(True)
        self.auto_submit_timer.setInterval(SCAN_AUTO_SUBMIT_DELAY_MS)
        self.auto_submit_timer.timeout.connect(self.submit_if_fast_input)
        self.input_widget.textEdited.connect(self.on_text_edited)
        self.input_widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.input_widget and event.type() == QEvent.FocusIn:
            activate_english_keyboard_layout()
        if (
            watched is self.input_widget
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter)
        ):
            self.submit()
            return True
        return super().eventFilter(watched, event)

    def on_text_edited(self, text):
        if not text:
            self.cancel()
            return

        now = time.monotonic()
        if self.first_input_at is None:
            self.first_input_at = now
        self.last_input_at = now
        if len(text) >= SCAN_AUTO_SUBMIT_MIN_LENGTH:
            self.auto_submit_timer.start()

    def submit_if_fast_input(self):
        elapsed_ms = int((self.last_input_at - self.first_input_at) * 1000) if self.last_input_at else 0
        if (
            len(self.input_widget.text()) >= SCAN_AUTO_SUBMIT_MIN_LENGTH
            and elapsed_ms <= SCAN_AUTO_SUBMIT_MAX_DURATION_MS
        ):
            self.submit()

    def submit(self):
        self.auto_submit_timer.stop()
        self.first_input_at = None
        self.last_input_at = None
        self.submit_callback()
        self.input_widget.setFocus()

    def cancel(self):
        self.auto_submit_timer.stop()
        self.first_input_at = None
        self.last_input_at = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.app_dir = Path(__file__).resolve().parents[1]
        self.config = ConfigManager(PathManager.data_dir() / "settings.json")
        self.settings = self.config.load()
        self.logger = AppLogger(PathManager.logs_dir())
        self.sound_engine = SoundEngine()
        self.task_manager = TaskManager()
        self.module_registry = ModuleRegistry()
        self.resources = ResourceManager(self.app_dir)
        self.version_manager = VersionManager(self.app_dir / "version.json")
        self.plugin_manager = PluginManager(self.app_dir / "plugins")
        self.i18n_manager = I18nManager(self.app_dir / "locales", self.settings.get("language", "zh_CN"))
        self.update_manager = UpdateManager(APP_VERSION, self.app_dir / "updater" / "update_manifest.example.json")
        self.update_installer = UpdateInstaller()
        self.data_manager = DataManager(PathManager.data_dir())
        self.changelog_manager = ChangelogManager(self.app_dir / "data" / "changelog.json")
        self.scan_service = ScanCheckService()
        self.update_notification_state = UpdateNotificationState()
        self.latest_update_info = None
        self.update_check_thread = None
        self.update_check_worker = None
        self.excel_conversion_thread = None
        self.excel_conversion_worker = None
        self.label_printing_thread = None
        self.label_printing_worker = None
        self.excel_progress_dialog = None
        self.excel_progress_bar = None
        self.excel_progress_status = None
        self.excel_pause_button = None
        self.excel_cancel_button = None
        self.excel_conversion_control = None
        self.excel_conversion_cancelled = False
        self.excel_quit_after_cancellation = False
        self.excel_pending_result = None
        self.excel_pending_error = None
        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(6 * 60 * 60 * 1000)
        self.auto_update_timer.timeout.connect(self.start_background_update_check)

        self.excel_source = ""
        self.nav_buttons = []
        self.avatar_click_count = 0
        self.force_quit = False
        self.tray_notice_shown = False
        self.tray_icon = None
        self.app_icon = self.load_app_icon()

        self.setWindowTitle(f"{APP_TITLE} {APP_VERSION}")
        if not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)
        self.resize(1320, 850)
        self.setMinimumSize(1160, 760)

        self.build_ui()
        self.setup_tray_icon()
        self.connect_task_signals()
        self.apply_style()
        self.apply_current_theme()
        self.preload_sounds()
        self.setup_auto_update_checks()

        self.add_pdf_log("INFO", "程序启动，版本：" + APP_VERSION)
        self.add_pdf_log("INFO", "V4.0.0 Enterprise Migration：完整功能已迁移到正式架构。")

    def load_app_icon(self):
        candidates = [
            self.app_dir / "assets" / "icons" / "blackcat_app.ico",
            self.app_dir / "assets" / "icons" / "blackcat_app.png",
            self.app_dir / "assets" / "icons" / "blackcat_avatar.png",
        ]
        for path in candidates:
            if path.exists():
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon
        return QIcon()

    def setup_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable() or self.app_icon.isNull():
            return

        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip(f"{APP_TITLE} {APP_VERSION}")

        tray_menu = QMenu(self)
        tray_menu.setStyleSheet("""
            QMenu {
                background: #FFFFFF;
                color: #111827;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                font-weight: 700;
            }
            QMenu::item {
                color: #111827;
                background: transparent;
                padding: 8px 26px 8px 14px;
                border-radius: 6px;
                min-width: 112px;
            }
            QMenu::item:selected {
                background: #EEF2FF;
                color: #4F46E5;
            }
            QMenu::separator {
                height: 1px;
                background: #E5E7EB;
                margin: 6px 4px;
            }
        """)
        show_action = QAction("打开主窗口", self)
        show_action.triggered.connect(self.restore_from_tray)

        update_action = QAction("检查更新", self)
        update_action.triggered.connect(self.check_update_status)

        quit_action = QAction("退出软件", self)
        quit_action.triggered.connect(self.quit_from_tray)

        tray_menu.addAction(show_action)
        tray_menu.addAction(update_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.messageClicked.connect(self.open_update_settings)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        if self.excel_conversion_thread and self.excel_conversion_thread.isRunning():
            self.excel_quit_after_cancellation = True
            if self.excel_conversion_control:
                self.excel_conversion_control.cancel()
            if self.excel_pause_button:
                self.excel_pause_button.setEnabled(False)
            if self.excel_cancel_button:
                self.excel_cancel_button.setEnabled(False)
            if self.excel_progress_status:
                self.excel_progress_status.setText("正在结束任务，完成后将退出软件...")
            return

        self.finish_application_quit()

    def finish_application_quit(self):
        self.force_quit = True
        self.save_settings()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(250)
        root_layout.addWidget(self.sidebar)

        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(18, 18, 18, 20)
        side.setSpacing(8)

        avatar = QLabel()
        avatar.setObjectName("AvatarImage")
        avatar.setAlignment(Qt.AlignCenter)
        avatar_path = self.app_dir / "assets" / "icons" / "blackcat_avatar.png"
        pixmap = QPixmap(str(avatar_path))
        if not pixmap.isNull():
            avatar.setPixmap(pixmap.scaled(210, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            avatar.setText("🐈‍⬛")
        avatar.mousePressEvent = self.on_avatar_clicked
        side.addWidget(avatar)

        name = QLabel(APP_TITLE)
        name.setObjectName("SidebarTitle")
        name.setAlignment(Qt.AlignCenter)
        side.addWidget(name)

        brand = QLabel(APP_BRAND)
        brand.setObjectName("BrandText")
        brand.setAlignment(Qt.AlignCenter)
        side.addWidget(brand)

        side.addSpacing(8)

        self.add_nav_button(side, "🏠  主页", 0)
        self.add_nav_button(side, "📋  文件粘贴", 1)
        self.add_nav_button(side, "📦  面单压缩", 2)
        self.add_nav_button(side, "🖨  面单打印", 3)
        self.add_nav_button(side, "🔍  扫码验单", 4)

        self.add_separator(side)

        self.add_nav_button(side, "📑  处理记录", 5)
        self.add_nav_button(side, "📊  数据统计", 6)
        self.add_nav_button(side, "⭐  收藏模板", 7)

        self.add_separator(side)

        self.add_nav_button(side, "⚙  设置", 8)
        self.add_nav_button(side, "📖  帮助文档", 9)
        self.add_nav_button(side, "🆕  更新日志", 10)
        self.add_nav_button(side, "ℹ  关于我们", 11)

        side.addStretch()

        status = QLabel("● 准备就绪")
        status.setObjectName("SidebarStatus")
        side.addWidget(status)

        self.main = QFrame()
        self.main.setObjectName("Main")
        root_layout.addWidget(self.main, 1)

        main = QVBoxLayout(self.main)
        main.setContentsMargins(28, 22, 28, 16)
        main.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_label = QLabel(f"{APP_TITLE}  <span style='color:#6D5DF6'>{APP_BRAND}</span>")
        self.title_label.setObjectName("Title")
        self.subtitle_label = QLabel("主页")
        self.subtitle_label.setObjectName("Subtitle")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        header.addLayout(title_box)
        header.addStretch()
        self.theme_button = self.small_button("🌙  主题")
        self.theme_button.clicked.connect(self.show_theme_center)
        self.settings_button = self.small_button("⚙  设置")
        self.settings_button.clicked.connect(lambda: self.set_page(8))
        header.addWidget(self.theme_button)
        header.addWidget(self.settings_button)
        main.addLayout(header)

        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)

        self.stack.addWidget(self.build_home_page())
        self.stack.addWidget(self.build_excel_page())
        self.stack.addWidget(self.build_pdf_page())
        self.stack.addWidget(self.build_label_printing_page())
        self.stack.addWidget(self.build_scan_check_page())
        self.stack.addWidget(self.build_history_page())
        self.stack.addWidget(self.build_statistics_page())
        self.stack.addWidget(self.build_templates_page())
        self.stack.addWidget(self.build_settings_page())
        self.stack.addWidget(self.build_help_page())
        self.stack.addWidget(self.build_changelog_page())
        self.stack.addWidget(self.build_about_page())

        self.set_page(0)

    def add_separator(self, layout):
        line = QFrame()
        line.setObjectName("SideSeparator")
        line.setFixedHeight(1)
        layout.addWidget(line)

    def add_nav_button(self, layout, text, index):
        button = QPushButton(text)
        button.setObjectName("SideButton")
        button.clicked.connect(lambda: self.set_page(index))
        self.nav_buttons.append(button)
        layout.addWidget(button)

    def set_page(self, index):
        self.stack.setCurrentIndex(index)
        titles = [
            ("主页", "欢迎回来，选择左侧功能开始工作。"),
            ("文件粘贴", "支持一件代发 Excel 和黑猫新版 Excel，自动生成黑猫上传表。"),
            ("面单压缩", "支持多 PDF 批量选择，自动识别单号、拆分、重命名、分组压缩。"),
            ("面单打印", "按客户、面单类型和货架顺序生成可直接打印的 PDF。"),
            ("扫码验单", "本机扫码核对出库单号和 SKU，异常立即拦截。"),
            ("处理记录", "查看历史任务、输出目录、错误报告和重新打开任务。"),
            ("数据统计", "查看今日、本周、本月处理数量和效率。"),
            ("收藏模板", "保存常用模板、默认目录和常用处理方案。"),
            ("设置", "管理声音、输出目录、主题和处理参数。"),
            ("帮助文档", "查看第一次使用教程和常见问题。"),
            ("更新日志", "查看版本更新内容。"),
            ("关于我们", "软件信息和制作信息。"),
        ]
        self.subtitle_label.setText(titles[index][1])

        if index == 0 and hasattr(self, "home_recent_table"):
            self.refresh_dashboard()
        elif index == 5 and hasattr(self, "history_table"):
            self.refresh_history()
        elif index == 6 and hasattr(self, "stats_detail_text"):
            self.refresh_statistics()
        elif index == 7 and hasattr(self, "templates_table"):
            self.refresh_templates()

        for i, button in enumerate(self.nav_buttons):
            button.setProperty("active", i == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def build_home_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        welcome = self.create_card("欢迎使用黑猫审单助手")
        welcome_text = QLabel("Alpha16 已开始记录你的处理历史，并统计每日/月度数据。")
        welcome_text.setObjectName("BodyText")
        welcome_text.setWordWrap(True)
        welcome.layout().addWidget(welcome_text)

        quick = QHBoxLayout()
        excel_btn = QPushButton("📋  文件粘贴")
        excel_btn.setObjectName("ExcelButton")
        excel_btn.clicked.connect(lambda: self.set_page(1))
        pdf_btn = QPushButton("📦  面单压缩")
        pdf_btn.setObjectName("PrimaryButton")
        pdf_btn.clicked.connect(lambda: self.set_page(2))
        label_btn = QPushButton("🖨  面单打印")
        label_btn.clicked.connect(lambda: self.set_page(3))
        scan_btn = QPushButton("🔍  扫码验单")
        scan_btn.clicked.connect(lambda: self.set_page(4))
        history_btn = QPushButton("📑  处理记录")
        history_btn.clicked.connect(lambda: self.set_page(5))
        quick.addWidget(excel_btn)
        quick.addWidget(pdf_btn)
        quick.addWidget(label_btn)
        quick.addWidget(scan_btn)
        quick.addWidget(history_btn)
        welcome.layout().addLayout(quick)
        layout.addWidget(welcome)

        self.home_info_row = QHBoxLayout()
        self.home_info_row.setSpacing(14)
        self.home_today_card = self.info_card("今日处理", "0", "今日处理总数")
        self.home_month_card = self.info_card("本月处理", "0", "本月累计处理")
        self.home_fast_card = self.info_card("最快速度", "--", "历史最高页/秒")
        self.home_info_row.addWidget(self.home_today_card)
        self.home_info_row.addWidget(self.home_month_card)
        self.home_info_row.addWidget(self.home_fast_card)
        layout.addLayout(self.home_info_row)

        recent_card = self.create_card("最近处理记录")
        self.home_recent_table = QTableWidget(0, 5)
        self.home_recent_table.setObjectName("DataTable")
        self.home_recent_table.setAlternatingRowColors(True)
        self.home_recent_table.verticalHeader().setVisible(False)
        self.home_recent_table.setHorizontalHeaderLabels(["时间", "功能", "数量", "成功", "输出"])
        self.home_recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.home_recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        recent_card.layout().addWidget(self.home_recent_table)
        layout.addWidget(recent_card, 1)

        self.refresh_dashboard()
        return page

    def build_excel_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        intro = self.create_card("📋 文件粘贴工作台")
        desc = QLabel("选择源 Excel，设置输出位置，然后生成黑猫上传表。支持一件代发 Excel 和黑猫新版 Excel。")
        desc.setObjectName("BodyText")
        desc.setWordWrap(True)
        intro.layout().addWidget(desc)
        layout.addWidget(intro)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        layout.addLayout(workspace)

        input_card = self.create_card("1. 输入与输出")
        input_card.layout().addLayout(self.section_label("源 Excel"))

        row = QHBoxLayout()
        row.setSpacing(10)
        self.excel_input = QLineEdit()
        self.excel_input.setPlaceholderText("请选择一件代发或黑猫新版 Excel（.xlsx / .xlsm）")
        choose_btn = QPushButton("📁  选择 Excel")
        choose_btn.setObjectName("ToolButton")
        choose_btn.clicked.connect(self.select_upload_excel)
        row.addWidget(self.excel_input, 1)
        row.addWidget(choose_btn)
        input_card.layout().addLayout(row)

        input_card.layout().addLayout(self.section_label("输出位置"))

        out_row = QHBoxLayout()
        out_row.setSpacing(10)
        self.excel_output_dir_input = QLineEdit()
        self.excel_output_dir_input.setPlaceholderText("不选择时默认保存到 BlackCatUploadTable")
        out_btn = QPushButton("📁  输出位置")
        out_btn.setObjectName("ToolButton")
        out_btn.clicked.connect(self.select_excel_output_dir)
        out_row.addWidget(self.excel_output_dir_input, 1)
        out_row.addWidget(out_btn)
        input_card.layout().addLayout(out_row)

        input_card.layout().addLayout(self.section_label("生成结果"))

        result_row = QHBoxLayout()
        result_row.setSpacing(10)
        self.excel_output_input = QLineEdit()
        self.excel_output_input.setPlaceholderText("生成后自动显示输出文件路径")
        self.excel_output_input.setReadOnly(True)
        result_row.addWidget(self.excel_output_input, 1)
        input_card.layout().addLayout(result_row)

        self.excel_generate_button = QPushButton("⬇  生成上传表")
        self.excel_generate_button.setObjectName("ExcelButton")
        self.excel_generate_button.clicked.connect(self.convert_upload_excel)
        input_card.layout().addWidget(self.excel_generate_button)
        workspace.addWidget(input_card, 3)

        log_card = self.create_card("2. 文件粘贴日志")
        self.excel_log_text = QTextEdit()
        self.excel_log_text.setReadOnly(True)
        self.excel_log_text.setObjectName("LogText")
        self.excel_log_text.setMinimumHeight(260)
        log_card.layout().addWidget(self.excel_log_text)
        workspace.addWidget(log_card, 2)

        layout.addStretch()
        return page

    def build_pdf_page(self):
        page = self.create_scroll_page()
        main = page.layout()

        intro = self.create_card("📦 面单压缩工作台")
        desc = QLabel("可一次选择多个 PDF，统一拆分、识别单号、重命名、按每组数量分文件夹并生成 ZIP。")
        desc.setObjectName("BodyText")
        desc.setWordWrap(True)
        intro.layout().addWidget(desc)
        main.addWidget(intro)

        task_row = QHBoxLayout()
        task_row.setSpacing(14)
        main.addLayout(task_row)

        config_card = self.create_card("1. 任务配置")
        config_card.layout().addLayout(self.section_label("面单 PDF"))

        pdf_row = QHBoxLayout()
        pdf_row.setSpacing(10)
        self.pdf_input = QLineEdit()
        self.pdf_input.setPlaceholderText("请选择一个或多个面单 PDF 文件")
        pdf_btn = QPushButton("📁  选择 PDF")
        pdf_btn.setObjectName("ToolButton")
        pdf_btn.clicked.connect(self.select_pdf)
        pdf_row.addWidget(self.pdf_input, 1)
        pdf_row.addWidget(pdf_btn)
        config_card.layout().addLayout(pdf_row)

        config_card.layout().addLayout(self.section_label("输出目录"))
        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        self.output_input = QLineEdit()
        self.output_input.setText(str(self.settings.get("last_output_dir", "")) or str(PathManager.output_dir()))
        self.output_input.setPlaceholderText("请选择输出目录")
        output_btn = QPushButton("📁  浏览")
        output_btn.setObjectName("ToolButton")
        output_btn.clicked.connect(self.select_output_dir)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(output_btn)
        config_card.layout().addLayout(output_row)

        config_card.layout().addLayout(self.section_label("处理参数"))
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(12)
        settings_grid.setVerticalSpacing(10)
        settings_grid.addWidget(QLabel("每个文件夹最多 PDF 数："), 0, 0)
        self.batch_size = QSpinBox()
        self.batch_size.setRange(1, 9999)
        self.batch_size.setValue(int(self.settings.get("batch_size", 90)))
        settings_grid.addWidget(self.batch_size, 0, 1)

        self.auto_zip = QCheckBox("自动压缩 ZIP")
        self.auto_zip.setChecked(bool(self.settings.get("auto_zip", True)))
        settings_grid.addWidget(self.auto_zip, 1, 0)

        self.open_output = QCheckBox("完成后打开输出目录")
        self.open_output.setChecked(bool(self.settings.get("open_output", True)))
        settings_grid.addWidget(self.open_output, 1, 1)

        self.sound_enabled = QCheckBox("完成提示音")
        self.sound_enabled.setChecked(bool(self.settings.get("sound_enabled", True)))
        settings_grid.addWidget(self.sound_enabled, 2, 0)
        config_card.layout().addLayout(settings_grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.start_button = QPushButton("▶  开始处理")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_process)
        self.cancel_button = QPushButton("■  停止")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_process)
        action_row.addWidget(self.start_button, 1)
        action_row.addWidget(self.cancel_button, 1)
        config_card.layout().addLayout(action_row)
        task_row.addWidget(config_card, 3)

        status_card = self.create_card("2. 进度与统计")

        status_card.layout().addLayout(self.section_label("整体进度"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        status_card.layout().addWidget(self.progress_bar)

        progress_meta = QGridLayout()
        progress_meta.setHorizontalSpacing(12)
        progress_meta.setVerticalSpacing(8)
        self.progress_processed = QLabel("已处理：0 / 0")
        self.progress_remaining = QLabel("预计剩余：00:00:00")
        self.progress_speed = QLabel("速度：0.00 页/秒")
        self.progress_elapsed = QLabel("已用时：00:00:00")
        progress_meta.addWidget(self.progress_processed, 0, 0)
        progress_meta.addWidget(self.progress_remaining, 0, 1)
        progress_meta.addWidget(self.progress_speed, 1, 0)
        progress_meta.addWidget(self.progress_elapsed, 1, 1)
        status_card.layout().addLayout(progress_meta)

        status_card.layout().addLayout(self.section_label("任务统计"))
        self.stats_labels = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        items = [
            ("📄 总页数", "total"),
            ("📑 已处理", "current"),
            ("✅ 成功", "success"),
            ("⚠ 失败", "failed"),
            ("🚀 速度", "speed"),
            ("⏱ 耗时", "elapsed"),
            ("🔁 重复", "duplicate"),
            ("⏳ 剩余", "remaining"),
        ]
        for index, (label, key) in enumerate(items):
            row = index // 2
            col = (index % 2) * 2
            grid.addWidget(QLabel(label + "："), row, col)
            value = QLabel("0")
            value.setObjectName("StatValue")
            self.stats_labels[key] = value
            grid.addWidget(value, row, col + 1)
        status_card.layout().addLayout(grid)
        task_row.addWidget(status_card, 2)

        log_card = self.create_card("3. 运行日志")
        log_row = QHBoxLayout()
        log_row.addStretch()
        clear_btn = QPushButton("清空日志")
        clear_btn.setObjectName("SmallButton")
        clear_btn.clicked.connect(self.clear_pdf_log)
        log_row.addWidget(clear_btn)
        log_card.layout().addLayout(log_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("LogText")
        self.log_text.setMinimumHeight(250)
        log_card.layout().addWidget(self.log_text)
        main.addWidget(log_card)

        return page

    def build_label_printing_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        intro = self.create_card("🖨 面单打印工作台")
        description = QLabel(
            "选择原始一件代发表、完整成品表和一个或多个黑猫面单 PDF，"
            "按货架顺序生成打印文件；原始 PDF 不会被修改。"
        )
        description.setObjectName("BodyText")
        description.setWordWrap(True)
        intro.layout().addWidget(description)
        layout.addWidget(intro)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        layout.addLayout(workspace)

        config_card = self.create_card("1. 文件与打印范围")
        self._add_label_printing_file_row(
            config_card, "原始一件代发表", "请选择原始一件代发 Excel（.xlsx）",
            "label_source_input", self.select_label_source,
        )
        self._add_label_printing_file_row(
            config_card, "完整成品表", "请选择完整成品 Excel（.xlsx）",
            "label_finished_input", self.select_label_finished,
        )
        self._add_label_printing_file_row(
            config_card, "黑猫面单 PDF", "可选择一个或多个面单 PDF",
            "label_pdf_input", self.select_label_pdfs,
        )

        config_card.layout().addLayout(self.section_label("输出目录（可选）"))
        output_row = QHBoxLayout()
        self.label_output_dir_input = QLineEdit()
        self.label_output_dir_input.setPlaceholderText("不选择时默认保存到 LabelPrinting 输出目录")
        output_button = QPushButton("📁  选择目录")
        output_button.setObjectName("ToolButton")
        output_button.clicked.connect(self.select_label_output_dir)
        self.label_output_dir_button = output_button
        output_row.addWidget(self.label_output_dir_input, 1)
        output_row.addWidget(output_button)
        config_card.layout().addLayout(output_row)

        config_card.layout().addLayout(self.section_label("打印规则"))
        rules = QGridLayout()
        rules.setHorizontalSpacing(12)
        rules.setVerticalSpacing(10)
        rules.addWidget(QLabel("打印范围："), 0, 0)
        self.label_scope_combo = QComboBox()
        self.label_scope_combo.addItem("全部客户一次打印", "all")
        self.label_scope_combo.addItem("按客户逐个打印", "by_customer")
        rules.addWidget(self.label_scope_combo, 0, 1)
        rules.addWidget(QLabel("面单类型："), 1, 0)
        self.label_split_types_combo = QComboBox()
        self.label_split_types_combo.addItem("合并宅急便和投函", False)
        self.label_split_types_combo.addItem("分开投函和宅急便", True)
        rules.addWidget(self.label_split_types_combo, 1, 1)
        self.label_open_after_checkbox = QCheckBox("完成后打开输出目录")
        self.label_open_after_checkbox.setChecked(True)
        rules.addWidget(self.label_open_after_checkbox, 2, 0, 1, 2)
        config_card.layout().addLayout(rules)

        self.label_start_button = QPushButton("▶  生成打印文件")
        self.label_start_button.setObjectName("PrimaryButton")
        self.label_start_button.clicked.connect(self.start_label_printing)
        config_card.layout().addWidget(self.label_start_button)
        self.label_printing_controls = [
            self.label_source_input, self.label_source_input_button,
            self.label_finished_input, self.label_finished_input_button,
            self.label_pdf_input, self.label_pdf_input_button,
            self.label_output_dir_input, self.label_output_dir_button,
            self.label_scope_combo, self.label_split_types_combo,
            self.label_open_after_checkbox, self.label_start_button,
        ]
        workspace.addWidget(config_card, 3)

        progress_card = self.create_card("2. 运行进度")
        self.label_progress_status = QLabel("等待选择文件。")
        self.label_progress_status.setObjectName("BodyText")
        self.label_progress_status.setWordWrap(True)
        progress_card.layout().addWidget(self.label_progress_status)
        self.label_progress_bar = QProgressBar()
        self.label_progress_bar.setValue(0)
        progress_card.layout().addWidget(self.label_progress_bar)
        progress_card.layout().addStretch()
        workspace.addWidget(progress_card, 2)

        log_card = self.create_card("3. 面单打印日志")
        self.label_log_text = QTextEdit()
        self.label_log_text.setObjectName("LogText")
        self.label_log_text.setReadOnly(True)
        self.label_log_text.setMinimumHeight(220)
        log_card.layout().addWidget(self.label_log_text)
        layout.addWidget(log_card)

        layout.addStretch()
        return page

    def _add_label_printing_file_row(
        self, card, title, placeholder, input_name, callback,
    ):
        card.layout().addLayout(self.section_label(title))
        row = QHBoxLayout()
        input_widget = QLineEdit()
        input_widget.setPlaceholderText(placeholder)
        setattr(self, input_name, input_widget)
        button = QPushButton("📁  选择文件")
        button.setObjectName("ToolButton")
        button.clicked.connect(callback)
        setattr(self, f"{input_name}_button", button)
        row.addWidget(input_widget, 1)
        row.addWidget(button)
        card.layout().addLayout(row)

    def build_scan_check_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        workbench = QHBoxLayout()
        workbench.setSpacing(16)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        scan_card = self.create_card("扫码输入")
        scan_header = QHBoxLayout()
        scan_header.setSpacing(8)
        scan_hint = QLabel("扫描出库单号或 SKU")
        scan_hint.setObjectName("ScanMutedText")
        scan_header.addWidget(scan_hint)
        scan_header.addStretch()
        import_btn = QPushButton("导入 Excel")
        import_btn.setObjectName("SmallButton")
        import_btn.clicked.connect(self.choose_scan_excel)
        rule_btn = QPushButton("字段规则")
        rule_btn.setObjectName("SmallButton")
        rule_btn.clicked.connect(self.show_scan_rule_info)
        self.scan_status_badge = QLabel("● 扫码枪已连接")
        self.scan_status_badge.setObjectName("ScanStatusBadge")
        self.scan_status_badge.setAlignment(Qt.AlignCenter)
        scan_header.addWidget(import_btn)
        scan_header.addWidget(rule_btn)
        scan_header.addWidget(self.scan_status_badge)
        scan_card.layout().addLayout(scan_header)

        self.scan_excel_path = QLineEdit()
        self.scan_excel_path.setPlaceholderText("选择包含出库单号、SKU、数量的 Excel 文件")
        self.scan_excel_path.setVisible(False)
        self.scan_order_column = QComboBox()
        self.scan_order_column.addItems(["出库单号列", "订单号", "参考单号", "单号"])
        self.scan_order_column.setVisible(False)
        self.scan_sku_column = QComboBox()
        self.scan_sku_column.addItems(["SKU 列", "商品编码", "品番", "条码"])
        self.scan_sku_column.setVisible(False)
        self.scan_qty_column = QComboBox()
        self.scan_qty_column.addItems(["数量列", "出库数量", "发货数量", "Qty"])
        self.scan_qty_column.setVisible(False)
        self.scan_match_mode = QComboBox()
        self.scan_match_mode.addItems(["严格匹配", "忽略大小写", "去空格后匹配"])
        self.scan_match_mode.setVisible(False)
        self.scan_sound_enabled = QCheckBox("声音提示")
        self.scan_sound_enabled.setChecked(True)
        self.scan_sound_enabled.setVisible(False)
        self.scan_block_enabled = QCheckBox("异常拦截")
        self.scan_block_enabled.setChecked(True)
        self.scan_block_enabled.setVisible(False)

        self.scan_input = QLineEdit()
        self.scan_input.setObjectName("ScanBigInput")
        self.scan_input.setPlaceholderText("▥   请扫描出库单号或 SKU")
        self.scan_input_controller = ScanInputController(self.scan_input, self.handle_scan_input)
        scan_card.layout().addWidget(self.scan_input)
        hint = QLabel("将光标放在输入框内，使用扫码枪扫描。当前导入批次仅作本机扫码核对依据，请以实时扫码提示为准。")
        hint.setObjectName("ScanMutedText")
        hint.setWordWrap(True)
        scan_card.layout().addWidget(hint)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.scan_start_button = QPushButton("开始验单")
        self.scan_start_button.setObjectName("PrimaryButton")
        self.scan_start_button.clicked.connect(self.start_scan_session)
        self.scan_pause_button = QPushButton("暂停")
        self.scan_pause_button.clicked.connect(self.pause_scan_session)
        self.scan_pause_button.setEnabled(False)
        action_row.addWidget(self.scan_start_button, 2)
        action_row.addWidget(self.scan_pause_button, 1)
        scan_card.layout().addLayout(action_row)
        left_panel.addWidget(scan_card)

        self.scan_progress_card = self.create_card("整体进度")
        self.scan_progress_card.setObjectName("ScanProgressCard")
        progress_row = QHBoxLayout()
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_percent_label = QLabel("已匹配 0 / 0（0%）")
        self.scan_percent_label.setObjectName("ScanLinkText")
        progress_row.addWidget(self.scan_progress_bar, 1)
        progress_row.addWidget(self.scan_percent_label)
        self.scan_progress_card.layout().addLayout(progress_row)

        metric_row = QHBoxLayout()
        metric_row.setSpacing(10)
        self.scan_metric_total_card = self.info_card("本机已扫", "0", "当前电脑扫码数")
        self.scan_metric_pass_card = self.info_card("通过", "0", "匹配成功")
        self.scan_metric_fail_card = self.info_card("异常", "0", "需要处理")
        self.scan_metric_rate_card = self.info_card("通过率", "--", "本机扫描结果")
        metric_row.addWidget(self.scan_metric_total_card)
        metric_row.addWidget(self.scan_metric_pass_card)
        metric_row.addWidget(self.scan_metric_fail_card)
        metric_row.addWidget(self.scan_metric_rate_card)
        left_panel.addWidget(self.scan_progress_card)

        current_card = self.create_card("当前验单信息")
        self.scan_order_hero_frame = QFrame()
        self.scan_order_hero_frame.setObjectName("ScanOrderHero")
        hero_layout = QVBoxLayout(self.scan_order_hero_frame)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(10)

        hero_content = QHBoxLayout()
        hero_content.setSpacing(18)

        order_col = QVBoxLayout()
        order_label = QLabel("出库单号")
        order_label.setObjectName("ScanFieldLabel")
        self.scan_order_label = order_label
        self.scan_current_order = QLabel("未选择")
        self.scan_current_order.setObjectName("ScanOrderHeroValue")
        self.scan_current_order.setWordWrap(True)
        self.scan_current_order.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scan_order_time = QLabel("出库时间：--")
        self.scan_order_time.setObjectName("ScanMutedText")
        order_col.addWidget(order_label)
        order_col.addWidget(self.scan_current_order)
        order_col.addWidget(self.scan_order_time)

        sku_col = QVBoxLayout()
        sku_label = QLabel("SKU")
        sku_label.setObjectName("ScanFieldLabel")
        self.scan_sku_label = sku_label
        self.scan_current_sku = QLabel("等待输入")
        self.scan_current_sku.setObjectName("ScanFieldValue")
        self.scan_product_name = QLabel("商品名称：--")
        self.scan_product_name.setObjectName("ScanMutedText")
        sku_col.addWidget(sku_label)
        sku_col.addWidget(self.scan_current_sku)
        sku_col.addWidget(self.scan_product_name)

        hero_content.addLayout(order_col, 2)
        hero_content.addLayout(sku_col, 2)
        hero_layout.addLayout(hero_content)

        success_box = QFrame()
        success_box.setObjectName("ScanSuccessBanner")
        success_layout = QHBoxLayout(success_box)
        success_layout.setContentsMargins(14, 10, 14, 10)
        self.scan_current_result = QLabel("等待开始")
        self.scan_current_result.setObjectName("ScanSuccessText")
        self.scan_success_time = QLabel("扫描时间  --")
        self.scan_success_time.setObjectName("ScanMutedText")
        success_layout.addWidget(self.scan_current_result)
        success_layout.addStretch()
        success_layout.addWidget(self.scan_success_time)
        hero_layout.addWidget(success_box)
        current_card.layout().addWidget(self.scan_order_hero_frame)

        preview_box = QLabel("商品\n图片")
        preview_box.setObjectName("ScanProductPreview")
        preview_box.setAlignment(Qt.AlignCenter)
        preview_box.setFixedSize(86, 76)
        preview_row = QHBoxLayout()
        preview_row.addStretch()
        preview_row.addWidget(preview_box)
        current_card.layout().addLayout(preview_row)
        self.set_scan_order_hero_style("ready")
        left_panel.addWidget(current_card)

        scan_metrics_card = self.create_card("本机扫码概况")
        scan_metrics_card.layout().addLayout(metric_row)
        left_panel.addWidget(scan_metrics_card)

        detail_card = self.create_card("出库单明细")
        detail_tip = QLabel("当前单据明细，扫码后逐行更新本机已扫数量。")
        detail_tip.setObjectName("ScanMutedText")
        detail_card.layout().addWidget(detail_tip)
        self.scan_detail_table = QTableWidget(0, 6)
        self.scan_detail_table.setObjectName("DataTable")
        self.scan_detail_table.setHorizontalHeaderLabels(["#", "SKU", "商品名称", "数量", "本机已扫", "状态"])
        self.scan_detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scan_detail_table.verticalHeader().setVisible(False)
        self.scan_detail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scan_detail_table.setMinimumHeight(190)
        detail_card.layout().addWidget(self.scan_detail_table)
        left_panel.addWidget(detail_card)

        workbench.addLayout(left_panel, 8)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        status_card = self.create_card("放行状态")
        pass_box = QFrame()
        pass_box.setObjectName("ScanRightStatus")
        self.scan_gate_frame = pass_box
        pass_layout = QHBoxLayout(pass_box)
        pass_layout.setContentsMargins(16, 16, 16, 16)
        pass_icon = QLabel("✓")
        pass_icon.setObjectName("ScanStatusIcon")
        pass_icon.setAlignment(Qt.AlignCenter)
        self.scan_gate_icon = pass_icon
        gate_text = QVBoxLayout()
        self.scan_gate_status = QLabel("放行中")
        self.scan_gate_status.setObjectName("ScanGateStatus")
        self.scan_gate_sub = QLabel("一扫正确，可以继续扫描")
        self.scan_gate_sub.setObjectName("ScanMutedText")
        gate_text.addWidget(self.scan_gate_status)
        gate_text.addWidget(self.scan_gate_sub)
        pass_layout.addWidget(pass_icon)
        pass_layout.addLayout(gate_text, 1)
        status_card.layout().addWidget(pass_box)
        right_panel.addWidget(status_card)

        result_card = self.create_card("最近扫描记录")
        view_all = QLabel("查看全部")
        view_all.setObjectName("ScanLinkText")
        view_all.setAlignment(Qt.AlignRight)
        result_card.layout().addWidget(view_all)
        self.scan_log_table = QTableWidget(0, 4)
        self.scan_log_table.setObjectName("DataTable")
        self.scan_log_table.setHorizontalHeaderLabels(["出库单号", "SKU", "时间", "结果"])
        self.scan_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scan_log_table.verticalHeader().setVisible(False)
        self.scan_log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scan_log_table.setMinimumHeight(230)
        result_card.layout().addWidget(self.scan_log_table)
        right_panel.addWidget(result_card)

        unmatched_export_btn = QPushButton("导出未匹配源数据")
        unmatched_export_btn.clicked.connect(self.export_scan_unmatched_source_rows)
        right_panel.addWidget(unmatched_export_btn)
        right_panel.addStretch()
        workbench.addLayout(right_panel, 4)
        layout.addLayout(workbench)
        layout.addStretch()
        return page

    def choose_scan_excel(self):
        self.play_click_sound()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择扫码验单 Excel",
            str(Path.home() / "Desktop"),
            "Excel 文件 (*.xlsx *.xlsm)"
        )
        if not path:
            return

        try:
            summary = self.scan_service.load_excel(path)
            self.scan_excel_path.setText(path)
            self.scan_status_badge.setText("● Excel 已导入")
            self.scan_start_button.setEnabled(True)
            self.scan_pause_button.setEnabled(False)
            self.scan_pause_button.setText("暂停")
            self.scan_current_result.setText(f"已导入 {summary['order_count']} 个出库单，{summary['item_count']} 个 SKU")
            self.scan_success_time.setText("导入时间  " + time.strftime("%H:%M:%S"))
            self.set_scan_status_visual("ready", "未开始", "点击开始验单后，先扫描出库单号。")
            self.update_scan_summary(summary)
            self.refresh_scan_detail_table([])
            self.refresh_scan_log_tables()
            self.scan_input.setFocus()
            self.sound_engine.play_import()
            show_info(self, "导入完成", f"已导入 {summary['order_count']} 个出库单，{summary['item_count']} 个 SKU。")
        except Exception as error:
            self.play_error_sound()
            show_warning(self, "导入失败", str(error))

    def start_scan_session(self):
        self.play_click_sound()
        result = self.scan_service.start()
        if result.get("status") == "error":
            self.play_error_sound()
            show_warning(self, "提示", result.get("message", "请先导入 Excel。"))
            return
        self.scan_status_badge.setText("● 验单中")
        self.scan_start_button.setEnabled(False)
        self.scan_pause_button.setEnabled(True)
        self.set_scan_status_visual("ready", "放行中", "一扫正确，可以继续扫描")
        self.apply_scan_result(result)
        self.scan_input.setFocus()

    def pause_scan_session(self):
        self.play_click_sound()
        result = self.scan_service.pause()
        paused = bool(result.get("summary", {}).get("paused"))
        self.scan_pause_button.setText("继续" if paused else "暂停")
        self.scan_status_badge.setText("● 已暂停" if paused else "● 验单中")
        self.set_scan_status_visual("paused" if paused else "ready", "已暂停" if paused else "放行中", result.get("message", ""))
        self.apply_scan_result(result)
        self.scan_input.setFocus()

    def show_scan_rule_info(self):
        summary = self.scan_service.summary()
        message = (
            "当前规则：先扫描出库单号，再扫描 SKU。\n"
            "Excel 自动识别字段：出库单号、SKU、数量、商品名称。\n"
            "匹配方式：去除空格并忽略大小写。\n"
            "本页面仅统计当前导入批次的本机扫码结果。"
        )
        if summary.get("loaded"):
            message += (
                f"\n\n当前 Excel：{Path(summary.get('source_path', '')).name}\n"
                f"出库单：{summary.get('order_count', 0)} 个\n"
                f"SKU：{summary.get('item_count', 0)} 个"
            )
        show_info(self, "字段规则", message)

    def handle_scan_input(self):
        code = self.scan_input.text().strip()
        self.scan_input.clear()
        if not code:
            return

        result = self.scan_service.scan(code)
        self.apply_scan_result(result)
        if result.get("result") == "pass":
            self.play_scan_success_sound()
        elif result.get("result") == "block":
            self.play_scan_error_sound()
        else:
            self.play_click_sound()
        self.scan_input.setFocus()

    def apply_scan_result(self, result):
        summary = result.get("summary", {})
        self.update_scan_summary(summary)

        order_number = result.get("order_number") or summary.get("current_order") or "未选择"
        sku = result.get("sku") or "等待输入"
        product_name = result.get("product_name") or "--"
        self.scan_current_order.setText(order_number)
        self.scan_current_sku.setText(sku)
        self.scan_product_name.setText("商品名称：" + product_name)
        self.scan_order_time.setText("出库时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
        self.scan_current_result.setText(result.get("message", "等待扫码"))
        self.scan_success_time.setText("扫描时间  " + result.get("time", time.strftime("%H:%M:%S")))

        if result.get("result") == "pass":
            self.set_scan_status_visual("pass", "放行中", "匹配成功，可以继续扫描")
        elif result.get("result") == "block":
            self.set_scan_status_visual("block", "已拦截", result.get("message", "扫码异常"))
        elif result.get("status") == "order_selected":
            self.set_scan_status_visual("ready", "放行中", "已选中出库单，请继续扫描 SKU")

        self.refresh_scan_detail_table(result.get("items", []))
        self.refresh_scan_log_tables()

    def update_scan_summary(self, summary):
        if not summary:
            return
        self.set_info_card_value(self.scan_metric_total_card, str(summary.get("total_scans", 0)))
        self.set_info_card_value(self.scan_metric_pass_card, str(summary.get("passed", 0)))
        self.set_info_card_value(self.scan_metric_fail_card, str(summary.get("failed", 0)))
        total_scans = int(summary.get("total_scans", 0) or 0)
        if total_scans:
            self.set_info_card_value(self.scan_metric_rate_card, f"{summary.get('pass_rate', 0):.1f}%")
        else:
            self.set_info_card_value(self.scan_metric_rate_card, "--")
        matched = int(summary.get("matched_count", 0) or 0)
        matchable = int(summary.get("matchable_count", 0) or 0)
        percent = int(summary.get("progress_percent", 0) or 0)
        self.scan_progress_bar.setValue(percent)
        self.scan_percent_label.setText(f"已匹配 {matched} / {matchable}（{percent}%）")

    def refresh_scan_detail_table(self, items):
        self.scan_detail_table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                str(row + 1),
                str(item.get("sku", "")),
                str(item.get("product_name", "") or "--"),
                str(item.get("quantity", 0)),
                str(item.get("scanned", 0)),
                str(item.get("status", "")),
            ]
            for col, value in enumerate(values):
                self.set_scan_table_item(self.scan_detail_table, row, col, value)

    def refresh_scan_log_tables(self):
        summary = self.scan_service.summary()
        logs = summary.get("recent_logs", [])[:8]

        self.scan_log_table.setRowCount(len(logs))
        for row, item in enumerate(logs):
            values = [
                item.get("order_number", ""),
                item.get("sku", ""),
                item.get("time", ""),
                item.get("result", ""),
            ]
            for col, value in enumerate(values):
                table_item = self.set_scan_table_item(self.scan_log_table, row, col, value)
                if "成功" in value or "选中" in value:
                    table_item.setForeground(QColor("#059669"))

    def set_scan_table_item(self, table, row, col, value):
        item = QTableWidgetItem(str(value))
        item.setToolTip(str(value))
        table.setItem(row, col, item)
        return item

    def set_scan_order_hero_style(self, state):
        styles = {
            "block": "background: #FEF2F2; border: 2px solid #FCA5A5; border-radius: 12px;",
            "pass": "background: #ECFDF5; border: 2px solid #6EE7B7; border-radius: 12px;",
            "ready": "background: #252C45; border: 2px solid #4F46B5; border-radius: 12px;",
            "paused": "background: #FFFBEB; border: 2px solid #FCD34D; border-radius: 12px;",
        }
        order_colors = {
            "block": "#B91C1C",
            "pass": "#047857",
            "ready": "#FFFFFF",
            "paused": "#B45309",
        }
        self.scan_order_hero_frame.setStyleSheet(styles.get(state, styles["ready"]))
        if hasattr(self, "scan_current_order"):
            self.scan_current_order.setStyleSheet(
                f"color: {order_colors.get(state, order_colors['ready'])};"
            )
        if state == "ready":
            for name in ("scan_order_label", "scan_sku_label"):
                if hasattr(self, name):
                    getattr(self, name).setStyleSheet("color: #CBD5E1;")
            for name in ("scan_order_time", "scan_product_name", "scan_success_time"):
                if hasattr(self, name):
                    getattr(self, name).setStyleSheet("color: #E2E8F0;")
            if hasattr(self, "scan_current_sku"):
                self.scan_current_sku.setStyleSheet("color: #C4B5FD;")
        else:
            for name in (
                "scan_order_label", "scan_sku_label", "scan_order_time",
                "scan_product_name", "scan_success_time", "scan_current_sku",
            ):
                if hasattr(self, name):
                    getattr(self, name).setStyleSheet("")

    def set_scan_status_visual(self, state, title, subtitle):
        if hasattr(self, "scan_order_hero_frame"):
            self.set_scan_order_hero_style(state)
        status_token = getattr(self, "_scan_status_visual_token", 0) + 1
        self._scan_status_visual_token = status_token
        self.scan_gate_status.setText(title)
        self.scan_gate_sub.setText(subtitle)
        if state == "block":
            self.scan_gate_frame.setStyleSheet(
                "background: #FEF2F2; border: 2px solid #DC2626; border-radius: 10px;"
            )
            self.scan_gate_icon.setText("!")
            self.scan_gate_icon.setStyleSheet("color: #DC2626; font-size: 24px; font-weight: 900;")
            self.scan_gate_status.setStyleSheet("color: #DC2626;")
            self.scan_gate_sub.setStyleSheet("color: #991B1B;")
            self.scan_current_result.setStyleSheet("color: #DC2626; font-weight: 900;")
            QTimer.singleShot(
                1200,
                lambda: self._reset_scan_status_visual_if_current(status_token),
            )
        elif state == "paused":
            self.scan_gate_frame.setStyleSheet(
                "background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 10px;"
            )
            self.scan_gate_icon.setText("Ⅱ")
            self.scan_gate_icon.setStyleSheet("color: #D97706; font-size: 24px; font-weight: 900;")
            self.scan_gate_status.setStyleSheet("color: #D97706;")
            self.scan_gate_sub.setStyleSheet("color: #92400E;")
            self.scan_current_result.setStyleSheet("color: #D97706; font-weight: 900;")
        else:
            self.scan_gate_frame.setStyleSheet(
                "background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px;"
            )
            self.scan_gate_icon.setText("✓")
            self.scan_gate_icon.setStyleSheet("color: #059669; font-size: 24px; font-weight: 900;")
            self.scan_gate_status.setStyleSheet("color: #059669;")
            self.scan_gate_sub.setStyleSheet("color: #64748B;")
            result_color = "#A7F3D0" if state == "ready" else "#059669"
            self.scan_current_result.setStyleSheet(f"color: {result_color}; font-weight: 900;")

    def _reset_scan_status_visual_if_current(self, status_token):
        if getattr(self, "_scan_status_visual_token", None) == status_token:
            self.scan_current_result.setText("等待扫码")
            self.set_scan_status_visual("ready", "放行中", "一扫正确，可以继续扫描")

    def export_scan_unmatched_source_rows(self):
        if not self.scan_service.loaded:
            show_info(self, "提示", "请先导入扫码验单 Excel。")
            return
        if not self.scan_service.unmatched_source_rows():
            show_info(self, "提示", "当前没有未匹配的源数据。")
            return
        default_path = Path.home() / "Desktop" / f"扫码验单未匹配_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出未匹配源数据",
            str(default_path),
            "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        try:
            output = self.scan_service.export_unmatched_source_rows(path)
            show_info(self, "导出完成", f"未匹配源数据已导出：\n{output}")
        except Exception as error:
            self.play_error_sound()
            show_warning(self, "导出失败", str(error))

    def show_scan_feature_placeholder(self):
        show_info(self, "扫码验单", "扫码验单功能当前先完成界面布局，下一步再接入 Excel 读取、扫码匹配、报警提示和拦截逻辑。")

    def build_history_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        card = self.create_card("📑 处理记录")
        tip = QLabel("这里会保存最近 500 条任务记录。双击记录可以打开输出位置。")
        tip.setObjectName("BodyText")
        tip.setWordWrap(True)
        card.layout().addWidget(tip)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新记录")
        refresh_btn.clicked.connect(self.refresh_history)
        open_btn = QPushButton("打开选中输出位置")
        open_btn.clicked.connect(self.open_selected_history_output)
        clear_btn = QPushButton("清空记录")
        clear_btn.clicked.connect(self.clear_history_records)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        card.layout().addLayout(btn_row)

        self.history_table = QTableWidget(0, 8)
        self.history_table.setObjectName("DataTable")
        self.history_table.setHorizontalHeaderLabels(["时间", "功能", "来源", "总数", "成功", "失败", "耗时", "输出目录"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.cellDoubleClicked.connect(self.open_history_output)
        card.layout().addWidget(self.history_table)

        layout.addWidget(card, 1)
        self.refresh_history()
        return page

    def build_statistics_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        self.stats_summary_row = QHBoxLayout()
        self.stats_summary_row.setSpacing(14)
        self.stats_today_card = self.info_card("今日处理", "0", "今日所有任务数量")
        self.stats_month_card = self.info_card("本月处理", "0", "本月累计处理数量")
        self.stats_all_card = self.info_card("累计处理", "0", "历史累计处理数量")
        self.stats_fast_card = self.info_card("最快速度", "--", "历史最高处理速度")
        self.stats_summary_row.addWidget(self.stats_today_card)
        self.stats_summary_row.addWidget(self.stats_month_card)
        self.stats_summary_row.addWidget(self.stats_all_card)
        self.stats_summary_row.addWidget(self.stats_fast_card)
        layout.addLayout(self.stats_summary_row)

        detail = self.create_card("📊 数据统计明细")
        self.stats_detail_text = QLabel("")
        self.stats_detail_text.setObjectName("StatsDetailText")
        self.stats_detail_text.setWordWrap(True)
        detail.layout().addWidget(self.stats_detail_text)

        refresh_btn = QPushButton("刷新统计")
        refresh_btn.clicked.connect(self.refresh_statistics)
        detail.layout().addWidget(refresh_btn)
        layout.addWidget(detail)

        self.refresh_statistics()
        layout.addStretch()
        return page

    def build_templates_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        card = self.create_card("⭐ 收藏模板")
        tip = QLabel("模板可以保存常用输出目录、每组PDF数量、自动ZIP、完成提示音等设置。")
        tip.setObjectName("BodyText")
        tip.setWordWrap(True)
        card.layout().addWidget(tip)

        btn_row = QHBoxLayout()
        save_pdf_btn = QPushButton("收藏当前面单设置")
        save_pdf_btn.clicked.connect(self.save_current_pdf_template)
        import_btn = QPushButton("导入模板文件")
        import_btn.clicked.connect(self.import_template_file)
        export_btn = QPushButton("导出模板")
        export_btn.clicked.connect(self.export_templates_file)
        apply_btn = QPushButton("应用选中模板")
        apply_btn.clicked.connect(self.apply_selected_template)
        open_btn = QPushButton("打开模板位置")
        open_btn.clicked.connect(self.open_selected_template_location)
        delete_btn = QPushButton("删除选中模板")
        delete_btn.clicked.connect(self.delete_selected_template)
        btn_row.addWidget(save_pdf_btn)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        card.layout().addLayout(btn_row)

        self.templates_table = QTableWidget(0, 7)
        self.templates_table.setObjectName("DataTable")
        self.templates_table.setHorizontalHeaderLabels(["模板名", "类型", "文件/输出目录", "每组PDF", "自动ZIP", "打开目录", "创建时间"])
        self.templates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.templates_table.verticalHeader().setVisible(False)
        self.templates_table.setAlternatingRowColors(True)
        self.templates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        card.layout().addWidget(self.templates_table)

        layout.addWidget(card, 1)
        self.refresh_templates()
        return page

    def build_settings_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        update_card = self.create_card("🆕 软件更新")
        update_desc = QLabel("自动检查只读取版本清单，不会中断正在进行的扫码或文件处理。")
        update_desc.setObjectName("BodyText")
        update_desc.setWordWrap(True)
        update_card.layout().addWidget(update_desc)

        update_row = QHBoxLayout()
        self.settings_auto_update_check = QCheckBox("启动后及每 6 小时自动检查更新")
        self.settings_auto_update_check.setChecked(bool(self.settings.get("auto_update_check", True)))
        self.settings_auto_update_check.toggled.connect(self.on_auto_update_check_toggled)
        update_row.addWidget(self.settings_auto_update_check)
        update_row.addStretch()
        update_card.layout().addLayout(update_row)

        self.update_status_label = QLabel("等待自动检查更新。")
        self.update_status_label.setObjectName("BodyText")
        self.update_status_label.setWordWrap(True)
        self.update_version_label = QLabel(f"当前版本：{APP_VERSION}    最新版本：--")
        self.update_version_label.setObjectName("BodyText")
        self.update_version_label.setWordWrap(True)
        update_card.layout().addWidget(self.update_status_label)
        update_card.layout().addWidget(self.update_version_label)

        update_actions = QHBoxLayout()
        update_check_btn = QPushButton("检查更新")
        update_check_btn.clicked.connect(self.check_update_status)
        self.update_now_button = QPushButton("立即更新")
        self.update_now_button.setObjectName("PrimaryButton")
        self.update_now_button.setEnabled(False)
        self.update_now_button.clicked.connect(self.start_latest_update)
        update_actions.addWidget(update_check_btn)
        update_actions.addWidget(self.update_now_button)
        update_actions.addStretch()
        update_card.layout().addLayout(update_actions)
        layout.addWidget(update_card)

        general = self.create_card("⚙ 常规设置")
        general_desc = QLabel("这些设置会保存到本机，下次启动自动读取。")
        general_desc.setObjectName("BodyText")
        general.layout().addWidget(general_desc)

        default_row = QHBoxLayout()
        default_row.addWidget(QLabel("默认输出目录："))
        self.settings_default_output = QLineEdit()
        self.settings_default_output.setText(str(self.settings.get("last_output_dir", "")))
        self.settings_default_output.setPlaceholderText("请选择默认输出目录")
        browse_default = QPushButton("浏览")
        browse_default.clicked.connect(self.select_settings_default_output)
        default_row.addWidget(self.settings_default_output, 1)
        default_row.addWidget(browse_default)
        general.layout().addLayout(default_row)

        button_row = QHBoxLayout()
        self.settings_sound = QCheckBox("启用统一 UI 音效")
        self.settings_sound.setChecked(bool(self.settings.get("sound_enabled", True)))
        self.settings_open_output = QCheckBox("任务完成后自动打开输出目录")
        self.settings_open_output.setChecked(bool(self.settings.get("open_output", True)))
        button_row.addWidget(self.settings_sound)
        button_row.addWidget(self.settings_open_output)
        button_row.addStretch()
        general.layout().addLayout(button_row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("界面语言："))
        self.settings_language = QComboBox()
        self.settings_language.addItems(["zh_CN", "ja_JP"])
        self.settings_language.setCurrentText(self.settings.get("language", "zh_CN"))
        lang_row.addWidget(self.settings_language)
        lang_row.addStretch()
        general.layout().addLayout(lang_row)

        layout.addWidget(general)

        pdf_card = self.create_card("📦 面单压缩默认设置")
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("每个文件夹最多PDF数："))
        self.settings_batch_size = QSpinBox()
        self.settings_batch_size.setRange(1, 9999)
        self.settings_batch_size.setValue(int(self.settings.get("batch_size", 90)))
        pdf_row.addWidget(self.settings_batch_size)

        self.settings_auto_zip = QCheckBox("默认自动压缩 ZIP")
        self.settings_auto_zip.setChecked(bool(self.settings.get("auto_zip", True)))
        pdf_row.addWidget(self.settings_auto_zip)
        pdf_row.addStretch()
        pdf_card.layout().addLayout(pdf_row)

        quick_row = QHBoxLayout()
        set_90 = QPushButton("设置为90")
        set_90.clicked.connect(lambda: self.settings_batch_size.setValue(90))
        set_100 = QPushButton("设置为100")
        set_100.clicked.connect(lambda: self.settings_batch_size.setValue(100))
        quick_row.addWidget(set_90)
        quick_row.addWidget(set_100)
        quick_row.addStretch()
        pdf_card.layout().addLayout(quick_row)
        layout.addWidget(pdf_card)

        excel_card = self.create_card("📋 文件粘贴设置")
        self.settings_excel_open = QCheckBox("生成上传表后自动打开 Excel 文件")
        self.settings_excel_open.setChecked(True)
        self.settings_address_split = QCheckBox("启用地址自动拆分")
        self.settings_address_split.setChecked(True)
        excel_card.layout().addWidget(self.settings_excel_open)
        excel_card.layout().addWidget(self.settings_address_split)
        note = QLabel("提示：Alpha17 中这两项默认开启，后续版本会开放更细的规则设置。")
        note.setObjectName("BodyText")
        note.setWordWrap(True)
        excel_card.layout().addWidget(note)
        layout.addWidget(excel_card)

        action_card = self.create_card("保存设置")
        action_row = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_settings_from_page)
        reset_btn = QPushButton("恢复推荐设置")
        reset_btn.clicked.connect(self.reset_recommended_settings)
        action_row.addWidget(save_btn)
        action_row.addWidget(reset_btn)
        action_row.addStretch()
        action_card.layout().addLayout(action_row)
        layout.addWidget(action_card)

        stage3_card = self.create_card("🧩 第三阶段架构")
        stage3_text = QLabel("v3.0 已加入插件系统、多语言系统、自动更新接口和安装包脚本。当前是架构基础版，后续会逐步实装完整界面。")
        stage3_text.setObjectName("BodyText")
        stage3_text.setWordWrap(True)
        stage3_card.layout().addWidget(stage3_text)

        plugin_btn = QPushButton("查看插件状态")
        plugin_btn.clicked.connect(self.show_plugin_status)
        update_btn = QPushButton("检查更新")
        update_btn.clicked.connect(self.check_update_status)
        stage3_row = QHBoxLayout()
        stage3_row.addWidget(plugin_btn)
        stage3_row.addWidget(update_btn)
        stage3_row.addStretch()
        stage3_card.layout().addLayout(stage3_row)
        layout.addWidget(stage3_card)

        layout.addStretch()
        return page

    def build_help_page(self):
        page = self.create_scroll_page()
        layout = page.layout()
        card = self.create_card("📖 帮助文档")
        help_text = QLabel(
            "第一次使用：\n"
            "1. 文件粘贴：选择 Excel → 选择输出位置 → 生成上传表。\n"
            "2. 面单压缩：选择一个或多个 PDF → 选择输出目录 → 开始处理。\n"
            "3. 如果文件很多，建议先放到同一个文件夹，再多选导入。\n\n"
            "升级安装：\n"
            "1. 在设置页点击“检查更新”，确认新版本号、下载地址和 SHA256。\n"
            "2. 选择立即更新后，软件会下载并校验安装包。\n"
            "3. 确认安装后软件会退出，由独立脚本覆盖安装并重新启动。\n"
            "4. 如果一键更新失败，再下载 GitHub Release 安装包并运行安装脚本。"
        )
        help_text.setObjectName("BodyText")
        help_text.setWordWrap(True)
        card.layout().addWidget(help_text)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def build_changelog_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        top_card = self.create_card("🆕 更新日志")
        top_text = QLabel("这里会保存每个版本的新增、优化和修复内容。从 Alpha1 开始，更新日志作为独立数据维护。")
        top_text.setObjectName("BodyText")
        top_text.setWordWrap(True)
        top_card.layout().addWidget(top_text)

        refresh_btn = QPushButton("刷新更新日志")
        refresh_btn.clicked.connect(self.refresh_changelog_cards)
        top_card.layout().addWidget(refresh_btn)
        layout.addWidget(top_card)

        self.changelog_layout = QVBoxLayout()
        self.changelog_layout.setSpacing(14)
        layout.addLayout(self.changelog_layout)
        layout.addStretch()

        self.refresh_changelog_cards()
        return page

    def build_about_page(self):
        page = self.create_scroll_page()
        layout = page.layout()

        hero = self.create_card("ℹ 关于我们")
        title = QLabel("黑猫审单助手\nBlackCat Audit Assistant")
        title.setObjectName("AboutTitle")
        title.setWordWrap(True)
        hero.layout().addWidget(title)

        brand = QLabel("MADE IN チュウ ビョ")
        brand.setObjectName("AboutBrand")
        hero.layout().addWidget(brand)

        layout.addWidget(hero)

        contact = self.create_card("联系方式")
        email_row = QHBoxLayout()
        email_row.addWidget(QLabel("📧 Google 邮箱："))
        self.about_email = QLineEdit("zm3491583857@gmail.com")
        self.about_email.setReadOnly(True)
        copy_email = QPushButton("复制邮箱")
        copy_email.clicked.connect(self.copy_about_email)
        email_row.addWidget(self.about_email, 1)
        email_row.addWidget(copy_email)
        contact.layout().addLayout(email_row)

        phone_row = QHBoxLayout()
        phone_row.addWidget(QLabel("📱 电话号码："))
        self.about_phone = QLineEdit("09037279527")
        self.about_phone.setReadOnly(True)
        copy_phone = QPushButton("复制电话")
        copy_phone.clicked.connect(self.copy_about_phone)
        phone_row.addWidget(self.about_phone, 1)
        phone_row.addWidget(copy_phone)
        contact.layout().addLayout(phone_row)
        layout.addWidget(contact)

        info = self.create_card("软件信息")
        info_text = QLabel(
            f"软件版本：{APP_VERSION}\n"
            "Engine：BlackCat Engine\n"
            "Build：Alpha18 Stable Test\n"
            "UI Framework：PySide6 / Qt\n"
            "Excel Engine：OpenPyXL\n"
            "PDF Engine：PyMuPDF\n"
            "License：Internal Version\n"
            "用途：熟人内部测试版"
        )
        info_text.setObjectName("BodyText")
        info_text.setWordWrap(True)
        info.layout().addWidget(info_text)
        layout.addWidget(info)

        thanks = self.create_card("感谢使用")
        thanks_text = QLabel("感谢使用黑猫审单助手。这个版本已经可以作为长期稳定测试版继续使用。")
        thanks_text.setObjectName("BodyText")
        thanks_text.setWordWrap(True)
        thanks.layout().addWidget(thanks_text)
        layout.addWidget(thanks)

        layout.addStretch()
        return page

    def create_scroll_page(self):
        return ScrollPage()

    def info_card(self, title, value, subtitle):
        card = QFrame()
        card.setObjectName("InfoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("InfoTitle")
        value_label = QLabel(value)
        value_label.setObjectName("InfoValue")
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("InfoSub")
        sub_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(sub_label)
        return card

    def placeholder_table(self, title, subtitle):
        box = QFrame()
        box.setObjectName("PlaceholderBox")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 18)
        label = QLabel(title)
        label.setObjectName("PlaceholderTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("BodyText")
        sub.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(sub)
        return box

    def small_button(self, text):
        button = QPushButton(text)
        button.setObjectName("SmallButton")
        return button

    def create_card(self, title):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("CardTitle")
        layout.addWidget(label)
        return card

    def section_label(self, text):
        row = QHBoxLayout()
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        row.addWidget(label)
        row.addStretch()
        return row

    def apply_style(self):
        self.setStyleSheet("""
        QWidget {
            font-family: "Microsoft YaHei UI";
            font-size: 14px;
            color: #111827;
        }
        #Sidebar {
            background: #0F172A;
        }
        #AvatarImage {
            padding: 0px;
            border-radius: 24px;
        }
        #SidebarTitle {
            color: white;
            font-size: 24px;
            font-weight: 900;
            padding-top: 4px;
        }
        #BrandText {
            color: #C4B5FD;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        #SideButton {
            color: #CBD5E1;
            background: transparent;
            border: none;
            text-align: left;
            padding: 11px 16px;
            border-radius: 10px;
            font-size: 15px;
        }
        #SideButton:hover {
            background: #1E293B;
            color: white;
        }
        #SideButton[active="true"] {
            background: #6D5DF6;
            color: white;
            font-weight: 800;
        }
        #SideSeparator {
            background: #233044;
            margin-top: 4px;
            margin-bottom: 4px;
        }
        #SidebarStatus {
            color: #86EFAC;
            font-size: 13px;
        }
        #Main {
            background: #F5F7FB;
        }
        #Title {
            font-size: 32px;
            font-weight: 900;
        }
        #Subtitle {
            color: #64748B;
            font-size: 15px;
        }
        #Card, #InfoCard {
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }
        #CardTitle {
            font-size: 17px;
            font-weight: 800;
        }
        #ScanStatusBadge {
            color: #047857;
            background: #FFFFFF;
            border: 1px solid #D1FAE5;
            border-radius: 8px;
            padding: 7px 12px;
            font-weight: 900;
            min-width: 118px;
        }
        #ScanBigInput {
            color: #111827;
            background: #FFFFFF;
            border: 2px solid #6D5DF6;
            border-radius: 8px;
            padding: 18px 22px;
            font-size: 24px;
            font-weight: 900;
            min-height: 58px;
            selection-background-color: #6D5DF6;
            selection-color: #FFFFFF;
        }
        #ScanBigInput:focus {
            border: 2px solid #5B4CF0;
            background: #FFFFFF;
        }
        #ScanMutedText {
            color: #64748B;
            font-size: 12px;
        }
        #ScanFieldLabel {
            color: #64748B;
            font-size: 12px;
            font-weight: 800;
        }
        #ScanFieldValue {
            color: #6D5DF6;
            font-size: 18px;
            font-weight: 900;
        }
        #ScanOrderHeroValue {
            color: #FFFFFF;
            font-size: 30px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #ScanOrderHero {
            min-height: 150px;
        }
        #ScanProgressCard QProgressBar {
            min-height: 16px;
            border-radius: 8px;
        }
        #ScanProductPreview {
            color: #94A3B8;
            background: #F8FAFC;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }
        #ScanSuccessBanner {
            background: #ECFDF5;
            border: 1px solid #D1FAE5;
            border-radius: 8px;
        }
        #ScanSuccessText {
            color: #059669;
            font-weight: 900;
        }
        #ScanRightStatus {
            background: #ECFDF5;
            border: 1px solid #A7F3D0;
            border-radius: 8px;
        }
        #ScanStatusIcon {
            color: #FFFFFF;
            background: #10B981;
            border-radius: 15px;
            padding: 5px 9px;
            font-size: 18px;
            font-weight: 900;
        }
        #ScanGateStatus {
            color: #059669;
            font-size: 24px;
            font-weight: 900;
        }
        #ScanLinkText {
            color: #6D5DF6;
            font-size: 12px;
            font-weight: 900;
        }
        #BodyText {
            line-height: 150%;
        }
        #BodyText {
            color: #475569;
        }
        #StatsDetailText {
            color: #334155;
            background: #F8FAFC;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 14px;
            line-height: 160%;
        }
        #SectionLabel {
            color: #334155;
            font-size: 13px;
            font-weight: 900;
            padding-top: 4px;
        }
        #InfoTitle {
            color: #64748B;
            font-weight: 700;
        }
        #InfoValue {
            color: #6D5DF6;
            font-size: 34px;
            font-weight: 900;
        }
        #InfoSub {
            color: #94A3B8;
            font-size: 13px;
        }
        #PlaceholderBox {
            background: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 14px;
        }
        #PlaceholderTitle {
            font-size: 18px;
            font-weight: 800;
            color: #334155;
        }
        QLineEdit, QSpinBox, QComboBox {
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 9px 12px;
            background: white;
            color: #111827;
            min-height: 22px;
        }
        QComboBox QAbstractItemView {
            background: #FFFFFF;
            color: #111827;
            selection-background-color: #EDE9FE;
            selection-color: #111827;
            border: 1px solid #CBD5E1;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            min-height: 28px;
            padding: 6px 10px;
            color: #111827;
            background: #FFFFFF;
        }
        QPushButton {
            background: white;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 700;
            min-height: 22px;
        }
        QPushButton:hover {
            background: #F1F5F9;
        }
        #PrimaryButton {
            background: #6D5DF6;
            color: white;
            border: none;
            font-size: 17px;
            padding: 14px 24px;
            min-height: 30px;
        }
        #PrimaryButton:hover {
            background: #5B4CE0;
        }
        #ExcelButton {
            color: white;
            background: #22C55E;
            border: none;
            padding: 12px 20px;
            min-height: 28px;
        }
        #ExcelButton:hover {
            background: #16A34A;
        }
        #SmallButton {
            padding: 8px 14px;
        }
        #ToolButton {
            min-width: 118px;
        }
        QPushButton:disabled {
            background: #E5E7EB;
            color: #94A3B8;
        }
        QProgressBar {
            border: none;
            border-radius: 11px;
            background: #E5E7EB;
            height: 34px;
            min-height: 34px;
            text-align: center;
            font-weight: 900;
            color: #111827;
            font-size: 15px;
        }
        QProgressBar::chunk {
            border-radius: 11px;
            background: #6D5DF6;
        }
        #LogText {
            background: #0F172A;
            color: #D1D5DB;
            border-radius: 8px;
            padding: 10px;
            font-family: Consolas;
            font-size: 13px;
            min-height: 240px;
        }

        #DataTable {
            background: #FFFFFF;
            alternate-background-color: #F8FAFC;
            color: #111827;
            gridline-color: #E5E7EB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            selection-background-color: #EDE9FE;
            selection-color: #111827;
            font-size: 13px;
        }
        #DataTable::item {
            padding: 8px;
            color: #111827;
        }
        QHeaderView::section {
            background: #F1F5F9;
            color: #334155;
            padding: 8px;
            border: none;
            border-right: 1px solid #E5E7EB;
            border-bottom: 1px solid #CBD5E1;
            font-weight: 800;
        }


        #AboutTitle {
            color: #111827;
            font-size: 28px;
            font-weight: 900;
            line-height: 140%;
        }
        #AboutBrand {
            color: #6D5DF6;
            font-size: 18px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        #CurrentBadge {
            background: #6D5DF6;
            color: white;
            border-radius: 8px;
            padding: 6px 10px;
            font-weight: 900;
            max-width: 180px;
        }
        #ChangelogSectionTitle {
            color: #111827;
            font-size: 16px;
            font-weight: 900;
            padding-top: 8px;
        }


        QTableWidget {
            background: #FFFFFF;
            alternate-background-color: #F8FAFC;
            color: #111827;
            gridline-color: #E5E7EB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            selection-background-color: #EDE9FE;
            selection-color: #111827;
            font-size: 13px;
        }
        QTableWidget::item {
            padding: 8px;
            color: #111827;
        }
        QTableWidget::item:selected {
            background: #EDE9FE;
            color: #111827;
        }
        QHeaderView::section {
            background: #F1F5F9;
            color: #334155;
            padding: 8px;
            border: none;
            border-right: 1px solid #E5E7EB;
            border-bottom: 1px solid #CBD5E1;
            font-weight: 800;
        }

        #StatValue {
            font-size: 16px;
            font-weight: 900;
            color: #6D5DF6;
        }
        """)

    def connect_task_signals(self):
        self.task_manager.progress.connect(self.on_progress)
        self.task_manager.log.connect(self.add_pdf_log)
        self.task_manager.stats.connect(self.update_stats)
        self.task_manager.done.connect(self.on_done)
        self.task_manager.error.connect(self.on_error)

    def select_label_source(self):
        self.play_click_sound()
        path, _ = QFileDialog.getOpenFileName(
            self, "选择原始一件代发表", "", "Excel Files (*.xlsx *.xlsm)"
        )
        if path:
            self.label_source_input.setText(path)
            self.add_label_log("INFO", f"已选择原始一件代发表: {path}")

    def select_label_finished(self):
        self.play_click_sound()
        path, _ = QFileDialog.getOpenFileName(
            self, "选择完整成品表", "", "Excel Files (*.xlsx *.xlsm)"
        )
        if path:
            self.label_finished_input.setText(path)
            self.add_label_log("INFO", f"已选择完整成品表: {path}")

    def select_label_pdfs(self):
        self.play_click_sound()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择一个或多个面单 PDF", "", "PDF Files (*.pdf)"
        )
        if paths:
            self.label_pdf_input.setText("|".join(paths))
            self.add_label_log("INFO", f"已选择面单 PDF: {len(paths)} 个")

    def select_label_output_dir(self):
        self.play_click_sound()
        path = QFileDialog.getExistingDirectory(self, "选择面单打印输出目录")
        if path:
            self.label_output_dir_input.setText(path)
            self.add_label_log("INFO", f"已选择输出目录: {path}")

    def get_label_printing_context(self):
        source_path = self.label_source_input.text().strip()
        finished_path = self.label_finished_input.text().strip()
        pdf_paths = [path for path in self.label_pdf_input.text().split("|") if path]
        missing = []
        for name, path in (("原始一件代发表", source_path), ("完整成品表", finished_path)):
            if not path:
                missing.append(name)
            elif not Path(path).is_file():
                show_warning(self, "面单打印", f"{name}不存在或不是文件：\n{path}")
                self.play_error_sound()
                return None
        if missing:
            show_warning(self, "面单打印", "请先选择：" + "、".join(missing))
            self.play_error_sound()
            return None
        if not pdf_paths:
            show_warning(self, "面单打印", "请至少选择一个黑猫面单 PDF。")
            self.play_error_sound()
            return None
        invalid_pdfs = [path for path in pdf_paths if not Path(path).is_file()]
        if invalid_pdfs:
            show_warning(self, "面单打印", "以下面单 PDF 不存在或不是文件：\n" + "\n".join(invalid_pdfs[:5]))
            self.play_error_sound()
            return None

        output_text = self.label_output_dir_input.text().strip()
        output_dir = Path(output_text) if output_text else PathManager.output_dir() / "LabelPrinting"
        if output_text and not output_dir.is_dir():
            show_warning(self, "面单打印", f"输出目录不存在或不可用：\n{output_dir}")
            self.play_error_sound()
            return None
        return {
            "source_path": source_path,
            "finished_path": finished_path,
            "pdf_paths": pdf_paths,
            "output_dir": str(output_dir),
            "scope": self.label_scope_combo.currentData(),
            "split_types": bool(self.label_split_types_combo.currentData()),
            "open_after": self.label_open_after_checkbox.isChecked(),
        }

    def start_label_printing(self):
        if self.label_printing_thread and self.label_printing_thread.isRunning():
            return
        self.play_click_sound()
        context = self.get_label_printing_context()
        if not context:
            return

        self.label_printing_started_at = time.monotonic()
        self.label_progress_bar.setRange(0, 0)
        self.label_progress_status.setText("正在准备面单打印任务...")
        self.add_label_log("INFO", "开始面单打印任务")
        self.set_label_printing_controls_enabled(False)

        self.label_printing_thread = QThread(self)
        self.label_printing_worker = LabelPrintingWorker(self.module_registry, context)
        self.label_printing_worker.moveToThread(self.label_printing_thread)
        self.label_printing_thread.started.connect(self.label_printing_worker.run)
        self.label_printing_worker.progress.connect(self.on_label_printing_progress)
        self.label_printing_worker.finished.connect(self.on_label_printing_finished)
        self.label_printing_worker.failed.connect(self.on_label_printing_failed)
        self.label_printing_worker.finished.connect(self.label_printing_thread.quit)
        self.label_printing_worker.failed.connect(self.label_printing_thread.quit)
        self.label_printing_thread.finished.connect(self.label_printing_worker.deleteLater)
        self.label_printing_thread.finished.connect(self.clear_label_printing_worker)
        self.label_printing_thread.finished.connect(self.label_printing_thread.deleteLater)
        self.label_printing_thread.start()

    def set_label_printing_controls_enabled(self, enabled):
        for control in self.label_printing_controls:
            control.setEnabled(enabled)

    def on_label_printing_progress(self, event):
        event = event or {}
        if event.get("indeterminate"):
            self.label_progress_bar.setRange(0, 0)
        else:
            total = max(1, int(event.get("total") or 0))
            current = max(0, min(total, int(event.get("current") or 0)))
            self.label_progress_bar.setRange(0, total)
            self.label_progress_bar.setValue(current)
        message = event.get("message") or "正在生成面单打印文件..."
        self.label_progress_status.setText(message)
        self.add_label_log("INFO", message)

    def on_label_printing_finished(self, result):
        self.label_progress_bar.setRange(0, 100)
        self.label_progress_bar.setValue(100)
        self.label_progress_status.setText("面单打印完成。")
        self.set_label_printing_controls_enabled(True)
        self.handle_label_printing_success(result)

    def on_label_printing_failed(self, error):
        self.label_progress_status.setText("面单打印失败。")
        self.set_label_printing_controls_enabled(True)
        self.add_label_log("ERROR", f"面单打印失败: {error}")
        self.play_error_sound()
        show_warning(self, "面单打印失败", error)

    def handle_label_printing_success(self, result):
        output_paths = result.get("output_paths", [])
        total_pages = int(result.get("total_pages", 0))
        matched_pages = int(result.get("matched_pages", 0))
        excluded_pages = int(result.get("excluded_pages", 0))
        printed_pages = max(0, matched_pages - excluded_pages)
        elapsed = max(0, int(time.monotonic() - getattr(self, "label_printing_started_at", time.monotonic())))
        output_dir = result.get("output_dir", "")
        self.label_output_dir_input.setText(output_dir)
        self.add_label_log("SUCCESS", f"面单打印文件已生成至: {output_dir}")
        self.add_label_log("INFO", f"总页数: {total_pages}；匹配: {matched_pages}；可打印: {printed_pages}；排除: {excluded_pages}")
        for output_path in output_paths:
            self.add_label_log("INFO", f"生成文件: {Path(output_path).name}")
        self.data_manager.add_record({
            "type": "面单打印",
            "source": self.label_source_input.text().strip(),
            "output": output_dir,
            "total": total_pages,
            "success": printed_pages,
            "failed": excluded_pages,
            "elapsed": elapsed,
            "note": f"匹配 {matched_pages} 页，输出 {len(output_paths)} 个文件",
        })
        self.refresh_dashboard()
        self.refresh_statistics()
        self.play_done_sound()
        names = "\n".join(f"- {Path(path).name}" for path in output_paths) or "- 未生成可打印文件"
        show_info(
            self,
            "面单打印完成",
            f"总页数：{total_pages}\n匹配页数：{matched_pages}\n可打印页数：{printed_pages}\n排除页数：{excluded_pages}"
            f"\n输出目录：{output_dir}\n\n生成文件：\n{names}",
        )

    def clear_label_printing_worker(self):
        self.label_printing_worker = None
        self.label_printing_thread = None

    def add_label_log(self, level, message):
        self.write_log_to_widget(self.label_log_text, level, message)
        if bool(self.settings.get("save_logs", True)):
            self.logger.write(level, message)

    def select_pdf(self):
        self.play_click_sound()
        paths, _ = QFileDialog.getOpenFileNames(self, "选择一个或多个 PDF", "", "PDF Files (*.pdf)")
        if paths:
            self.play_import_sound()
            self.pdf_input.setText("|".join(paths))
            if not self.output_input.text().strip():
                self.output_input.setText(str(Path(paths[0]).parent / "BlackCatOutput"))
            self.add_pdf_log("INFO", f"已选择PDF文件数: {len(paths)}")
            for path in paths:
                self.add_pdf_log("INFO", f"PDF: {path}")

    def select_output_dir(self):
        self.play_click_sound()
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_input.setText(path)
            self.add_pdf_log("INFO", f"已选择输出目录: {path}")

    def select_upload_excel(self):
        self.play_click_sound()
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel", "", "Excel Files (*.xlsx *.xlsm)")
        if path:
            self.play_import_sound()
            self.excel_source = path
            self.excel_input.setText(path)
            self.add_excel_log("INFO", f"已选择Excel: {path}")

    def select_excel_output_dir(self):
        self.play_click_sound()
        path = QFileDialog.getExistingDirectory(self, "选择上传表输出位置")
        if path:
            self.excel_output_dir_input.setText(path)
            self.add_excel_log("INFO", f"已选择上传表输出位置: {path}")

    def convert_upload_excel(self):
        self.play_click_sound()
        source = self.excel_input.text().strip()
        if not source:
            self.select_upload_excel()
            source = self.excel_input.text().strip()
            if not source:
                return

        output_dir_text = self.excel_output_dir_input.text().strip()
        if output_dir_text:
            output_dir = Path(output_dir_text)
        else:
            output_dir = PathManager.output_dir() / "BlackCatUploadTable"

        self.start_excel_conversion(source, output_dir)

    def start_excel_conversion(self, source, output_dir):
        from modules.file_paste.converter import ConversionControl

        if self.excel_conversion_thread and self.excel_conversion_thread.isRunning():
            return

        self.excel_generate_button.setEnabled(False)
        self.excel_pending_result = None
        self.excel_pending_error = None
        self.excel_conversion_cancelled = False
        self.excel_conversion_control = ConversionControl()
        self.show_excel_progress_dialog()

        context = {
            "source_path": source,
            "output_dir": output_dir,
            "open_after": True,
            "conversion_control": self.excel_conversion_control,
        }
        self.excel_conversion_thread = QThread(self)
        self.excel_conversion_worker = ExcelConversionWorker(self.module_registry, context)
        self.excel_conversion_worker.moveToThread(self.excel_conversion_thread)
        self.excel_conversion_thread.started.connect(self.excel_conversion_worker.run)
        self.excel_conversion_worker.progress.connect(self.on_excel_conversion_progress)
        self.excel_conversion_worker.finished.connect(self.on_excel_conversion_finished)
        self.excel_conversion_worker.cancelled.connect(self.on_excel_conversion_cancelled)
        self.excel_conversion_worker.failed.connect(self.on_excel_conversion_failed)
        self.excel_conversion_worker.finished.connect(self.excel_conversion_thread.quit)
        self.excel_conversion_worker.cancelled.connect(self.excel_conversion_thread.quit)
        self.excel_conversion_worker.failed.connect(self.excel_conversion_thread.quit)
        self.excel_conversion_thread.finished.connect(self.excel_conversion_worker.deleteLater)
        self.excel_conversion_thread.finished.connect(self.clear_excel_conversion_worker)
        self.excel_conversion_thread.finished.connect(self.excel_conversion_thread.deleteLater)
        self.excel_conversion_thread.start()

    def show_excel_progress_dialog(self):
        dialog = ExcelProgressDialog(self)
        dialog.setWindowTitle("正在生成上传表")
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowCloseButtonHint, False)
        dialog.setFixedSize(430, 226)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(14)

        title = QLabel("正在生成黑猫上传表")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        self.excel_progress_status = QLabel("正在准备任务...")
        self.excel_progress_status.setObjectName("DialogText")
        self.excel_progress_status.setWordWrap(True)
        layout.addWidget(self.excel_progress_status)

        self.excel_progress_bar = QProgressBar()
        self.excel_progress_bar.setRange(0, 0)
        self.excel_progress_bar.setTextVisible(True)
        layout.addWidget(self.excel_progress_bar)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.excel_pause_button = QPushButton("暂停")
        self.excel_pause_button.clicked.connect(self.toggle_excel_conversion_pause)
        buttons.addWidget(self.excel_pause_button)
        self.excel_cancel_button = QPushButton("结束任务")
        self.excel_cancel_button.setObjectName("DangerButton")
        self.excel_cancel_button.clicked.connect(self.cancel_excel_conversion)
        buttons.addWidget(self.excel_cancel_button)
        layout.addLayout(buttons)

        self.excel_progress_dialog = dialog
        dialog.show()

    def on_excel_conversion_progress(self, event):
        if not self.excel_progress_bar or not self.excel_progress_status:
            return

        if event.get("indeterminate"):
            self.excel_progress_bar.setRange(0, 0)
        else:
            total = max(1, int(event.get("total") or 0))
            current = max(0, min(total, int(event.get("current") or 0)))
            self.excel_progress_bar.setRange(0, total)
            self.excel_progress_bar.setValue(current)
        self.excel_progress_status.setText(event.get("message") or "正在处理 Excel 文件...")

    def toggle_excel_conversion_pause(self):
        if not self.excel_conversion_control or not self.excel_pause_button:
            return
        if self.excel_conversion_control.paused:
            self.excel_conversion_control.resume()
            self.excel_pause_button.setText("暂停")
            if self.excel_progress_status:
                self.excel_progress_status.setText("正在继续处理...")
        else:
            self.excel_conversion_control.pause()
            self.excel_pause_button.setText("继续")
            if self.excel_progress_status:
                self.excel_progress_status.setText("已暂停，可点击继续")

    def cancel_excel_conversion(self):
        if not self.excel_conversion_control:
            return
        self.excel_conversion_control.cancel()
        if self.excel_pause_button:
            self.excel_pause_button.setEnabled(False)
        if self.excel_cancel_button:
            self.excel_cancel_button.setEnabled(False)
        if self.excel_progress_status:
            self.excel_progress_status.setText("正在结束，等待当前步骤完成...")

    def on_excel_conversion_finished(self, result):
        self.excel_pending_result = result
        self.finish_excel_progress()

    def on_excel_conversion_cancelled(self):
        self.excel_conversion_cancelled = True
        self.finish_excel_progress()

    def on_excel_conversion_failed(self, error):
        self.excel_pending_error = error
        self.finish_excel_progress()

    def finish_excel_progress(self):
        if self.excel_progress_bar and not self.excel_conversion_cancelled and not self.excel_pending_error:
            self.excel_progress_bar.setRange(0, 100)
            self.excel_progress_bar.setValue(100)
        if self.excel_progress_status:
            if self.excel_conversion_cancelled:
                status = "任务已结束，正在清理未完成文件..."
            elif self.excel_pending_error:
                status = "生成失败，正在显示错误..."
            else:
                status = "生成完成，正在打开结果..."
            self.excel_progress_status.setText(status)
        QTimer.singleShot(180, self.close_excel_progress_and_report)

    def close_excel_progress_and_report(self):
        if self.excel_progress_dialog:
            self.excel_progress_dialog.close()
            self.excel_progress_dialog.deleteLater()
        self.excel_progress_dialog = None
        self.excel_progress_bar = None
        self.excel_progress_status = None
        self.excel_pause_button = None
        self.excel_cancel_button = None
        self.excel_generate_button.setEnabled(True)

        if self.excel_conversion_cancelled:
            self.excel_conversion_cancelled = False
            self.add_excel_log("INFO", "文件粘贴任务已结束，未生成文件。")
            return

        if self.excel_pending_error:
            error = self.excel_pending_error
            self.excel_pending_error = None
            self.add_excel_log("ERROR", f"黑猫上传表生成失败: {error}")
            self.play_error_sound()
            show_warning(self, "提示", error)
            return

        result = self.excel_pending_result
        self.excel_pending_result = None
        self.handle_excel_conversion_success(result)

    def handle_excel_conversion_success(self, result):
        output_dir = result.get("output_dir", result["output_path"])
        output_paths = result.get("output_paths", [result["output_path"]])
        self.excel_output_input.setText(output_dir)
        self.add_excel_log("SUCCESS", f"黑猫上传表已生成至文件夹: {output_dir}")
        self.add_excel_log("INFO", f"识别格式: {result.get('source_type', '')}")
        self.add_excel_log("INFO", f"生成行数: {result['row_count']}")
        self.add_excel_log("INFO", f"生成文件: {result.get('file_count', len(output_paths))} 份")
        for output_path in output_paths:
            self.add_excel_log("INFO", f"文件: {Path(output_path).name}")
        self.add_excel_log("INFO", f"地址自动拆分并标黄: {result.get('split_count', 0)} 行")
        self.add_excel_log("INFO", f"关键字段为空并标红: {result.get('missing_count', 0)} 行")
        self.add_excel_log("INFO", f"地址超长已放入O列并标红: {result.get('address_overflow_count', 0)} 行")
        self.add_excel_log("INFO", f"SKU数量待确认并标红: {result.get('quantity_issue_count', 0)} 行")
        quantity_issue_orders = result.get("quantity_issue_orders", [])
        if quantity_issue_orders:
            self.add_excel_log("WARNING", "SKU数量待确认订单: " + ", ".join(quantity_issue_orders))
        self.data_manager.add_record({
            "type": "文件粘贴",
            "source": str(self.excel_input.text().strip()),
            "output": str(output_dir),
            "total": result["row_count"],
            "success": result["row_count"],
            "failed": 0,
            "elapsed": 0,
            "note": result.get("source_type", "")
        })
        self.refresh_dashboard()
        self.refresh_statistics()
        self.play_done_sound()
        show_info(
            self,
            "完成",
            file_paste_success_message(result),
        )

    def clear_excel_conversion_worker(self):
        self.excel_conversion_worker = None
        self.excel_conversion_thread = None
        if self.excel_quit_after_cancellation:
            self.excel_quit_after_cancellation = False
            self.finish_application_quit()

    def save_settings(self):
        if hasattr(self, "batch_size"):
            self.settings["batch_size"] = int(self.batch_size.value())
        if hasattr(self, "auto_zip"):
            self.settings["auto_zip"] = bool(self.auto_zip.isChecked())
        if hasattr(self, "open_output"):
            self.settings["open_output"] = bool(self.open_output.isChecked())
        if hasattr(self, "sound_enabled"):
            self.settings["sound_enabled"] = bool(self.sound_enabled.isChecked())
        if hasattr(self, "output_input"):
            self.settings["last_output_dir"] = self.output_input.text().strip()
        self.config.save(self.settings)

    def get_config(self):
        pdf = self.pdf_input.text().strip()
        output = self.output_input.text().strip()

        if not pdf:
            self.play_error_sound()
            show_warning(self, "提示", "请先选择 PDF 文件。")
            return None

        pdf_paths = [item for item in pdf.split("|") if item]
        missing = [item for item in pdf_paths if not Path(item).exists()]
        if missing:
            self.play_error_sound()
            show_warning(self, "提示", "以下 PDF 文件不存在：\n" + "\n".join(missing[:5]))
            return None

        if not output:
            self.play_error_sound()
            show_warning(self, "提示", "请先选择输出目录。")
            return None

        return {
            "pdf": pdf,
            "output": output,
            "batch_size": int(self.batch_size.value()),
            "auto_zip": bool(self.auto_zip.isChecked()),
            "open_output": bool(self.open_output.isChecked()),
        }

    def start_process(self):
        self.play_click_sound()
        config = self.get_config()
        if not config:
            return

        self.save_settings()
        self.reset_stats()
        self.progress_bar.setValue(0)
        self.clear_pdf_log()
        self.add_pdf_log("INFO", "开始新任务")
        self.add_pdf_log("INFO", f"每个文件夹最多PDF数: {self.batch_size.value()}")

        if self.task_manager.start(config):
            self.start_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress_processed.setText("已处理：0 / 0")
            self.progress_remaining.setText("预计剩余：计算中")
            self.progress_speed.setText("速度：0.00 页/秒")
            self.progress_elapsed.setText("已用时：00:00:00")

    def cancel_process(self):
        self.play_click_sound()
        self.task_manager.cancel()
        self.cancel_button.setEnabled(False)
        self.progress_processed.setText("正在停止...")

    def on_progress(self, percent, text):
        self.progress_bar.setValue(int(percent))

    def update_stats(self, data):
        total = int(data.get("total", 0))
        current = int(data.get("current", 0))
        success = int(data.get("success", 0))
        failed = int(data.get("failed", 0))
        speed = float(data.get("speed", 0))
        elapsed = float(data.get("elapsed", 0))

        remaining_pages = max(total - current, 0)
        remaining_seconds = remaining_pages / speed if speed > 0 else 0

        self.stats_labels["total"].setText(str(total))
        self.stats_labels["current"].setText(str(current))
        self.stats_labels["success"].setText(str(success))
        self.stats_labels["failed"].setText(str(failed))
        self.stats_labels["speed"].setText(f"{speed:.2f} 页/秒")
        self.stats_labels["elapsed"].setText(self.format_seconds(elapsed))
        self.stats_labels["duplicate"].setText("0")
        self.stats_labels["remaining"].setText(self.format_seconds(remaining_seconds))

        self.progress_processed.setText(f"已处理：{current} / {total}")
        self.progress_remaining.setText(f"预计剩余：{self.format_seconds(remaining_seconds)}")
        self.progress_speed.setText(f"速度：{speed:.2f} 页/秒")
        self.progress_elapsed.setText(f"已用时：{self.format_seconds(elapsed)}")

    def reset_stats(self):
        for key in self.stats_labels:
            if key == "speed":
                self.stats_labels[key].setText("0.00 页/秒")
            elif key in ["elapsed", "remaining"]:
                self.stats_labels[key].setText("00:00:00")
            else:
                self.stats_labels[key].setText("0")

        self.progress_processed.setText("已处理：0 / 0")
        self.progress_remaining.setText("预计剩余：00:00:00")
        self.progress_speed.setText("速度：0.00 页/秒")
        self.progress_elapsed.setText("已用时：00:00:00")

    def on_done(self, result):
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if result.get("cancelled"):
            show_info(self, "提示", "任务已停止。")
            return

        if result.get("success"):
            self.data_manager.add_record({
                "type": "面单压缩",
                "source": self.pdf_input.text().strip(),
                "output": result.get("output_dir", ""),
                "total": result.get("page_count", 0),
                "success": result.get("saved_count", 0),
                "failed": len(result.get("failed", [])),
                "elapsed": result.get("elapsed", 0),
                "note": "PDF处理"
            })
            self.refresh_dashboard()
            self.refresh_statistics()
            self.play_done_sound()
            show_info(
                self,
                "完成",
                f"处理完成。\n已保存：{result.get('saved_count')} 个PDF\n输出目录：{result.get('output_dir')}"
            )
        else:
            self.data_manager.add_record({
                "type": "面单压缩失败",
                "source": self.pdf_input.text().strip(),
                "output": result.get("output_dir", ""),
                "total": result.get("page_count", 0),
                "success": result.get("saved_count", 0),
                "failed": len(result.get("failed", [])),
                "elapsed": result.get("elapsed", 0),
                "note": "重复单号" if result.get("duplicate_info") else "识别待检查"
            })
            self.refresh_dashboard()
            self.refresh_statistics()
            self.play_error_sound()
            duplicate = result.get("duplicate_info")
            if duplicate:
                show_warning(
                    self,
                    "发现重复面单",
                    f"重复单号：{duplicate.get('number')}\n首次出现：{duplicate.get('first_location')}\n重复出现：{duplicate.get('current_location')}\n\n任务已停止，未继续生成后续 ZIP。"
                )
            else:
                report = result.get("recognition_report", "")
                message = "任务已停止，请查看运行日志。"
                if report:
                    message += f"\n\n识别报告：{report}\n低置信度页面会保存到 unrecognized_pages 文件夹。"
                show_warning(self, "提示", message)

    def on_error(self, message):
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.add_pdf_log("ERROR", message)
        self.play_error_sound()
        show_warning(self, "提示", message)

    def add_pdf_log(self, level, message):
        if hasattr(self, "log_text"):
            self.write_log_to_widget(self.log_text, level, message)
        if bool(self.settings.get("save_logs", True)):
            self.logger.write(level, message)

    def add_excel_log(self, level, message):
        self.write_log_to_widget(self.excel_log_text, level, message)
        if bool(self.settings.get("save_logs", True)):
            self.logger.write(level, message)

    def write_log_to_widget(self, widget, level, message):
        stamp = time.strftime("%H:%M:%S")
        color = {
            "INFO": "#93C5FD",
            "WARNING": "#FBBF24",
            "ERROR": "#F87171",
            "SUCCESS": "#86EFAC",
        }.get(level, "#D1D5DB")
        badge = {
            "INFO": "INFO",
            "WARNING": "WARN",
            "ERROR": "ERROR",
            "SUCCESS": "SUCCESS",
        }.get(level, level)

        widget.append(
            f"<span style='color:#94A3B8'>[{stamp}]</span> "
            f"<span style='background-color:{color}; color:#0F172A; padding:2px 6px; border-radius:4px;'>{badge}</span> "
            f"<span style='color:#D1D5DB'>{message}</span>"
        )

    def clear_pdf_log(self):
        self.log_text.clear()

    def format_seconds(self, seconds):
        seconds = max(0, int(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def sound_path(self, name):
        return self.resources.sound(name)

    def is_sound_enabled(self):
        return hasattr(self, "sound_enabled") and self.sound_enabled.isChecked()

    def play_click_sound(self):
        if self.is_sound_enabled():
            self.sound_engine.play_click(self.sound_path("ui_click.wav")) if hasattr(self.sound_engine, "play_click") else self.sound_engine.play(self.sound_path("ui_click.wav"))

    def play_scan_success_sound(self):
        if self.is_sound_enabled():
            self.sound_engine.play(self.sound_path("scan_success.wav"))

    def play_scan_error_sound(self):
        self.sound_engine.play(self.sound_path("scan_error.wav"))

    def play_import_sound(self):
        if self.is_sound_enabled():
            self.sound_engine.play_import(self.sound_path("file_import.wav"))

    def play_error_sound(self):
        if self.is_sound_enabled():
            self.sound_engine.play_error(self.sound_path("soft_error.wav")) if hasattr(self.sound_engine, "play_error") else self.sound_engine.play(self.sound_path("soft_error.wav"))

    def play_done_sound(self):
        if self.is_sound_enabled():
            try:
                if hasattr(self.sound_engine, "play_done"):
                    self.sound_engine.play_done(self.sound_path("water_complete.wav"))
                elif hasattr(self.sound_engine, "play_complete"):
                    self.sound_engine.play_complete(self.sound_path("water_complete.wav"))
                else:
                    self.sound_engine.play(self.sound_path("water_complete.wav"))
            except Exception:
                pass

    def on_avatar_clicked(self, event):
        self.avatar_click_count += 1
        if self.avatar_click_count >= 5:
            self.avatar_click_count = 0
            show_info(self, "Developer Mode", "Developer Mode 会在后续版本开放。\n这里将显示 CPU、线程、缓存、PDF耗时和日志。")

    def refresh_dashboard(self):
        stats = self.data_manager.get_stats()
        if hasattr(self, "home_today_card"):
            self.set_info_card_value(self.home_today_card, str(stats["today"]["total"]))
            self.set_info_card_value(self.home_month_card, str(stats["month"]["total"]))
            fastest = stats.get("fastest", 0)
            self.set_info_card_value(self.home_fast_card, f"{fastest:.2f}" if fastest else "--")

        if hasattr(self, "home_recent_table"):
            records = self.data_manager.get_records()[:8]
            self.home_recent_table.setRowCount(len(records))
            for row, record in enumerate(records):
                values = [
                    record.get("time", ""),
                    record.get("type", ""),
                    str(record.get("total", 0)),
                    str(record.get("success", 0)),
                    record.get("output", ""),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.home_recent_table.setItem(row, col, item)

    def set_info_card_value(self, card, value):
        labels = card.findChildren(QLabel)
        for label in labels:
            if label.objectName() == "InfoValue":
                label.setText(value)
                return

    def refresh_history(self):
        records = self.data_manager.get_records()
        self.history_table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                record.get("time", ""),
                record.get("type", ""),
                record.get("source", ""),
                str(record.get("total", 0)),
                str(record.get("success", 0)),
                str(record.get("failed", 0)),
                self.format_seconds(record.get("elapsed", 0)),
                record.get("output", ""),
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))

    def clear_history_records(self):
        self.data_manager.clear_records()
        self.refresh_history()
        self.refresh_dashboard()
        self.refresh_statistics()
        show_info(self, "完成", "处理记录已清空。")

    def open_history_output(self, row, col):
        item = self.history_table.item(row, 7)
        if not item:
            return
        output = item.text()
        if output and Path(output).exists():
            import os
            os.startfile(output)
        else:
            show_warning(self, "提示", "输出目录不存在。")

    def refresh_statistics(self):
        stats = self.data_manager.get_stats()
        if hasattr(self, "stats_today_card"):
            self.set_info_card_value(self.stats_today_card, str(stats["today"]["total"]))
            self.set_info_card_value(self.stats_month_card, str(stats["month"]["total"]))
            self.set_info_card_value(self.stats_all_card, str(stats["all"]["total"]))
            fastest = stats.get("fastest", 0)
            self.set_info_card_value(self.stats_fast_card, f"{fastest:.2f}" if fastest else "--")

        text = (
            f"今日任务数：{stats['today']['tasks']}\n"
            f"今日成功：{stats['today']['success']}，失败：{stats['today']['failed']}\n"
            f"今日平均速度：{stats['today']['speed']:.2f} 单/秒\n\n"
            f"本月任务数：{stats['month']['tasks']}\n"
            f"本月成功：{stats['month']['success']}，失败：{stats['month']['failed']}\n"
            f"本月平均速度：{stats['month']['speed']:.2f} 单/秒\n\n"
            f"累计任务数：{stats['all']['tasks']}\n"
            f"累计成功：{stats['all']['success']}，失败：{stats['all']['failed']}\n"
            f"收藏模板：{stats['templates_count']} 个"
        )
        if hasattr(self, "stats_detail_text"):
            self.stats_detail_text.setText(text)

    def refresh_templates(self):
        templates = self.data_manager.get_templates()
        self.templates_table.setRowCount(len(templates))
        for row, template in enumerate(templates):
            values = [
                template.get("name", ""),
                template.get("type", ""),
                template.get("file_path", "") or template.get("output_dir", ""),
                str(template.get("batch_size", "")),
                "是" if template.get("auto_zip") else "否",
                "是" if template.get("open_output") else "否",
                template.get("created_at", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.templates_table.setItem(row, col, item)

    def save_current_pdf_template(self):
        default_name = f"面单模板_{time.strftime('%m%d_%H%M')}"
        name, ok = QInputDialog, QDialog, QComboBox.getText(self, "保存模板", "请输入模板名称：", text=default_name)
        if not ok or not name.strip():
            return

        template = {
            "name": name.strip(),
            "type": "面单压缩",
            "output_dir": self.output_input.text().strip() if hasattr(self, "output_input") else "",
            "batch_size": int(self.batch_size.value()) if hasattr(self, "batch_size") else 90,
            "auto_zip": bool(self.auto_zip.isChecked()) if hasattr(self, "auto_zip") else True,
            "open_output": bool(self.open_output.isChecked()) if hasattr(self, "open_output") else True,
            "sound_enabled": bool(self.sound_enabled.isChecked()) if hasattr(self, "sound_enabled") else True,
        }
        self.data_manager.add_template(template)
        self.refresh_templates()
        self.refresh_statistics()
        show_info(self, "完成", "模板已收藏。")

    def apply_selected_template(self):
        row = self.templates_table.currentRow()
        templates = self.data_manager.get_templates()
        if row < 0 or row >= len(templates):
            show_warning(self, "提示", "请先选择一个模板。")
            return

        template = templates[row]
        if hasattr(self, "output_input"):
            self.output_input.setText(template.get("output_dir", ""))
        if hasattr(self, "batch_size"):
            self.batch_size.setValue(int(template.get("batch_size", 90) or 90))
        if hasattr(self, "auto_zip"):
            self.auto_zip.setChecked(bool(template.get("auto_zip", True)))
        if hasattr(self, "open_output"):
            self.open_output.setChecked(bool(template.get("open_output", True)))
        if hasattr(self, "sound_enabled"):
            self.sound_enabled.setChecked(bool(template.get("sound_enabled", True)))

        self.save_settings()
        show_info(self, "完成", "模板已应用到面单压缩设置。")

    def delete_selected_template(self):
        row = self.templates_table.currentRow()
        if row < 0:
            show_warning(self, "提示", "请先选择一个模板。")
            return
        self.data_manager.delete_template(row)
        self.refresh_templates()
        self.refresh_statistics()
        show_info(self, "完成", "模板已删除。")

    def select_settings_default_output(self):
        self.play_click_sound()
        path = QFileDialog.getExistingDirectory(self, "选择默认输出目录")
        if path:
            self.settings_default_output.setText(path)

    def save_settings_from_page(self):
        self.settings["last_output_dir"] = self.settings_default_output.text().strip()
        self.settings["batch_size"] = int(self.settings_batch_size.value())
        self.settings["auto_zip"] = bool(self.settings_auto_zip.isChecked())
        self.settings["open_output"] = bool(self.settings_open_output.isChecked())
        self.settings["sound_enabled"] = bool(self.settings_sound.isChecked())
        self.settings["auto_update_check"] = bool(self.settings_auto_update_check.isChecked())
        if hasattr(self, "settings_language"):
            self.settings["language"] = self.settings_language.currentText()
        self.config.save(self.settings)

        if hasattr(self, "output_input"):
            self.output_input.setText(self.settings["last_output_dir"])
        if hasattr(self, "batch_size"):
            self.batch_size.setValue(self.settings["batch_size"])
        if hasattr(self, "auto_zip"):
            self.auto_zip.setChecked(self.settings["auto_zip"])
        if hasattr(self, "open_output"):
            self.open_output.setChecked(self.settings["open_output"])
        if hasattr(self, "sound_enabled"):
            self.sound_enabled.setChecked(self.settings["sound_enabled"])

        show_info(self, "完成", "设置已保存。")

    def reset_recommended_settings(self):
        self.settings_batch_size.setValue(90)
        self.settings_auto_zip.setChecked(True)
        self.settings_open_output.setChecked(True)
        self.settings_sound.setChecked(True)
        self.settings_auto_update_check.setChecked(True)
        show_info(self, "提示", "已恢复推荐设置，请点击“保存设置”生效。")

    def open_selected_history_output(self):
        if not hasattr(self, "history_table"):
            return
        row = self.history_table.currentRow()
        if row < 0:
            show_warning(self, "提示", "请先选择一条处理记录。")
            return
        self.open_history_output(row, 7)

    def refresh_changelog_cards(self):
        if not hasattr(self, "changelog_layout"):
            return

        while self.changelog_layout.count():
            item = self.changelog_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        logs = self.changelog_manager.load()
        if not logs:
            empty = self.create_card("暂无更新日志")
            msg = QLabel("没有读取到 data/changelog.json。")
            msg.setObjectName("BodyText")
            empty.layout().addWidget(msg)
            self.changelog_layout.addWidget(empty)
            return

        for item in logs:
            if not isinstance(item, dict):
                continue

            title = ("🆕 " if item.get("current") else "📌 ") + item.get("version", "")
            card = self.create_card(title)

            date = QLabel(item.get("date", ""))
            date.setObjectName("BodyText")
            card.layout().addWidget(date)

            if item.get("current"):
                badge = QLabel("CURRENT VERSION")
                badge.setObjectName("CurrentBadge")
                card.layout().addWidget(badge)

            self.add_changelog_section(card, "✨ 新增", item.get("added", []))
            self.add_changelog_section(card, "⚡ 优化", item.get("improved", []))
            self.add_changelog_section(card, "🐞 修复", item.get("fixed", []))
            self.changelog_layout.addWidget(card)

    def add_changelog_section(self, card, title, items):
        if not items:
            return
        title_label = QLabel(title)
        title_label.setObjectName("ChangelogSectionTitle")
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.layout().addWidget(title_label)

        body = QLabel("\n".join([f"✔ {text}" for text in items]))
        body.setObjectName("BodyText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.layout().addWidget(body)

    def copy_about_email(self):
        self.play_click_sound()
        clipboard = self.window().clipboard() if hasattr(self.window(), "clipboard") else None
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("zm3491583857@gmail.com")
        show_info(self, "完成", "邮箱已复制。")

    def copy_about_phone(self):
        self.play_click_sound()
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("09037279527")
        show_info(self, "完成", "电话已复制。")

    def get_theme_palette(self, theme_name=None):
        theme_name = theme_name or self.settings.get("theme", "BlackCat Purple（默认）")
        palettes = {
            "BlackCat Purple（默认）": {"accent": "#6D5DF6", "accent_hover": "#5B4CE0", "sidebar": "#0F172A", "soft": "#EDE9FE"},
            "Ocean Blue": {"accent": "#2563EB", "accent_hover": "#1D4ED8", "sidebar": "#0F172A", "soft": "#DBEAFE"},
            "Pure White": {"accent": "#475569", "accent_hover": "#334155", "sidebar": "#111827", "soft": "#F1F5F9"},
            "Sakura Pink": {"accent": "#EC4899", "accent_hover": "#DB2777", "sidebar": "#1F1724", "soft": "#FCE7F3"},
            "Matcha Green": {"accent": "#22C55E", "accent_hover": "#16A34A", "sidebar": "#102016", "soft": "#DCFCE7"},
            "Black Night": {"accent": "#8B5CF6", "accent_hover": "#7C3AED", "sidebar": "#020617", "soft": "#EDE9FE"},
        }
        return palettes.get(theme_name, palettes["BlackCat Purple（默认）"])

    def apply_current_theme(self):
        palette = self.get_theme_palette()
        if hasattr(self, "sidebar"):
            self.sidebar.setStyleSheet(f"background: {palette['sidebar']};")
        accent = palette["accent"]
        hover = palette["accent_hover"]
        soft = palette["soft"]
        extra = f"""
        #SideButton[active="true"] {{
            background: {accent};
            color: white;
            font-weight: 800;
        }}
        #PrimaryButton {{
            background: {accent};
            color: white;
            border: none;
        }}
        #PrimaryButton:hover {{
            background: {hover};
        }}
        #ExcelButton {{
            background: #22C55E;
            color: white;
            border: none;
        }}
        QProgressBar::chunk {{
            border-radius: 11px;
            background: {accent};
        }}
        #InfoValue, #StatValue, #AboutBrand, #Title span {{
            color: {accent};
        }}
        QTableWidget::item:selected {{
            background: {soft};
            color: #111827;
        }}
        """
        self.setStyleSheet(self.styleSheet() + extra)

    def show_theme_center(self):
        self.play_click_sound()
        dialog = QDialog(self)
        dialog.setWindowTitle("主题中心")
        dialog.setFixedSize(520, 320)
        dialog.setStyleSheet("""
        QDialog {
            background: #FFFFFF;
            color: #111827;
            font-family: "Microsoft YaHei UI";
        }
        QLabel {
            color: #111827;
            font-size: 14px;
        }
        QComboBox {
            background: #FFFFFF;
            color: #111827;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 8px 10px;
            min-height: 28px;
        }
        QComboBox QAbstractItemView {
            background: #FFFFFF;
            color: #111827;
            selection-background-color: #EDE9FE;
            selection-color: #111827;
            border: 1px solid #CBD5E1;
        }
        QPushButton {
            background: #FFFFFF;
            color: #111827;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 9px 16px;
            font-weight: 700;
        }
        QPushButton:hover {
            background: #F1F5F9;
        }
        #ThemeSaveButton {
            background: #6D5DF6;
            color: white;
            border: none;
        }
        """)
        layout = QVBoxLayout(dialog)

        title = QLabel("主题中心")
        title.setStyleSheet("font-size: 22px; font-weight: 900; color: #111827;")
        layout.addWidget(title)

        tip = QLabel("选择主题后点击保存，会立即改变左侧菜单、按钮、进度条等强调色。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #475569;")
        layout.addWidget(tip)

        combo = QComboBox()
        combo.addItems(["BlackCat Purple（默认）", "Ocean Blue", "Pure White", "Sakura Pink", "Matcha Green", "Black Night"])
        combo.setCurrentText(self.settings.get("theme", "BlackCat Purple（默认）"))
        layout.addWidget(combo)

        preview = QLabel("预览：按钮 / 进度条 / 菜单高亮 会跟随主题改变")
        preview.setStyleSheet("background:#F8FAFC; border:1px solid #E5E7EB; border-radius:10px; padding:14px; color:#334155;")
        preview.setWordWrap(True)
        layout.addWidget(preview)

        row = QHBoxLayout()
        save_btn = QPushButton("保存并应用")
        save_btn.setObjectName("ThemeSaveButton")
        save_btn.clicked.connect(lambda: self.save_theme_choice(combo.currentText(), dialog))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        row.addStretch()
        row.addWidget(save_btn)
        row.addWidget(close_btn)
        layout.addLayout(row)
        dialog.exec()

    def save_theme_choice(self, theme_name, dialog):
        self.settings["theme"] = theme_name
        self.config.save(self.settings)
        self.apply_current_theme()
        show_info(self, "完成", f"主题已保存并应用：{theme_name}")
        dialog.accept()

    def import_template_file(self):
        self.play_click_sound()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模板文件",
            "",
            "Template Files (*.xlsx *.xlsm *.json)"
        )
        if not path:
            return

        source = Path(path)
        try:
            if source.suffix.lower() == ".json":
                count = self.data_manager.import_templates_json(source)
                self.refresh_templates()
                self.refresh_statistics()
                show_info(self, "完成", f"已从 JSON 导入 {count} 个模板。")
                return

            name, ok = QInputDialog.getText(self, "导入模板", "请输入模板名称：", text=source.stem)
            if not ok or not name.strip():
                return

            self.data_manager.add_file_template(name.strip(), "Excel模板", str(source))
            self.refresh_templates()
            self.refresh_statistics()
            show_info(self, "完成", "模板文件已导入。")
        except Exception as error:
            show_warning(self, "提示", str(error))

    def export_templates_file(self):
        self.play_click_sound()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            "blackcat_templates.json",
            "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            self.data_manager.export_templates(path)
            show_info(self, "完成", f"模板已导出：\\n{path}")
        except Exception as error:
            show_warning(self, "提示", str(error))

    def open_selected_template_location(self):
        row = self.templates_table.currentRow()
        templates = self.data_manager.get_templates()
        if row < 0 or row >= len(templates):
            show_warning(self, "提示", "请先选择一个模板。")
            return
        item = templates[row]
        target = item.get("file_path") or item.get("output_dir")
        if not target:
            show_warning(self, "提示", "这个模板没有可打开的位置。")
            return
        path = Path(target)
        if path.is_file():
            path = path.parent
        if path.exists():
            import os
            os.startfile(path)
        else:
            show_warning(self, "提示", "模板位置不存在。")

    def show_plugin_status(self):
        plugins = self.plugin_manager.discover()
        if not plugins:
            show_info(self, "插件系统", "当前没有发现插件。")
            return
        lines = []
        for plugin in plugins:
            lines.append(f"{plugin.get('name', plugin.get('id', 'unknown'))} - {plugin.get('status', '')}")
        show_info(self, "插件系统", "\n".join(lines))

    def setup_auto_update_checks(self):
        enabled = bool(self.settings.get("auto_update_check", True))
        self.update_auto_update_schedule(enabled, check_now=False)
        if enabled:
            QTimer.singleShot(8000, self.start_background_update_check)
        elif hasattr(self, "update_status_label"):
            self.update_status_label.setText("自动检查已关闭，可随时手动检查更新。")

    def on_auto_update_check_toggled(self, enabled):
        self.settings["auto_update_check"] = bool(enabled)
        self.config.save(self.settings)
        self.update_auto_update_schedule(bool(enabled), check_now=bool(enabled))

    def update_auto_update_schedule(self, enabled, check_now):
        if enabled:
            self.auto_update_timer.start()
            if check_now:
                QTimer.singleShot(0, self.start_background_update_check)
            return
        self.auto_update_timer.stop()
        if hasattr(self, "update_status_label"):
            self.update_status_label.setText("自动检查已关闭，可随时手动检查更新。")

    def start_background_update_check(self):
        if not self.settings.get("auto_update_check", True):
            return
        if self.update_check_thread and self.update_check_thread.isRunning():
            return

        self.update_check_thread = QThread(self)
        self.update_check_worker = UpdateCheckWorker(self.update_manager)
        self.update_check_worker.moveToThread(self.update_check_thread)
        self.update_check_thread.started.connect(self.update_check_worker.run)
        self.update_check_worker.check_finished.connect(self.handle_background_update_result)
        self.update_check_worker.check_finished.connect(self.update_check_thread.quit)
        self.update_check_worker.check_finished.connect(self.update_check_worker.deleteLater)
        self.update_check_thread.finished.connect(self.clear_update_check_worker)
        self.update_check_thread.finished.connect(self.update_check_thread.deleteLater)
        self.update_check_thread.start()

    def clear_update_check_worker(self):
        self.update_check_thread = None
        self.update_check_worker = None

    def handle_background_update_result(self, result):
        self.latest_update_info = result
        outcome = self.update_notification_state.apply(result)
        self.refresh_update_settings_status(result, outcome.get("status", "up_to_date"))
        if outcome.get("should_notify") and self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "发现新版本",
                f"黑猫审单助手 {result.get('latest_version', '')} 已可更新，可在设置中立即更新。",
                QSystemTrayIcon.Information,
                8000,
            )

    def refresh_update_settings_status(self, result, status=None):
        if not hasattr(self, "update_status_label"):
            return
        current_version = result.get("current_version", APP_VERSION)
        latest_version = result.get("latest_version") or "--"
        self.update_version_label.setText(f"当前版本：{current_version}    最新版本：{latest_version}")
        if status == "check_failed" or result.get("remote_error"):
            self.update_status_label.setText("自动检查失败，将在下次检查时重试。")
            self.update_now_button.setEnabled(False)
            return
        if result.get("has_update"):
            self.update_status_label.setText(f"发现新版本 {latest_version}，可立即更新。")
            can_update = bool(result.get("download_url") and result.get("package_sha256"))
            self.update_now_button.setEnabled(can_update)
            return
        self.update_status_label.setText("当前已是最新版本。")
        self.update_now_button.setEnabled(False)

    def open_update_settings(self):
        self.set_page(8)
        self.restore_from_tray()

    def start_latest_update(self):
        if not self.latest_update_info or not self.latest_update_info.get("has_update"):
            show_info(self, "自动更新", "当前没有可安装的新版本。")
            return
        self.start_one_click_update(self.latest_update_info)

    def check_update_status(self):
        result = self.update_manager.check_update()
        self.latest_update_info = result
        self.refresh_update_settings_status(result)
        lines = [
            result.get("message", "暂无更新信息。"),
            f"当前版本：{result.get('current_version', APP_VERSION)}",
        ]
        if result.get("latest_version"):
            lines.append(f"最新版本：{result.get('latest_version')}")
        if result.get("has_update"):
            lines.append("状态：发现新版本")
        else:
            lines.append("状态：当前已是最新版本或未配置远程更新源")
        if result.get("download_url"):
            lines.append(f"下载地址：{result.get('download_url')}")
        if result.get("package_sha256"):
            lines.append(f"SHA256：{result.get('package_sha256')}")

        message = "\n".join(lines)
        if result.get("has_update") and result.get("download_url") and result.get("package_sha256"):
            choice = QMessageBox.question(
                self,
                "自动更新",
                message + "\n\n是否立即下载并安装新版？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice == QMessageBox.Yes:
                self.start_one_click_update(result)
            return

        show_info(self, "自动更新", message)

    def start_one_click_update(self, update_info):
        if not getattr(sys, "frozen", False):
            show_warning(self, "自动更新", "一键更新只在打包安装后的软件中执行。源码测试时请先完成打包验证。")
            return

        prepare_result = self.update_installer.prepare_update(update_info)
        if not prepare_result.get("ok"):
            self.play_error_sound()
            show_warning(self, "自动更新失败", prepare_result.get("message", "更新准备失败。"))
            return

        self.play_done_sound()
        choice = QMessageBox.question(
            self,
            "准备安装",
            prepare_result.get("message", "更新包已准备完成。") + "\n\n点击“是”后软件会退出，并自动安装新版。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if choice != QMessageBox.Yes:
            return

        self.force_quit = True
        if self.tray_icon:
            self.tray_icon.hide()
        self.update_installer.launch_update_script(prepare_result["script_path"])
        QApplication.quit()

    def preload_sounds(self):
        try:
            if hasattr(self, "sound_engine"):
                if hasattr(self.sound_engine, "warm_up"):
                    self.sound_engine.warm_up()
                else:
                    for name in ["ui_click.wav", "scan_success.wav", "water_complete.wav", "water_drop.wav", "file_import.wav", "soft_error.wav"]:
                        try:
                            self.sound_engine.preload(name)
                        except Exception:
                            pass
        except Exception:
            pass

    def closeEvent(self, event):
        self.save_settings()
        if self.force_quit:
            event.accept()
            return

        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            if not self.tray_notice_shown:
                self.tray_icon.showMessage(
                    APP_TITLE,
                    "软件已最小化到右下角托盘。右键托盘图标可退出。",
                    QSystemTrayIcon.Information,
                    3500,
                )
                self.tray_notice_shown = True
            return

        event.accept()
