from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
for name in ["build", "dist", "__pycache__"]:
    for path in ROOT.rglob(name):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
print("Clean completed.")
