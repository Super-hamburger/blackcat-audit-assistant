import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.update_installer import UpdateInstaller


class FakeResponse(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class UpdateInstallerProgressTests(unittest.TestCase):
    def test_download_file_reports_known_size_progress(self):
        events = []
        content = b"update-package"

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "update.zip"
            with patch("core.update_installer.urllib.request.urlopen", return_value=FakeResponse(content)):
                UpdateInstaller().download_file("https://example.test/update.zip", target, events.append)

            self.assertEqual(target.read_bytes(), content)

        self.assertEqual(events[-1], {
            "stage": "downloading",
            "message": "正在下载更新包...",
            "downloaded_bytes": len(content),
            "total_bytes": len(content),
        })

    def test_prepare_update_reports_verifying_extracting_and_preparing_stages(self):
        events = []
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            package_path = temporary_path / "update.zip"
            with zipfile.ZipFile(package_path, "w") as archive:
                archive.writestr("BlackCatAuditAssistant/BlackCatAuditAssistant.exe", b"updated-app")
            package_sha256 = UpdateInstaller().file_sha256(package_path)
            install_directory = temporary_path / "installed"
            install_directory.mkdir()
            current_executable = install_directory / "BlackCatAuditAssistant.exe"
            current_executable.write_bytes(b"current-app")

            installer = UpdateInstaller()
            with patch.object(installer, "download_file") as download_file, \
                    patch("core.update_installer.sys.frozen", True, create=True), \
                    patch("core.update_installer.sys.executable", str(current_executable)):
                download_file.side_effect = lambda url, target, progress_callback: target.write_bytes(package_path.read_bytes())
                result = installer.prepare_update({
                    "download_url": "https://example.test/update.zip",
                    "package_sha256": package_sha256,
                    "latest_version": "5.0.1",
                }, events.append)

        self.assertTrue(result["ok"])
        self.assertEqual(
            [event["stage"] for event in events],
            ["verifying", "extracting", "preparing"],
        )
        for event in events:
            self.assertEqual(set(event), {"stage", "message", "downloaded_bytes", "total_bytes"})


if __name__ == "__main__":
    unittest.main()
