@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%answer.py" (
  py -3 "%SCRIPT_DIR%answer.py" %*
) else (
  echo answer.py not found next to answer.cmd
  exit /b 1
)
