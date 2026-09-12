@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m brainfc serve --workspace ".work\app"
) else (
  python -m brainfc serve
)
pause
