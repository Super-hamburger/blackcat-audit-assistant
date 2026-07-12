@echo off
chcp 65001 >nul
cd /d %~dp0
set PYTHON_EXE=D:\Python\python.exe
if exist "%PYTHON_EXE%" goto build
set PYTHON_EXE=python
:build
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean BlackCatAuditAssistant.spec
echo.
echo V4.0.0便携版输出位置：dist\BlackCatAuditAssistant
echo 发送给朋友时，请压缩整个 dist\BlackCatAuditAssistant 文件夹。
pause
