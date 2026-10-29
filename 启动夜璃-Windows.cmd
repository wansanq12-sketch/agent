@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.12 tools\windows_setup.py
  if errorlevel 1 pause
  exit /b
)
py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.11 tools\windows_setup.py
  if errorlevel 1 pause
  exit /b
)
echo Please install Python 3.11 or 3.12 (64-bit) with Python Launcher from https://www.python.org/downloads/windows/
pause
