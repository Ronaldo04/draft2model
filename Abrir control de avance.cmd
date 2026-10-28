@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" seguimiento\control.py --watch-only
) else (
  python seguimiento\control.py --watch-only
)
if errorlevel 1 pause
