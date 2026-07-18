import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from core.modules.module_registry import ModuleRegistry


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
app_spec = importlib.util.spec_from_file_location("self_test_app", APP_PATH)
app = importlib.util.module_from_spec(app_spec)
app_spec.loader.exec_module(app)


class PortableBuildConfigurationTest(unittest.TestCase):
    def test_registry_discovers_label_printing(self):
        module_ids = [item.module_id for item in ModuleRegistry().discover()]

        self.assertIn("label_printing", module_ids)

    def test_label_printing_module_requires_pdf_inputs_only(self):
        result = ModuleRegistry().run("label_printing", {})

        self.assertFalse(result.ok)
        self.assertIn("pdf_paths", result.message)
        self.assertIn("output_dir", result.message)
        self.assertNotIn("source_path", result.message)

    def test_pdf_only_module_does_not_require_excel_paths(self):
        result = ModuleRegistry().run("label_printing", {
            "mode": "pdf_only_trial", "pdf_paths": ["missing.pdf"], "output_dir": "out",
        })

        self.assertFalse(result.ok)
        self.assertNotIn("source_path", result.message)

    def test_self_test_exercises_only_pdf_only_label_printing_sample(self):
        with tempfile.TemporaryDirectory() as temp_name:
            report_path = Path(temp_name) / "self_test_report.json"

            exit_code = app.run_self_test(report_path)

            report = json.loads(report_path.read_text(encoding="utf-8"))

        check_names = [check["name"] for check in report["checks"]]
        self.assertEqual(0, exit_code)
        self.assertTrue(report["ok"])
        self.assertNotIn("run label_printing sample pdf", check_names)
        self.assertIn("run pdf_only_trial sample pdf", check_names)

    def test_portable_build_uses_resource_collecting_specification(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "installer" / "build_portable.bat").read_text(encoding="utf-8")

        self.assertIn("BlackCatAuditAssistant.spec", script)

    def test_spec_recursively_collects_project_resource_files(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "BlackCatAuditAssistant.spec").read_text(encoding="utf-8")

        self.assertIn("path.rglob", spec)


if __name__ == "__main__":
    unittest.main()
