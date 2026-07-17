import unittest

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
            "source_path": "source.xlsx", "finished_path": "finished.xlsx", "pdf_paths": ["labels.pdf"],
            "output_dir": "out", "scope": "by_customer", "split_types": True, "open_after": False,
        })
        results = []
        progress = []
        worker.finished.connect(results.append)
        worker.progress.connect(progress.append)

        worker.run()

        self.assertEqual(registry.module_id, "label_printing")
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


if __name__ == "__main__":
    unittest.main()
