from pathlib import Path
import sys


class ResourceManager:
    def __init__(self, app_dir=None):
        self.app_dir = Path(app_dir) if app_dir else self.runtime_root()

    @staticmethod
    def runtime_root():
        # PyInstaller onefile/onedir uses sys._MEIPASS for bundled resources.
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[1]

    def asset(self, *parts):
        return self.runtime_root() / "assets" / Path(*parts)

    def legacy_ui_resource(self, *parts):
        return self.runtime_root() / "ui" / "resources" / Path(*parts)

    def sound(self, name):
        candidates = [
            self.asset("sounds", name),
            self.legacy_ui_resource("sounds", name),
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def icon(self, name):
        candidates = [
            self.asset("icons", name),
            self.legacy_ui_resource("icons", name),
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def avatar(self, name="blackcat_avatar.png"):
        candidates = [
            self.asset("avatar", name),
            self.asset("icons", name),
            self.legacy_ui_resource("icons", name),
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]
