import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton

from core.config_manager import DEFAULT_SETTINGS
from core.update_manager import UpdateManager
from core.update_notification import UpdateNotificationState
from ui import main_window


class FailingRemoteUpdateManager(UpdateManager):
    def load_local_manifest(self):
        return {
            "latest_version": "4.3.1",
            "manifest_url": "https://updates.example.test/update_manifest.json",
        }

    def load_remote_manifest(self, url):
        raise OSError("offline")


class RecordingUpdateManager:
    current_version = "5.0.0"

    def __init__(self, result):
        self.result = result
        self.ran_on_gui_thread = None

    def check_update(self):
        self.ran_on_gui_thread = QThread.currentThread() is QApplication.instance().thread()
        return dict(self.result)


class RecordingUpdateInstaller:
    def __init__(self, results):
        self.results = list(results)
        self.prepare_threads = []
        self.launched_scripts = []

    def prepare_update(self, update_info, progress_callback=None):
        self.prepare_threads.append(QThread.currentThread() is QApplication.instance().thread())
        if progress_callback:
            progress_callback({
                "stage": "downloading",
                "message": "正在下载更新包...",
                "downloaded_bytes": 1,
                "total_bytes": 2,
            })
        return dict(self.results.pop(0))

    def launch_update_script(self, script_path):
        self.launched_scripts.append(script_path)


class QueuedCleanupUpdateInstaller(RecordingUpdateInstaller):
    def __init__(self):
        super().__init__([
            {"ok": False, "message": "下载失败。"},
            {"ok": True, "message": "更新包已准备完成。", "script_path": "C:/temp/apply_update.bat"},
        ])
        self.second_started = threading.Event()
        self.release_second = threading.Event()

    def prepare_update(self, update_info, progress_callback=None):
        call_index = len(self.prepare_threads)
        if call_index == 1:
            self.second_started.set()
            self.release_second.wait(3.0)
        return super().prepare_update(update_info, progress_callback)


class UpdateNotificationStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def make_window(self, update_manager=None, update_installer=None):
        window = main_window.MainWindow.__new__(main_window.MainWindow)
        QMainWindow.__init__(window)
        window.update_manager = update_manager
        window.update_installer = update_installer
        window.update_notification_state = UpdateNotificationState()
        window.latest_update_info = None
        window.update_check_thread = None
        window.update_check_worker = None
        window.update_check_manual = False
        window.update_install_thread = None
        window.update_install_worker = None
        window.update_install_info = None
        window.update_prepare_result = None
        window.update_retry_requested = False
        window.update_confirm_dialog = None
        window.update_progress_dialog = None
        window.update_check_buttons = [QPushButton("检查更新", window)]
        window.update_now_button = QPushButton("立即更新", window)
        window.update_status_label = QLabel(window)
        window.update_version_label = QLabel(window)
        window.update_check_action = None
        window.tray_icon = None
        window.force_quit = False
        window.play_done_sound = lambda: None
        window.play_error_sound = lambda: None
        return window

    def wait_until(self, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        self.assertTrue(predicate(), "timed out waiting for Qt worker completion")

    def test_new_version_notifies_only_once_per_session(self):
        state = UpdateNotificationState()
        update_result = {
            "has_update": True,
            "current_version": "4.3.1",
            "latest_version": "4.4.0",
        }

        first = state.apply(update_result)
        second = state.apply(update_result)

        self.assertEqual(first["status"], "update_available")
        self.assertTrue(first["should_notify"])
        self.assertFalse(second["should_notify"])

    def test_network_error_does_not_request_notification(self):
        state = UpdateNotificationState()

        outcome = state.apply({"has_update": False, "remote_error": "offline"})

        self.assertEqual(outcome["status"], "check_failed")
        self.assertFalse(outcome["should_notify"])

    def test_default_settings_enable_automatic_update_checks(self):
        self.assertTrue(DEFAULT_SETTINGS["auto_update_check"])

    def test_update_manager_returns_remote_error_for_background_status(self):
        result = FailingRemoteUpdateManager("4.3.1").check_update()

        self.assertEqual(result["remote_error"], "offline")

    def test_manual_check_runs_off_gui_thread_and_restores_controls(self):
        manager = RecordingUpdateManager({
            "has_update": False,
            "current_version": "5.0.0",
            "latest_version": "5.0.0",
            "message": "当前已是最新版本。",
        })
        window = self.make_window(update_manager=manager)

        with patch.object(main_window, "show_info"):
            main_window.MainWindow.check_update_status(window)
            self.assertFalse(window.update_check_buttons[0].isEnabled())
            self.wait_until(lambda: window.update_check_thread is None)

        self.assertFalse(manager.ran_on_gui_thread)
        self.assertTrue(window.update_check_buttons[0].isEnabled())
        window.deleteLater()

    def test_install_preparation_is_async_and_restart_requires_explicit_confirmation(self):
        installer = RecordingUpdateInstaller([{
            "ok": True,
            "message": "更新包已准备完成。",
            "script_path": "C:/temp/apply_update.bat",
        }])
        window = self.make_window(update_installer=installer)
        update_info = {
            "has_update": True,
            "current_version": "5.0.0",
            "latest_version": "5.0.1",
            "download_url": "https://updates.example.test/update.zip",
            "package_sha256": "a" * 64,
        }

        with (
            patch.object(main_window.sys, "frozen", True, create=True),
            patch.object(main_window.QMessageBox, "question", return_value=main_window.QMessageBox.No),
            patch.object(main_window.QApplication, "quit") as application_quit,
        ):
            main_window.MainWindow.start_one_click_update(window, update_info)
            self.wait_until(lambda: window.update_install_thread is None)

            self.assertEqual(installer.prepare_threads, [False])
            self.assertEqual(installer.launched_scripts, [])
            application_quit.assert_not_called()

            main_window.MainWindow.confirm_update_restart(window)

            self.assertEqual(installer.launched_scripts, ["C:/temp/apply_update.bat"])
            application_quit.assert_called_once_with()

        window.deleteLater()

    def test_retry_starts_a_fresh_install_worker(self):
        installer = RecordingUpdateInstaller([
            {"ok": False, "message": "下载失败。"},
            {"ok": True, "message": "更新包已准备完成。", "script_path": "C:/temp/apply_update.bat"},
        ])
        window = self.make_window(update_installer=installer)
        update_info = {
            "has_update": True,
            "current_version": "5.0.0",
            "latest_version": "5.0.1",
            "download_url": "https://updates.example.test/update.zip",
            "package_sha256": "a" * 64,
        }

        with (
            patch.object(main_window.sys, "frozen", True, create=True),
            patch.object(main_window, "show_warning"),
        ):
            main_window.MainWindow.start_one_click_update(window, update_info)
            first_worker = window.update_install_worker
            self.wait_until(lambda: window.update_install_thread is None)

            main_window.MainWindow.retry_latest_update(window)
            second_worker = window.update_install_worker
            self.assertIsNot(first_worker, second_worker)
            self.wait_until(lambda: window.update_install_thread is None)

        self.assertEqual(len(installer.prepare_threads), 2)
        self.assertTrue(window.update_prepare_result["ok"])
        window.deleteLater()

    def test_failed_result_reopens_a_progress_dialog_closed_while_active(self):
        window = self.make_window()
        window.update_progress_dialog = main_window.UpdateProgressDialog(window)
        window.update_progress_dialog.show()
        self.application.processEvents()
        window.update_progress_dialog.reject()
        self.assertFalse(window.update_progress_dialog.isVisible())

        main_window.MainWindow.handle_update_install_result(
            window,
            {"ok": False, "message": "下载失败。"},
        )
        self.application.processEvents()

        self.assertTrue(window.update_progress_dialog.isVisible())
        self.assertTrue(window.update_progress_dialog.retry_button.isVisible())
        window.update_progress_dialog.close()
        window.deleteLater()

    def test_retry_waits_for_queued_cleanup_and_stale_cleanup_cannot_clear_new_worker(self):
        installer = QueuedCleanupUpdateInstaller()
        window = self.make_window(update_installer=installer)
        update_info = {
            "has_update": True,
            "current_version": "5.0.0",
            "latest_version": "5.0.1",
            "download_url": "https://updates.example.test/update.zip",
            "package_sha256": "a" * 64,
        }
        threads_to_wait = []
        kept_old_reference = False
        stale_cleanup_preserved_new_task = False

        with patch.object(main_window.sys, "frozen", True, create=True):
            main_window.MainWindow.start_one_click_update(window, update_info)
            old_thread = window.update_install_thread
            deadline = time.monotonic() + 3.0
            while len(installer.prepare_threads) < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(installer.prepare_threads), 1)
            old_thread.quit()
            self.assertTrue(old_thread.wait(3000))
            self.assertFalse(old_thread.isRunning())
            self.assertIs(window.update_install_thread, old_thread)

            try:
                main_window.MainWindow.retry_latest_update(window)
                kept_old_reference = window.update_install_thread is old_thread
                if kept_old_reference:
                    self.wait_until(installer.second_started.is_set)
                    new_thread = window.update_install_thread
                    threads_to_wait.append(new_thread)
                    self.assertIsNot(new_thread, old_thread)
                    main_window.MainWindow.clear_update_install_worker(window, old_thread)
                    stale_cleanup_preserved_new_task = window.update_install_thread is new_thread
            finally:
                current_thread = window.update_install_thread
                if current_thread and current_thread not in threads_to_wait:
                    threads_to_wait.append(current_thread)
                installer.release_second.set()
                for thread in threads_to_wait:
                    if thread and thread.isRunning():
                        thread.quit()
                        thread.wait(3000)
                self.application.processEvents()

        self.assertTrue(kept_old_reference)
        self.assertTrue(stale_cleanup_preserved_new_task)
        window.deleteLater()


if __name__ == "__main__":
    unittest.main()
