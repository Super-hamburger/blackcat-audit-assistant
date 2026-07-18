import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path


class UpdateInstaller:
    def __init__(self, app_name="BlackCatAuditAssistant", timeout=30):
        self.app_name = app_name
        self.timeout = int(timeout)

    def prepare_update(self, update_info, progress_callback=None):
        download_url = str(update_info.get("download_url", "")).strip()
        expected_sha256 = str(update_info.get("package_sha256", "")).strip().lower()
        latest_version = str(update_info.get("latest_version", "")).strip() or "unknown"

        if not getattr(sys, "frozen", False):
            return self.failure("一键更新只能在打包后的软件中使用。源码运行时不会覆盖项目文件。")
        if not download_url:
            return self.failure("更新清单缺少 download_url，不能一键更新。")
        if not expected_sha256:
            return self.failure("更新清单缺少 package_sha256，不能安全执行一键更新。")

        install_dir = Path(sys.executable).resolve().parent
        current_exe = install_dir / f"{self.app_name}.exe"
        if not current_exe.exists():
            return self.failure(f"找不到当前程序：{current_exe}")

        work_dir = Path(tempfile.gettempdir()) / f"{self.app_name}_updates" / f"{latest_version}_{int(time.time())}"
        package_path = work_dir / f"{self.app_name}_update.zip"
        extract_dir = work_dir / "extracted"
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.download_file(download_url, package_path, progress_callback)
            self.emit_progress(progress_callback, "verifying", "正在校验安装包...")
            actual_sha256 = self.file_sha256(package_path)
            if actual_sha256.lower() != expected_sha256:
                return self.failure(
                    "安装包 SHA256 校验失败，已停止更新。\n"
                    f"期望：{expected_sha256}\n实际：{actual_sha256}"
                )

            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            self.emit_progress(progress_callback, "extracting", "正在解压更新包...")
            with zipfile.ZipFile(package_path, "r") as archive:
                archive.extractall(extract_dir)

            source_dir = self.find_update_app_dir(extract_dir)
            if not source_dir:
                return self.failure("安装包结构不正确，未找到 BlackCatAuditAssistant.exe。")

            self.emit_progress(progress_callback, "preparing", "正在准备安装更新...")
            script_path = self.write_update_script(work_dir, source_dir, install_dir, current_exe, os.getpid())
            return {
                "ok": True,
                "message": "更新包已下载并校验完成，准备退出并安装新版。",
                "script_path": str(script_path),
                "package_path": str(package_path),
                "source_dir": str(source_dir),
                "sha256": actual_sha256,
            }
        except Exception as error:
            return self.failure(f"准备更新失败：{error}")

    @staticmethod
    def emit_progress(progress_callback, stage, message, downloaded_bytes=None, total_bytes=None):
        if progress_callback is not None:
            progress_callback({
                "stage": stage,
                "message": message,
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": total_bytes,
            })

    def download_file(self, url, target, progress_callback=None):
        request = urllib.request.Request(url, headers={"User-Agent": "BlackCatAuditAssistant-Updater"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            content_length = response.headers.get("Content-Length")
            total_bytes = int(content_length) if content_length and content_length.isdigit() else None
            downloaded_bytes = 0
            with Path(target).open("wb") as file:
                while chunk := response.read(1024 * 1024):
                    file.write(chunk)
                    downloaded_bytes += len(chunk)
                    self.emit_progress(
                        progress_callback,
                        "downloading",
                        "正在下载更新包...",
                        downloaded_bytes,
                        total_bytes,
                    )

    def file_sha256(self, path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def find_update_app_dir(self, extract_dir):
        direct = Path(extract_dir) / self.app_name
        direct_exe = direct / f"{self.app_name}.exe"
        if direct_exe.exists():
            return direct
        for candidate in Path(extract_dir).rglob(f"{self.app_name}.exe"):
            if candidate.parent.name == self.app_name:
                return candidate.parent
        return None

    def write_update_script(self, work_dir, source_dir, install_dir, current_exe, pid):
        script_path = Path(work_dir) / "apply_update.bat"
        script = f"""@echo off
chcp 65001 >nul
setlocal
set "SOURCE={source_dir}"
set "TARGET={install_dir}"
set "EXE={current_exe}"

if not exist "%SOURCE%\\{self.app_name}.exe" exit /b 1
if not exist "%TARGET%\\{self.app_name}.exe" exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command "Wait-Process -Id {int(pid)} -ErrorAction SilentlyContinue -Timeout 45"
timeout /t 2 /nobreak >nul
robocopy "%SOURCE%" "%TARGET%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
start "" "%EXE%"
exit /b 0
"""
        script_path.write_text(script, encoding="utf-8")
        return script_path

    def launch_update_script(self, script_path):
        subprocess.Popen(["cmd", "/c", "start", "", str(script_path)], shell=False)

    @staticmethod
    def failure(message):
        return {"ok": False, "message": str(message)}
