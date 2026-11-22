@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if /i "%~1"=="--console" goto console
if /i "%~1"=="--check" goto console
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py" %*
    exit /b 0
)
:console
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
) else (
    python "%~dp0main.py" %*
)
set "JARVIS_EXIT_CODE=%errorlevel%"
if not "%JARVIS_EXIT_CODE%"=="0" (
    echo.
    echo اجرای جارویس ناموفق بود. پیام خطای بالا را بررسی کنید.
    pause
)
endlocal & exit /b %JARVIS_EXIT_CODE%
