import json
import sys
from pathlib import Path


class ChangelogManager:
    def __init__(self, path=None):
        self.path = Path(path) if path else None

    def _project_root(self):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[1]

    def _candidate_paths(self):
        paths = []
        packaged = self._project_root() / "data" / "changelog.json"
        paths.append(packaged)
        if self.path:
            paths.append(self.path)
        return paths

    def load(self):
        for path in self._candidate_paths():
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, list) and data:
                        return data
            except Exception:
                continue
        return []
