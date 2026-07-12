import importlib.util
import json
from pathlib import Path


class PluginManager:
    def __init__(self, plugins_dir):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins = []

    def discover(self):
        self.plugins = []
        for manifest_path in sorted(self.plugins_dir.glob("*/plugin.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugin_dir = manifest_path.parent
                entry = manifest.get("entry", "plugin.py")
                entry_path = plugin_dir / entry
                if not entry_path.exists():
                    manifest["status"] = "missing_entry"
                else:
                    manifest["status"] = "ready"
                manifest["_dir"] = str(plugin_dir)
                manifest["_entry_path"] = str(entry_path)
                self.plugins.append(manifest)
            except Exception as error:
                self.plugins.append({
                    "name": manifest_path.parent.name,
                    "status": "error",
                    "error": str(error),
                })
        return self.plugins

    def load_plugin(self, manifest):
        entry_path = Path(manifest["_entry_path"])
        module_name = "blackcat_plugin_" + manifest.get("id", entry_path.parent.name)
        spec = importlib.util.spec_from_file_location(module_name, entry_path)
        if not spec or not spec.loader:
            raise RuntimeError("Cannot load plugin spec.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def get_plugins(self):
        if not self.plugins:
            return self.discover()
        return self.plugins
