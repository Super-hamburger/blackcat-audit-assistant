import json
from pathlib import Path
from core.path_manager import PathManager

DEFAULT_SETTINGS = {
    "batch_size": 90,
    "auto_zip": True,
    "open_output": True,
    "save_logs": True,
    "sound_enabled": True,
    "auto_update_check": True,
    "last_output_dir": ""
}

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)

    def load(self):
        if not self.config_path.exists():
            self.save(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            settings = dict(DEFAULT_SETTINGS)
            settings.update(data)
            return settings
        except Exception:
            return dict(DEFAULT_SETTINGS)

    def save(self, settings):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
