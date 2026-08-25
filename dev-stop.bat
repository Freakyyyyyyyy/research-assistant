@echo off
REM One-command shutdown for the Windows development environment.

setlocal
set "PROJECT_ROOT=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%dev-stop.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Shutdown failed. Review the message above.
  pause
)

endlocal & exit /b %EXIT_CODE%
