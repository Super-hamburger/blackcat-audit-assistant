import hashlib
import json
import re
import unittest
from pathlib import Path

from ui.main_window import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path):
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8") as file:
        return json.load(file)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ReleaseMetadataTests(unittest.TestCase):
    def test_v4_4_4_release_contract(self):
        version = load_json("version.json")
        changelog = load_json("data/changelog.json")
        manifest = load_json("updater/update_manifest.example.json")
        file_paste_module = load_json("modules/file_paste/module.json")
        label_printing_module = load_json("modules/label_printing/module.json")
        package_path = PROJECT_ROOT / "release/BlackCatAuditAssistant_Setup_4.4.4.zip"

        self.assertEqual("4.4.4", APP_VERSION)
        self.assertEqual("4.4.4", version["version"])
        self.assertEqual("4.4.4", version["engine_version"])
        self.assertEqual("4.4.4", version["ui_version"])
        self.assertEqual("4.4.4", manifest["latest_version"])
        self.assertTrue(
            package_path.is_file(),
            f"Release package is required for the final release contract: {package_path}",
        )
        self.assertEqual(64, len(manifest["package_sha256"]))
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{64}", manifest["package_sha256"]))
        self.assertEqual(sha256_file(package_path), manifest["package_sha256"])
        self.assertEqual("4.4.4", file_paste_module["version"])
        self.assertEqual("4.4.4", label_printing_module["version"])
        self.assertEqual("V4.4.4", changelog[0]["version"])
        self.assertEqual(1, sum(entry.get("current", False) for entry in changelog))


if __name__ == "__main__":
    unittest.main()
