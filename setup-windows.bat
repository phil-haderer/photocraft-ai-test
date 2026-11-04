@echo off
setlocal
cd /d "%~dp0"
set "HERE=%~dp0"
set "CHECK="
set "NOMENU="
:args
if "%~1"=="" goto :argsdone
if /i "%~1"=="/check" (set "CHECK=1") else if /i "%~1"=="/nomenu" (set "NOMENU=1") else if "%~1"=="/?" (goto :usage) else (echo Unknown option: %~1& goto :usage)
shift
goto :args
:usage
echo Usage: setup-windows.bat [/check] [/nomenu] [/?]
echo   /check   only look: shows the steps and what each would do, changes nothing
echo   /nomenu  skips the desktop shortcut "PhotoCraft AI" (step 4)
exit /b 1
:argsdone
echo Setup of the bridge: 1 Python, 2 virtual environment, 3 packages, 4 desktop shortcut.
if defined CHECK echo (/check: nothing is changed, the steps only say what they would do.)

echo.
echo [1/4] Python 3.11 or newer with tkinter
set "PYEXE="
for %%P in (py python "%USERPROFILE%\miniconda3\python.exe") do call :try "%%~P"
if not defined PYEXE goto :nopython
echo Using Python: %PYEXE%

echo.
echo [2/4] Virtual environment %HERE%.venv
set "PYRUN=%HERE%.venv\Scripts\python.exe"
set "PIPARGS="
if exist "%PYRUN%" (
    echo It exists already.
) else if defined CHECK (
    echo Would create it with %PYEXE%.
) else (
    "%PYEXE%" -m venv "%HERE%.venv"
    echo Created.
)
if not exist "%PYRUN%" goto :step3
"%PYRUN%" -c "import tkinter; r = tkinter.Tk(); r.destroy()" >nul 2>&1
if not errorlevel 1 goto :step3
echo The virtual environment cannot open a Tk window, so %PYEXE% is used directly.
set "PYRUN=%PYEXE%"
set "PIPARGS=--user"

:step3
echo.
echo [3/4] Packages: pillow numpy websocket-client tkinterdnd2
if defined CHECK (
    echo Would install them with pip.
    goto :step4
)
if not exist data mkdir data
"%PYRUN%" -m pip install %PIPARGS% pillow numpy websocket-client tkinterdnd2
if errorlevel 1 goto :pipfail
(echo %PYRUN%)>"%HERE%data\python.txt"

:step4
echo.
echo [4/4] Desktop shortcut "PhotoCraft AI"
if defined NOMENU (
    echo Skipped by /nomenu.
    goto :finish
)
if defined CHECK (
    echo Would create the shortcut.
    goto :finish
)
"%PYRUN%" -m pccomfy shortcut

:finish
echo.
if defined CHECK (
    echo Check done, nothing was changed.
    exit /b 0
)
echo One ComfyUI custom node pack is needed: ComfyUI-KJNodes (Flux 3 Upscale uses its Color Match node).
echo Install it from the ComfyUI Manager or from https://github.com/kijai/ComfyUI-KJNodes . If you have it already, do nothing.
echo.
if defined NOMENU (
    echo Setup done. Start PhotoCraft with the shortcut made by "python -m pccomfy shortcut".
) else (
    echo Setup done. Start PhotoCraft with the desktop shortcut "PhotoCraft AI".
)
pause
exit /b 0

:try
if defined PYEXE exit /b 0
"%~1" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYEXE=%~1"
exit /b 0

:nopython
echo Python 3.11 or newer with tkinter was not found.
echo Install it from python.org (tick "tcl/tk") or use miniconda, then run this again.
pause
exit /b 1

:pipfail
echo pip install failed. Check the messages above.
pause
exit /b 1
