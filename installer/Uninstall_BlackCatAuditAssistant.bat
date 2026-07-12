@echo off
chcp 65001 >nul
setlocal

set "TARGET=%LOCALAPPDATA%\BlackCatAuditAssistant"
set "SHORTCUT=%USERPROFILE%\Desktop\黑猫审单助手.lnk"

if exist "%SHORTCUT%" del "%SHORTCUT%"
if exist "%TARGET%" rmdir /s /q "%TARGET%"

echo 卸载完成。
pause
