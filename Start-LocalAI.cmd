@echo off
setlocal DisableDelayedExpansion
if exist "%LOCALAPPDATA%\LocalAI-Evaluation\Start-LocalAI.cmd" (
  call "%LOCALAPPDATA%\LocalAI-Evaluation\Start-LocalAI.cmd"
  exit /b
)
if not exist "%~dp0artifacts\windows-evaluation\venv\Scripts\pythonw.exe" (
  echo Run this once in PowerShell from the project folder:
  echo .\installer\Install-Evaluation.ps1
  pause
  exit /b 1
)
start "" "%~dp0artifacts\windows-evaluation\venv\Scripts\pythonw.exe" -I -B "%~dp0scripts\start_windows_ui.py"
