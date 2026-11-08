@echo off
setlocal
cd /d "%~dp0"
if not exist "data\python.txt" (echo Run setup-windows.bat first.& pause & exit /b 1)
rem data\python.txt is UTF-8 (setup-windows.bat): read it with code page 65001, or a folder name with umlauts breaks
chcp 65001 >nul
set /p PY=<"data\python.txt"
echo ---- check ----
"%PY%" -m pccomfy check
echo.
echo ---- probe ----
"%PY%" -m pccomfy probe
echo.
pause
