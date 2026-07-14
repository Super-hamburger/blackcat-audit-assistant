import unittest

from ui import main_window


class FilePasteProgressTest(unittest.TestCase):
    def test_minimum_progress_delay_fills_the_remaining_time(self):
        remaining = getattr(main_window, "minimum_remaining_progress_ms", lambda *_: -1)

        self.assertEqual(remaining(0.5, 2.0), 500)

    def test_minimum_progress_delay_is_zero_after_two_seconds(self):
        remaining = getattr(main_window, "minimum_remaining_progress_ms", lambda *_: -1)

        self.assertEqual(remaining(0.0, 2.5), 0)

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


if __name__ == "__main__":
    unittest.main()
