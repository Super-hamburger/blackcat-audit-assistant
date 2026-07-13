# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project = Path.cwd()
icon_path = project / "assets" / "icons" / "blackcat_app.ico"
datas = []
for folder in ["assets", "data", "locales", "modules", "plugins", "updater"]:
    path = project / folder
    if not path.exists():
        continue
    for file in path.rglob("*"):
        if file.is_file():
            datas.append((str(file), str(file.parent.relative_to(project))))

version_path = project / "version.json"
if version_path.exists():
    datas.append((str(version_path), "."))

for package in ["fitz", "pymupdf", "openpyxl"]:
    datas += collect_data_files(package)

binaries = []
for package in ["fitz", "pymupdf"]:
    binaries += collect_dynamic_libs(package)

hiddenimports = []
for package in ["core", "modules", "fitz", "pymupdf", "openpyxl"]:
    hiddenimports += collect_submodules(package)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BlackCatAuditAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BlackCatAuditAssistant",
)
