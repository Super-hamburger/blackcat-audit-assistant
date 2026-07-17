import json
import unittest
from pathlib import Path

from ui.main_window import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path):
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8") as file:
        return json.load(file)


class ReleaseMetadataTests(unittest.TestCase):
    def test_v4_4_4_release_contract(self):
        version = load_json("version.json")
        changelog = load_json("data/changelog.json")
        manifest = load_json("updater/update_manifest.example.json")
        file_paste_module = load_json("modules/file_paste/module.json")
        label_printing_module = load_json("modules/label_printing/module.json")

        self.assertEqual("4.4.4", APP_VERSION)
        self.assertEqual("4.4.4", version["version"])
        self.assertEqual("4.4.4", version["engine_version"])
        self.assertEqual("4.4.4", version["ui_version"])
        self.assertEqual("4.4.4", manifest["latest_version"])
        self.assertEqual("", manifest["package_sha256"])
        self.assertEqual("4.4.4", file_paste_module["version"])
        self.assertEqual("4.4.4", label_printing_module["version"])
        self.assertEqual("V4.4.4", changelog[0]["version"])
        self.assertEqual(1, sum(entry.get("current", False) for entry in changelog))


if __name__ == "__main__":
    unittest.main()
