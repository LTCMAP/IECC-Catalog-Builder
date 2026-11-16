@echo off
REM Nightly catalog build (run by Windows Task Scheduler). No pauses, no windows; writes a dated log.
cd /d "%~dp0"
if not exist logs mkdir logs
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d
echo ==== %DATE% %TIME% ==== >> "logs\build-%TODAY%.log"
catalog-builder.exe --only-if-changed >> "logs\build-%TODAY%.log" 2>&1
set RC=%ERRORLEVEL%
echo exit code %RC% >> "logs\build-%TODAY%.log"
REM keep 60 days of logs
forfiles /p logs /m build-*.log /d -60 /c "cmd /c del @path" >nul 2>&1
exit /b %RC%
