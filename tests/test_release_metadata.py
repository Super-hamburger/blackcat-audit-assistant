import hashlib
import json
import os
import re
import unittest
from pathlib import Path
from zipfile import ZipFile

from ui.main_window import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ASSET_ENV = "BLACKCAT_RELEASE_ASSET"
RELEASE_ASSET_NAME = "BlackCatAuditAssistant_Setup_5.0.0.zip"
RELEASE_ROOT = "BlackCatAuditAssistant"
EXPECTED_PUBLISHED_AT = "2026-07-18T19:30:00+08:00"
OLD_RELEASE_TEXT = ("尚未上传 GitHub", "自动更新尚不可用")


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
    def test_v5_0_0_metadata_contract(self):
        version = load_json("version.json")
        changelog = load_json("data/changelog.json")
        manifest = load_json("updater/update_manifest.example.json")
        file_paste_module = load_json("modules/file_paste/module.json")
        label_printing_module = load_json("modules/label_printing/module.json")
        release_notes_path = PROJECT_ROOT / "docs/RELEASE_5.0.0.md"

        self.assertEqual("5.0.0", APP_VERSION)
        self.assertEqual("5.0.0", version["version"])
        self.assertEqual("5.0.0", version["engine_version"])
        self.assertEqual("5.0.0", version["ui_version"])
        self.assertEqual("5.0.0", manifest["latest_version"])
        self.assertEqual(64, len(manifest["package_sha256"]))
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{64}", manifest["package_sha256"]))
        release_notes = release_notes_path.read_text(encoding="utf-8")
        release_notes_hash = re.search(r"SHA256：`([0-9a-f]{64})`", release_notes)
        self.assertIsNotNone(release_notes_hash)
        self.assertEqual(manifest["package_sha256"], release_notes_hash.group(1))
        self.assertIn("5.0.0", release_notes)
        self.assertIn("自动更新", release_notes)
        self.assertIn("5.0.0 已正式发布", manifest["message"])
        self.assertIn("自动更新", manifest["message"])
        self.assertEqual(EXPECTED_PUBLISHED_AT, manifest["published_at"])
        self.assertEqual("5.0.0", file_paste_module["version"])
        self.assertEqual("5.0.0", label_printing_module["version"])
        self.assertEqual("V5.0.0", changelog[0]["version"])
        self.assertEqual(1, sum(entry.get("current", False) for entry in changelog))

    @unittest.skipUnless(
        os.environ.get(RELEASE_ASSET_ENV),
        f"set {RELEASE_ASSET_ENV} to validate a release ZIP",
    )
    def test_release_asset_contract_when_explicitly_requested(self):
        package_path = Path(os.environ[RELEASE_ASSET_ENV])
        manifest = load_json("updater/update_manifest.example.json")
        release_notes = (PROJECT_ROOT / "docs/RELEASE_5.0.0.md").read_text(encoding="utf-8")

        self.assertEqual(RELEASE_ASSET_NAME, package_path.name)
        self.assertTrue(package_path.is_file(), f"Release package is required: {package_path}")
        self.assertEqual(sha256_file(package_path), manifest["package_sha256"])
        self.assertIn(manifest["package_sha256"], release_notes)

        with ZipFile(package_path) as archive:
            names = archive.namelist()
            top_levels = {name.split("/", 1)[0] for name in names if name}
            self.assertEqual({RELEASE_ROOT}, top_levels)
            self.assertEqual(
                [f"{RELEASE_ROOT}/{RELEASE_ROOT}.exe"],
                [name for name in names if name.endswith("/BlackCatAuditAssistant.exe")],
            )
            self.assertFalse(any("/output/" in f"/{name.lower()}" for name in names))
            self.assertFalse(any("self_test" in name.lower() for name in names))
            embedded_manifest = json.loads(
                archive.read(
                    f"{RELEASE_ROOT}/_internal/updater/update_manifest.example.json"
                ).decode("utf-8")
            )

        embedded_text = json.dumps(embedded_manifest, ensure_ascii=False)
        self.assertEqual("5.0.0", embedded_manifest["latest_version"])
        self.assertIn("5.0.0 已正式发布", embedded_manifest["message"])
        self.assertIn("自动更新", embedded_manifest["message"])
        self.assertEqual(EXPECTED_PUBLISHED_AT, embedded_manifest["published_at"])
        self.assertEqual("", embedded_manifest["package_sha256"])
        for obsolete_text in OLD_RELEASE_TEXT:
            self.assertNotIn(obsolete_text, embedded_text)


if __name__ == "__main__":
    unittest.main()
