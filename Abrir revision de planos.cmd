@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m draft2model.revision_visual
if errorlevel 1 pause
