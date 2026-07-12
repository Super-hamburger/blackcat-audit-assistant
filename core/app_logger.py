from datetime import datetime
from core.path_manager import PathManager


class AppLogger:
    def __init__(self, log_dir=None):
        self.log_dir = PathManager.logs_dir()

    def write(self, level, message):
        try:
            log_file = self.log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{stamp}] [{level}] {message}\n")
        except Exception:
            pass
