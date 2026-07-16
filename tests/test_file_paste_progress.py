import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton

from modules.file_paste.converter import ConversionCancelled, ConversionControl
from ui import main_window


class FilePasteProgressTest(unittest.TestCase):
    @staticmethod
    def progress_window():
        QApplication.instance() or QApplication([])
        window = type("ProgressWindow", (), {})()
        window.excel_progress_bar = QProgressBar()
        window.excel_progress_status = QLabel()
        window.excel_pause_button = QPushButton()
        window.excel_cancel_button = QPushButton()
        window.excel_conversion_control = ConversionControl()
        window.close_excel_progress_and_report = lambda: None
        return window

    def test_background_worker_returns_the_module_result(self):
        expected = {"output_path": "C:/temp/output.xlsx"}

        class Registry:
            def run(self, module_id, context):
                self.module_id = module_id
                self.context = context
                return type("Result", (), {"ok": True, "data": expected, "message": ""})()

        registry = Registry()
        worker = main_window.ExcelConversionWorker(registry, {"source_path": "source.xlsx"})
        results = []
        errors = []
        worker.finished.connect(results.append)
        worker.failed.connect(errors.append)

        worker.run()

        self.assertEqual(registry.module_id, "file_paste")
        self.assertEqual(results, [expected])
        self.assertEqual(errors, [])

    def test_background_worker_forwards_conversion_progress(self):
        expected = {"output_path": "C:/temp/output.xlsx"}

        class Registry:
            def run(self, module_id, context):
                context["progress_callback"]({
                    "phase": "reading",
                    "message": "正在读取数据（1/1）",
                    "current": 1,
                    "total": 1,
                    "indeterminate": False,
                })
                return type("Result", (), {"ok": True, "data": expected, "message": ""})()

        worker = main_window.ExcelConversionWorker(Registry(), {"source_path": "source.xlsx"})
        progress_events = []
        worker.progress.connect(progress_events.append)

        worker.run()

        self.assertEqual(len(progress_events), 1)
        self.assertEqual(progress_events[0]["phase"], "reading")
        self.assertEqual(progress_events[0]["current"], 1)

    def test_background_worker_reports_a_cancelled_conversion_without_error(self):
        class Registry:
            def run(self, module_id, context):
                raise ConversionCancelled()

        worker = main_window.ExcelConversionWorker(Registry(), {"source_path": "source.xlsx"})
        cancelled = []
        errors = []
        worker.cancelled.connect(lambda: cancelled.append(True))
        worker.failed.connect(errors.append)

        worker.run()

        self.assertEqual(cancelled, [True])
        self.assertEqual(errors, [])

    def test_real_progress_uses_rows_and_busy_bar_for_save(self):
        window = self.progress_window()

        main_window.MainWindow.on_excel_conversion_progress(window, {
            "phase": "writing",
            "message": "正在写入上传表（12/60）",
            "current": 12,
            "total": 60,
            "indeterminate": False,
        })

        self.assertEqual(window.excel_progress_bar.maximum(), 60)
        self.assertEqual(window.excel_progress_bar.value(), 12)
        self.assertEqual(window.excel_progress_status.text(), "正在写入上传表（12/60）")

        main_window.MainWindow.on_excel_conversion_progress(window, {
            "phase": "saving",
            "message": "正在保存上传表...",
            "indeterminate": True,
        })

        self.assertEqual(window.excel_progress_bar.maximum(), 0)
        self.assertEqual(window.excel_progress_status.text(), "正在保存上传表...")

    def test_pause_continue_and_cancel_control_conversion(self):
        window = self.progress_window()

        main_window.MainWindow.toggle_excel_conversion_pause(window)
        self.assertTrue(window.excel_conversion_control.paused)
        self.assertEqual(window.excel_pause_button.text(), "继续")

        main_window.MainWindow.toggle_excel_conversion_pause(window)
        self.assertFalse(window.excel_conversion_control.paused)
        self.assertEqual(window.excel_pause_button.text(), "暂停")

        main_window.MainWindow.cancel_excel_conversion(window)
        self.assertTrue(window.excel_conversion_control.cancelled)
        self.assertFalse(window.excel_pause_button.isEnabled())
        self.assertFalse(window.excel_cancel_button.isEnabled())
        self.assertIn("正在结束", window.excel_progress_status.text())

    def test_cancelled_task_does_not_show_a_false_completed_progress(self):
        window = self.progress_window()
        window.excel_progress_bar.setRange(0, 60)
        window.excel_progress_bar.setValue(12)
        window.excel_conversion_cancelled = True
        window.excel_pending_error = None

        with patch.object(main_window.QTimer, "singleShot"):
            main_window.MainWindow.finish_excel_progress(window)

        self.assertEqual(window.excel_progress_bar.maximum(), 60)
        self.assertEqual(window.excel_progress_bar.value(), 12)
        self.assertIn("任务已结束", window.excel_progress_status.text())

    def test_main_window_initializes_without_a_synthetic_excel_progress_timer(self):
        app = QApplication.instance() or QApplication([])
        window = main_window.MainWindow()
        try:
            self.assertFalse(hasattr(window, "excel_progress_timer"))
        finally:
            window.close()
            app.processEvents()

    def test_progress_dialog_ignores_escape_rejection(self):
        app = QApplication.instance() or QApplication([])
        dialog = main_window.ExcelProgressDialog()
        dialog.show()
        app.processEvents()

        dialog.reject()

        self.assertTrue(dialog.isVisible())
        dialog.close()

    def test_quit_from_tray_cancels_active_conversion_before_quitting(self):
        control = ConversionControl()

        class Thread:
            @staticmethod
            def isRunning():
                return True

        window = type("TrayWindow", (), {})()
        window.excel_conversion_thread = Thread()
        window.excel_conversion_control = control
        window.excel_pause_button = None
        window.excel_cancel_button = None
        window.excel_progress_status = None
        window.excel_quit_after_cancellation = False

        with patch.object(main_window.QApplication, "quit") as application_quit:
            main_window.MainWindow.quit_from_tray(window)

        self.assertTrue(control.cancelled)
        self.assertTrue(window.excel_quit_after_cancellation)
        application_quit.assert_not_called()

    def test_thread_cleanup_finishes_a_pending_tray_quit(self):
        window = type("TrayWindow", (), {})()
        window.excel_conversion_worker = object()
        window.excel_conversion_thread = object()
        window.excel_quit_after_cancellation = True
        completed = []
        window.finish_application_quit = lambda: completed.append(True)

        main_window.MainWindow.clear_excel_conversion_worker(window)

        self.assertIsNone(window.excel_conversion_worker)
        self.assertIsNone(window.excel_conversion_thread)
        self.assertEqual(completed, [True])


if __name__ == "__main__":
    unittest.main()
