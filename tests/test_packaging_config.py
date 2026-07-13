import unittest
from pathlib import Path


class PortableBuildConfigurationTest(unittest.TestCase):
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
