@echo off
chcp 65001 >nul
cd /d %~dp0
set PYTHON_EXE=D:\Python\python.exe
if exist "%PYTHON_EXE%" goto install
set PYTHON_EXE=python
:install
"%PYTHON_EXE%" -m pip install -r requirements.txt
pause
