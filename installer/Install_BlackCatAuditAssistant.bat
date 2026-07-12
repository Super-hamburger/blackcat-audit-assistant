@echo off
chcp 65001 >nul
setlocal

set "SOURCE=%~dp0BlackCatAuditAssistant"
set "TARGET=%LOCALAPPDATA%\BlackCatAuditAssistant"
set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%SOURCE%\BlackCatAuditAssistant.exe" (
  echo 找不到安装源：%SOURCE%\BlackCatAuditAssistant.exe
  pause
  exit /b 1
)

if not exist "%TARGET%" mkdir "%TARGET%"
robocopy "%SOURCE%" "%TARGET%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo 安装失败，请检查文件权限。
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut('%DESKTOP%\黑猫审单助手.lnk'); $shortcut.TargetPath='%TARGET%\BlackCatAuditAssistant.exe'; $shortcut.WorkingDirectory='%TARGET%'; $shortcut.Save()"

echo 安装完成。
echo 桌面快捷方式：黑猫审单助手
echo 安装目录：%TARGET%
pause
