from pathlib import Path
from core.utils.path_manager import PathManager


def ensure_writable_dir(path, fallback_name="output"):
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except Exception:
        fallback = PathManager.writable_base_dir() / fallback_name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def safe_output_path(path, fallback_name="output"):
    path = Path(path)
    return ensure_writable_dir(path.parent, fallback_name) / path.name
