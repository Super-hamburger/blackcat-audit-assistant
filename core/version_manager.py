import json
from pathlib import Path


class VersionManager:
    def __init__(self, version_path):
        self.version_path = Path(version_path)
        self.info = self.load()

    def load(self):
        if not self.version_path.exists():
            return {
                "display_name": "黑猫审单助手",
                "version": "unknown",
                "brand": "MADE IN チュウ ビョ",
                "engine": "BlackCat Engine",
            }
        return json.loads(self.version_path.read_text(encoding="utf-8"))

    def get(self, key, default=""):
        return self.info.get(key, default)
