from pathlib import Path
import sys
import winsound


class SoundEngine:
    """
    Backward-compatible sound engine.

    Older UI code calls:
    - play_click(path)
    - play_complete(path)
    - play_error(path)

    Newer code may call:
    - preload(name)
    - play(name)

    This engine supports both APIs so business buttons never fail because of sound.
    """

    def __init__(self, sound_dir=None, enabled=True):
        self.enabled = bool(enabled)
        self.sound_dir = Path(sound_dir) if sound_dir else self.default_sound_dir()
        self.cache = {}

    def default_sound_dir(self):
        root = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[1]
        return root / "assets" / "sounds"

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def preload(self, name_or_path):
        path = Path(name_or_path)
        if not path.is_absolute():
            path = self.sound_dir / str(name_or_path)
        if path.exists():
            self.cache[str(name_or_path)] = str(path)
            self.cache[path.name] = str(path)
            return str(path)
        return None

    def _play_path(self, path):
        if not self.enabled:
            return
        try:
            path = Path(path)
            if path.exists():
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def play(self, name_or_path):
        path = Path(name_or_path)
        if not path.is_absolute():
            cached = self.cache.get(str(name_or_path)) or self.cache.get(path.name)
            path = Path(cached) if cached else self.sound_dir / str(name_or_path)
        self._play_path(path)

    def play_click(self, path=None):
        self.play(path or "ui_click.wav")

    def play_complete(self, path=None):
        self.play(path or "water_complete.wav")

    def play_done(self, path=None):
        self.play_complete(path)

    def play_error(self, path=None):
        self.play(path or "soft_error.wav")

    def play_import(self, path=None):
        self.play(path or "file_import.wav")

    def warm_up(self):
        # Cache common sounds without making user-visible system beep.
        for name in ["ui_click.wav", "scan_success.wav", "water_complete.wav", "water_drop.wav", "file_import.wav", "soft_error.wav"]:
            self.preload(name)
