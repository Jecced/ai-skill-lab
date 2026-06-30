@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "PS_SCRIPT=%REPO_ROOT%scripts\install-skills.ps1"

if not exist "%PS_SCRIPT%" (
  echo Missing install script: "%PS_SCRIPT%"
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -NoPause %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo Install finished.
) else (
  echo Install failed with exit code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
