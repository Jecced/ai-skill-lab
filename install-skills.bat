@echo off
setlocal

set "CMD_SCRIPT=%~dp0install-skills.cmd"

if not exist "%CMD_SCRIPT%" (
  echo Missing install script: "%CMD_SCRIPT%"
  pause
  exit /b 1
)

call "%CMD_SCRIPT%" %*
exit /b %ERRORLEVEL%
