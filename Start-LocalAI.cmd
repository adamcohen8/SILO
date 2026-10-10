@echo off
setlocal
if not exist "%~dp0artifacts\windows-evaluation\venv\Scripts\pythonw.exe" (
  echo The prepared local Python environment is missing.
  pause
  exit /b 1
)
start "" "%~dp0artifacts\windows-evaluation\venv\Scripts\pythonw.exe" -I -B "%~dp0scripts\start_windows_ui.py"
