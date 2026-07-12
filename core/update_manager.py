import json
import re
import urllib.request
from pathlib import Path


class UpdateManager:
    def __init__(self, current_version, manifest_path=None, timeout=8):
        self.current_version = current_version
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self.timeout = int(timeout)

    def load_local_manifest(self):
        if not self.manifest_path or not self.manifest_path.exists():
            return None
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def load_remote_manifest(self, url):
        if not url:
            return None
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BlackCatAuditAssistant-Updater"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)

    def load_manifest(self):
        local_manifest = self.load_local_manifest()
        if not local_manifest:
            return None

        manifest_url = local_manifest.get("manifest_url", "")
        if manifest_url:
            try:
                remote_manifest = self.load_remote_manifest(manifest_url)
                if remote_manifest:
                    remote_manifest.setdefault("manifest_url", manifest_url)
                    return remote_manifest
            except Exception as error:
                local_manifest["remote_error"] = str(error)

        return local_manifest

    def check_update(self):
        manifest = self.load_manifest()
        if not manifest:
            return {
                "has_update": False,
                "message": "没有配置更新源。当前版本为本地稳定版。",
                "current_version": self.current_version,
                "remote_error": "",
            }

        latest = str(manifest.get("latest_version", "")).strip()
        has_update = bool(latest) and self.compare_versions(latest, self.current_version) > 0
        message = manifest.get("message", "")
        if manifest.get("remote_error"):
            message = (message + "\n" if message else "") + f"远程更新源读取失败：{manifest['remote_error']}"

        return {
            "has_update": has_update,
            "current_version": self.current_version,
            "latest_version": latest,
            "message": message,
            "download_url": manifest.get("download_url", ""),
            "package_sha256": manifest.get("package_sha256", ""),
            "release_notes": manifest.get("release_notes", []),
            "mandatory": bool(manifest.get("mandatory", False)),
            "remote_error": manifest.get("remote_error", ""),
        }

    def check_local_update(self):
        return self.check_update()

    @staticmethod
    def compare_versions(left, right):
        left_parts = UpdateManager.version_parts(left)
        right_parts = UpdateManager.version_parts(right)
        max_len = max(len(left_parts), len(right_parts))
        left_parts.extend([0] * (max_len - len(left_parts)))
        right_parts.extend([0] * (max_len - len(right_parts)))
        if left_parts > right_parts:
            return 1
        if left_parts < right_parts:
            return -1
        return 0

    @staticmethod
    def version_parts(value):
        return [int(part) for part in re.findall(r"\d+", str(value))]
