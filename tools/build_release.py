from pathlib import Path
import shutil
import zipfile
import json
import time

ROOT = Path(__file__).resolve().parents[1]
version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
release_name = version.get("build", "release") + "_" + time.strftime("%Y%m%d_%H%M%S")
release_dir = ROOT / "release" / release_name
release_dir.mkdir(parents=True, exist_ok=True)

zip_path = release_dir / f"{release_name}.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for item in ROOT.rglob("*"):
        if "release" in item.parts or ".git" in item.parts:
            continue
        if item.is_file():
            z.write(item, item.relative_to(ROOT))
print(zip_path)
