@echo off
setlocal
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap-windows-launcher.ps1" -RepoRoot "%~dp0" %*
