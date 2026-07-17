import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path):
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8") as file:
        return json.load(file)


class ReleaseMetadataTests(unittest.TestCase):
    def test_v4_4_4_release_contract(self):
        version = load_json("version.json")
        changelog = load_json("data/changelog.json")
        manifest = load_json("updater/update_manifest.example.json")

        self.assertEqual("4.4.4", version["version"])
        self.assertEqual("4.4.4", manifest["latest_version"])
        self.assertEqual("V4.4.4", changelog[0]["version"])
        self.assertEqual(1, sum(entry.get("current", False) for entry in changelog))


if __name__ == "__main__":
    unittest.main()
