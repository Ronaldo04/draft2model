@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" seguimiento\control.py
) else (
  python seguimiento\control.py
)
if errorlevel 1 pause
