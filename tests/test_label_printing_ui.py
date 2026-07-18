import unittest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from ui import main_window


class LabelPrintingUiTest(unittest.TestCase):
    @staticmethod
    def application():
        return QApplication.instance() or QApplication([])

    def test_worker_routes_all_form_values_to_label_printing(self):
        expected = {"output_paths": ["out/全部客户_合并_货架排序.pdf"]}

        class Registry:
            def run(self, module_id, context):
                self.module_id = module_id
                self.context = context
                context["progress_callback"]({"current": 1, "total": 1, "message": "完成"})
                return type("Result", (), {"ok": True, "data": expected, "message": ""})()

        registry = Registry()
        worker = main_window.LabelPrintingWorker(registry, {
            "mode": "pdf_only_trial", "pdf_paths": ["labels.pdf"],
            "output_dir": "out", "scope": "by_customer", "split_types": True, "open_after": False,
        })
        results = []
        progress = []
        worker.finished.connect(results.append)
        worker.progress.connect(progress.append)

        worker.run()

        self.assertEqual(registry.module_id, "label_printing")
        self.assertEqual(registry.context["mode"], "pdf_only_trial")
        self.assertEqual(registry.context["scope"], "by_customer")
        self.assertTrue(registry.context["split_types"])
        self.assertFalse(registry.context["open_after"])
        self.assertEqual(results, [expected])
        self.assertEqual(progress[0]["message"], "完成")

    def test_nav_places_label_printing_before_scan_check(self):
        app = self.application()
        window = main_window.MainWindow()
        try:
            labels = [button.text() for button in window.nav_buttons]
            self.assertLess(labels.index("🖨  面单打印"), labels.index("🔍  扫码验单"))
        finally:
            window.close()
            app.processEvents()

    def test_page_exposes_required_selectors_with_exact_values(self):
        app = self.application()
        window = main_window.MainWindow()
        try:
            self.assertEqual(window.label_scope_combo.itemData(0), "all")
            self.assertEqual(window.label_scope_combo.itemData(1), "by_customer")
            self.assertFalse(window.label_split_types_combo.itemData(0))
            self.assertTrue(window.label_split_types_combo.itemData(1))
            self.assertIn("不选择时", window.label_output_dir_input.placeholderText())
        finally:
            window.close()
            app.processEvents()

    def test_pdf_only_page_has_no_excel_or_mode_controls(self):
        app = self.application()
        window = main_window.MainWindow()
        try:
            self.assertFalse(hasattr(window, "label_input_mode"))
            self.assertFalse(hasattr(window, "label_source_input"))
            self.assertFalse(hasattr(window, "label_finished_input"))
            window.label_pdf_input.setText(str(Path(__file__).resolve()))
            window.label_output_dir_input.setText(str(Path.cwd()))
            context = window.get_label_printing_context()
            self.assertEqual(context["mode"], "pdf_only_trial")
            self.assertNotIn("source_path", context)
            self.assertNotIn("finished_path", context)
        finally:
            window.close()
            app.processEvents()

    def test_completion_summary_shows_printed_pages_customer_count_and_type_counts(self):
        app = self.application()
        window = main_window.MainWindow()
        try:
            window.label_printing_started_at = time.monotonic()
            window.add_label_log = MagicMock()
            window.data_manager.add_record = MagicMock()
            window.refresh_dashboard = MagicMock()
            window.refresh_statistics = MagicMock()
            window.play_done_sound = MagicMock()
            result = {
                "output_dir": "out",
                "output_paths": ["out/全部客户_合并_货架排序.pdf"],
                "total_pages": 4,
                "matched_pages": 4,
                "printed_pages": 2,
                "excluded_pages": 2,
                "customer_count": 2,
                "type_counts": {"投函": 1, "宅急便": 3},
            }

            with patch("ui.main_window.show_info") as modal:
                window.handle_label_printing_success(result)

            message = modal.call_args.args[2]
            self.assertIn("已打印页数：2", message)
            self.assertIn("客户数：2", message)
            self.assertIn("投函：1；宅急便：3", message)
        finally:
            window.close()
            app.processEvents()

    def test_zero_output_completion_message_names_missing_sku_one_labels(self):
        app = self.application()
        window = main_window.MainWindow()
        try:
            window.label_printing_started_at = time.monotonic()
            window.add_label_log = MagicMock()
            window.data_manager.add_record = MagicMock()
            window.refresh_dashboard = MagicMock()
            window.refresh_statistics = MagicMock()
            window.play_done_sound = MagicMock()
            result = {
                "output_dir": "out",
                "output_paths": [],
                "total_pages": 2,
                "matched_pages": 2,
                "printed_pages": 0,
                "excluded_pages": 2,
                "customer_count": 1,
                "type_counts": {"投函": 0, "宅急便": 2},
            }

            with patch("ui.main_window.show_info") as modal:
                window.handle_label_printing_success(result)

            message = modal.call_args.args[2]
            self.assertIn("没有可打印的 SKU×1 面单", message)
        finally:
            window.close()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
