@echo off

setlocal

if exist app\launcher.py (echo INSTALLATION_OK & exit /b 0) else (echo INSTALLATION_MISSING & exit /b 1)
