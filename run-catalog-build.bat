@echo off
REM Rebuild catalog outputs from the latest FileMaker export
cd /d "%~dp0"
catalog-builder.exe %*
if errorlevel 1 pause
start "" "%~dp0..\output\report.html"
