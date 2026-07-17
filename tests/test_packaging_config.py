import unittest
from pathlib import Path

from core.modules.module_registry import ModuleRegistry


class PortableBuildConfigurationTest(unittest.TestCase):
    def test_registry_discovers_label_printing(self):
        module_ids = [item.module_id for item in ModuleRegistry().discover()]

        self.assertIn("label_printing", module_ids)

    def test_label_printing_module_requires_all_input_categories(self):
        result = ModuleRegistry().run("label_printing", {})

        self.assertFalse(result.ok)
        for key in ("source_path", "finished_path", "pdf_paths", "output_dir"):
            self.assertIn(key, result.message)

    def test_pdf_only_module_does_not_require_excel_paths(self):
        result = ModuleRegistry().run("label_printing", {
            "mode": "pdf_only_trial", "pdf_paths": ["missing.pdf"], "output_dir": "out",
        })

        self.assertFalse(result.ok)
        self.assertNotIn("source_path", result.message)

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
