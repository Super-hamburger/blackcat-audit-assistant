@echo off
chcp 65001 >nul
cd /d %~dp0
set PYTHON_EXE=D:\Python\python.exe
"%PYTHON_EXE%" -m PyInstaller --onefile --windowed --name BlackCatAuditAssistant app.py
pause
