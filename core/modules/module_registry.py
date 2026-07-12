import importlib.util
import json
from core.modules.module_contract import ModuleMeta, ModuleResult
from core.utils.path_manager import PathManager


class ModuleRegistry:
    def __init__(self, modules_dir=None):
        self.modules_dir = modules_dir or (PathManager.project_root() / "modules")
        self.modules = []

    def discover(self):
        self.modules = []
        if not self.modules_dir.exists():
            return self.modules
        for module_dir in sorted(self.modules_dir.iterdir()):
            manifest = module_dir / "module.json"
            entry = module_dir / "module.py"
            if not module_dir.is_dir() or not manifest.exists() or not entry.exists():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if not data.get("enabled", True):
                continue
            self.modules.append(ModuleMeta(data.get("id", module_dir.name), data.get("name_key", data.get("id", module_dir.name)), data.get("description_key", ""), data.get("version", "0.0.0"), bool(data.get("enabled", True)), data.get("category", "general"), module_dir, entry))
        return self.modules

    def load_runner(self, meta):
        spec = importlib.util.spec_from_file_location(f"blackcat_module_{meta.module_id}", meta.entry)
        if not spec or not spec.loader:
            raise RuntimeError(f"Cannot load module: {meta.module_id}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "run"):
            raise RuntimeError(f"Module has no run function: {meta.module_id}")
        return module.run

    def run(self, module_id, context=None):
        if not self.modules:
            self.discover()
        for meta in self.modules:
            if meta.module_id == module_id:
                result = self.load_runner(meta)(context or {})
                if isinstance(result, ModuleResult):
                    return result
                if isinstance(result, dict):
                    return ModuleResult(ok=bool(result.get("ok", True)), message=str(result.get("message", "")), data=result)
                return ModuleResult(ok=True, message=str(result), data=None)
        return ModuleResult(ok=False, message=f"Module not found: {module_id}", data=None)
