@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\afterstory.ps1" %*
exit /b %errorlevel%
