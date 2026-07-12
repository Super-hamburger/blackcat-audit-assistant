from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModuleMeta:
    module_id: str
    name_key: str
    description_key: str
    version: str
    enabled: bool
    category: str
    path: Path
    entry: Path


@dataclass
class ModuleResult:
    ok: bool
    message: str
    data: dict | None = None
