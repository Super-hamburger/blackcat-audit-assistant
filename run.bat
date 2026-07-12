@echo off
chcp 65001 >nul
cd /d %~dp0
set PYTHON_EXE=D:\Python\python.exe
if exist "%PYTHON_EXE%" goto run
set PYTHON_EXE=python
:run
"%PYTHON_EXE%" app.py
pause
