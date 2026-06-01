@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0CREATE_REVIEW_ZIP.ps1" %*
