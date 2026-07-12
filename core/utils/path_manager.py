from pathlib import Path
import os
import sys
import tempfile


class PathManager:
    APP_FOLDER_NAME = "BlackCatAuditAssistant"

    @staticmethod
    def project_root():
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def desktop_dir():
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            return desktop
        one_drive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if one_drive:
            od_desktop = Path(one_drive) / "Desktop"
            if od_desktop.exists():
                return od_desktop
        return Path.home()

    @staticmethod
    def app_data_dir():
        base = os.environ.get("LOCALAPPDATA")
        path = Path(base) / PathManager.APP_FOLDER_NAME if base else Path.home() / f".{PathManager.APP_FOLDER_NAME}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def writable_base_dir():
        candidates = [PathManager.desktop_dir() / PathManager.APP_FOLDER_NAME, PathManager.app_data_dir(), Path(tempfile.gettempdir()) / PathManager.APP_FOLDER_NAME]
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                probe = candidate / ".write_test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return candidate
            except Exception:
                continue
        return PathManager.app_data_dir()

    @staticmethod
    def output_dir():
        path = PathManager.writable_base_dir() / "output"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def logs_dir():
        path = PathManager.writable_base_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def data_dir():
        path = PathManager.writable_base_dir() / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def runtime_data_dir():
        return PathManager.data_dir()
