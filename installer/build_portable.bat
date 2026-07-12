@echo off
chcp 65001 >nul
cd /d %~dp0\..
set PYTHON_EXE=D:\Python\python.exe
if not exist "%PYTHON_EXE%" (
  echo 找不到 Python：%PYTHON_EXE%
  pause
  exit /b 1
)
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --windowed --onedir --name BlackCatAuditAssistant app.py
echo.
echo 便携版输出位置：dist\BlackCatAuditAssistant
pause
