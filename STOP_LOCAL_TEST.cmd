@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0STOP_LOCAL_TEST.ps1" %*
