import json
from pathlib import Path


class I18nManager:
    def __init__(self, locales_dir, default_language="zh_CN"):
        self.locales_dir = Path(locales_dir)
        self.default_language = default_language
        self.language = default_language
        self.messages = {}
        self.load(default_language)

    def available_languages(self):
        result = []
        for path in sorted(self.locales_dir.glob("*.json")):
            result.append(path.stem)
        return result

    def load(self, language):
        path = self.locales_dir / f"{language}.json"
        if not path.exists():
            path = self.locales_dir / f"{self.default_language}.json"
        try:
            self.messages = json.loads(path.read_text(encoding="utf-8"))
            self.language = path.stem
        except Exception:
            self.messages = {}
            self.language = self.default_language
        return self.messages

    def t(self, key, default=None):
        return self.messages.get(key, default if default is not None else key)
