@echo off
setlocal DisableDelayedExpansion
if exist "%~dp0..\host\python.exe" (
  "%~dp0..\host\python.exe" -I -B "%~dp0scripts\start_windows_terminal.py" %*
  exit /b
)
if exist "%~dp0artifacts\windows-evaluation\venv\Scripts\python.exe" (
  "%~dp0artifacts\windows-evaluation\venv\Scripts\python.exe" -I -B "%~dp0scripts\start_windows_terminal.py" %*
  exit /b
)
echo Prepare this reviewed source with the evaluation installer first.
echo See docs\SILO-PHASE-2.md. No system Python or uncontained fallback is selected.
exit /b 1
