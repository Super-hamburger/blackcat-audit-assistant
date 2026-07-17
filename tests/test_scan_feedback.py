import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QFrame, QLabel, QLineEdit, QProgressBar, QScrollArea

from ui.main_window import MainWindow, ScanInputController


class FakeSoundEngine:
    def __init__(self):
        self.paths = []

    def play(self, path):
        self.paths.append(path)


class FakeText:
    def __init__(self, value):
        self.value = value

    def setText(self, value):
        self.value = value


class ScanFeedbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_scan_error_sound_is_valid_mono_wav(self):
        path = Path("assets/sounds/scan_error.wav")

        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertGreater(audio.getframerate(), 0)
            self.assertGreater(audio.getnframes(), 0)

    def test_scan_error_sound_bypasses_general_sound_setting(self):
        window = MainWindow.__new__(MainWindow)
        window.sound_engine = FakeSoundEngine()
        window.sound_path = lambda name: f"sounds/{name}"

        MainWindow.play_scan_error_sound(window)

        self.assertEqual(window.sound_engine.paths, ["sounds/scan_error.wav"])

    def window_with_blocked_scan_result(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_input = QLineEdit()
        window.scan_input.show()
        window.scan_input.setText("UNKNOWN-SKU")
        window.scan_block_enabled = QCheckBox()
        window.scan_block_enabled.setChecked(True)
        window.scan_service = SimpleNamespace(
            scan=lambda code: {"result": "block", "message": "SKU 不在当前出库单中"},
        )
        window.apply_scan_result = lambda result: None
        window.play_scan_error_sound = lambda: None
        self.application.processEvents()
        return window

    def progress_window(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_metric_total_card = object()
        window.scan_metric_pass_card = object()
        window.scan_metric_fail_card = object()
        window.scan_metric_rate_card = object()
        window.set_info_card_value = lambda card, value: None
        window.scan_progress_bar = QProgressBar()
        window.scan_percent_label = QLabel()
        return window

    def status_window(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_gate_status = QLabel()
        window.scan_gate_sub = QLabel()
        window.scan_gate_frame = QFrame()
        window.scan_gate_icon = QLabel()
        window.scan_current_result = QLabel()
        window.scan_order_hero_frame = QFrame()
        window.scan_current_order = QLabel()
        window.scan_order_time = QLabel()
        window.scan_current_sku = QLabel()
        window.scan_product_name = QLabel()
        window.scan_success_time = QLabel()
        return window

    def test_scan_workbench_keeps_current_result_in_viewport_at_minimum_size(self):
        window = MainWindow()
        try:
            window.resize(1160, 760)
            window.set_page(3)
            window.show()
            self.application.processEvents()

            viewport = next(
                area.viewport()
                for area in window.findChildren(QScrollArea)
                if area.isVisible()
            )
            viewport_top = viewport.mapTo(window, viewport.rect().topLeft()).y()
            viewport_bottom = viewport.mapTo(window, viewport.rect().bottomLeft()).y()
            order_top = window.scan_current_order.mapTo(
                window, window.scan_current_order.rect().topLeft()
            ).y()
            result_bottom = window.scan_current_result.mapTo(
                window, window.scan_current_result.rect().bottomLeft()
            ).y()

            self.assertGreaterEqual(order_top, viewport_top)
            self.assertLessEqual(result_bottom, viewport_bottom)
        finally:
            window.close()

    def test_blocked_scan_does_not_open_a_modal_warning_and_refocuses_input(self):
        window = self.window_with_blocked_scan_result()
        try:
            with patch("ui.main_window.show_warning") as warning:
                MainWindow.handle_scan_input(window)

            warning.assert_not_called()
            self.assertTrue(window.scan_input.hasFocus())
        finally:
            window.scan_input.close()

    def test_scan_summary_shows_matched_count_and_total(self):
        window = self.progress_window()

        MainWindow.update_scan_summary(window, {
            "total_scans": 3, "passed": 2, "failed": 1, "pass_rate": 66.7,
            "matched_count": 2, "matchable_count": 5, "progress_percent": 40,
        })

        self.assertEqual(window.scan_progress_bar.value(), 40)
        self.assertEqual(window.scan_percent_label.text(), "已匹配 2 / 5（40%）")

    def test_scan_summary_keeps_progress_label_in_hero_format(self):
        window = self.progress_window()

        MainWindow.update_scan_summary(window, {
            "total_scans": 4, "passed": 3, "failed": 1, "pass_rate": 75,
            "matched_count": 3, "matchable_count": 8, "progress_percent": 38,
        })

        self.assertEqual(window.scan_percent_label.text(), "已匹配 3 / 8（38%）")

    def test_scan_order_hero_changes_color_for_blocked_state(self):
        window = self.status_window()

        MainWindow.set_scan_status_visual(window, "block", "已拦截", "SKU 不属于当前出库单")

        self.assertIn("#FEF2F2", window.scan_order_hero_frame.styleSheet())

    def test_ready_order_hero_uses_light_secondary_text_on_dark_background(self):
        window = self.status_window()

        MainWindow.set_scan_order_hero_style(window, "ready")

        self.assertIn("#E2E8F0", window.scan_order_time.styleSheet())
        self.assertIn("#E2E8F0", window.scan_product_name.styleSheet())
        self.assertIn("#E2E8F0", window.scan_success_time.styleSheet())
        self.assertIn("#C4B5FD", window.scan_current_sku.styleSheet())

    def test_blocked_scan_reset_restores_waiting_text_only_for_current_token(self):
        window = MainWindow.__new__(MainWindow)
        window._scan_status_visual_token = 7
        window.scan_current_result = FakeText("SKU 不属于当前出库单")
        visual_updates = []
        window.set_scan_status_visual = lambda state, title, subtitle: visual_updates.append(
            (state, title, subtitle)
        )

        MainWindow._reset_scan_status_visual_if_current(window, 7)

        self.assertEqual(window.scan_current_result.value, "等待扫码")
        self.assertEqual(visual_updates, [("ready", "放行中", "一扫正确，可以继续扫描")])

        window._scan_status_visual_token = 8
        window.scan_current_result.setText("新的扫码结果")
        MainWindow._reset_scan_status_visual_if_current(window, 7)

        self.assertEqual(window.scan_current_result.value, "新的扫码结果")
        self.assertEqual(visual_updates, [("ready", "放行中", "一扫正确，可以继续扫描")])

    def test_scan_input_prefers_lowercase_latin_input(self):
        input_widget = QLineEdit()
        ScanInputController(input_widget, lambda: None)
        hints = input_widget.inputMethodHints()

        self.assertTrue(hints & Qt.ImhLatinOnly)
        self.assertTrue(hints & Qt.ImhPreferLowercase)


if __name__ == "__main__":
    unittest.main()
