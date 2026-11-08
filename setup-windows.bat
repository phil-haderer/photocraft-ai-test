@echo off
setlocal
cd /d "%~dp0"
set "HERE=%~dp0"
set "CHECK="
set "NOMENU="
set "NOPAUSE="
:args
if "%~1"=="" goto :argsdone
if /i "%~1"=="/check" (set "CHECK=1") else if /i "%~1"=="/nomenu" (set "NOMENU=1") else if /i "%~1"=="/nopause" (set "NOPAUSE=1") else if "%~1"=="/?" (goto :usage) else (echo Unknown option: %~1& goto :usage)
shift
goto :args
:usage
echo Usage: setup-windows.bat [/check] [/nomenu] [/nopause] [/?]
echo   /check   only look: shows the steps and what each would do, changes nothing
echo   /nomenu  skips the desktop shortcut "PhotoCraft AI" (step 4)
echo   /nopause does not wait for a key at the end (for scripts and the automatic install check)
echo Environment: PYTHON = the Python to use (tried first)
exit /b 1
:argsdone
echo Setup of the bridge: 1 Python, 2 virtual environment, 3 packages, 4 desktop shortcut.
if defined CHECK echo (/check: nothing is changed, the steps only say what they would do.)

echo.
echo [1/4] Python 3.11 or newer with tkinter
set "PYEXE="
rem Tested with Python 3.13 and 3.14 (3.14 brings Tk 9). PYTHON (if set) first, then the versions we know: 3.13, 3.12, 3.11, then 3.14; then any other.
if defined PYTHON call :try "%PYTHON%"
for %%V in (-3.13 -3.12 -3.11 -3.14) do call :tryv %%V
for %%P in (py python "%USERPROFILE%\miniconda3\python.exe") do call :try "%%~P"
if not defined PYEXE goto :nopython
:pyfound
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
rem Python writes the file, always as UTF-8 (an echo would use the console code page, 850 on German Windows, and break folder names with umlauts)
"%PYRUN%" -c "import sys, pathlib; pathlib.Path(sys.argv[1]).write_text(sys.executable, encoding='utf-8')" "%HERE%data\python.txt"
if errorlevel 1 goto :pipfail

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
call :waitkey
exit /b 0

:waitkey
if not defined NOPAUSE pause
exit /b 0

:tryv
if defined PYEXE exit /b 0
set "CAND="
for /f "usebackq delims=" %%I in (`py %~1 -c "import tkinter, sys; print(sys.executable)" 2^>nul`) do set "CAND=%%I"
if defined CAND set "PYEXE=%CAND%"
exit /b 0

:try
if defined PYEXE exit /b 0
"%~1" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYEXE=%~1"
exit /b 0

:nopython
echo Python 3.11 or newer with tkinter was not found.
if defined CHECK (
    echo Would offer to install Python 3.13 from python.org with winget, for this Windows user only.
    goto :finish
)
rem The offer (user 8.11.): winget installs the official python.org Python 3.13 for this user only (no admin rights,
rem tkinter included), after a Y. Without winget, after N, or unattended (/nopause): the download page and three steps.
if defined NOPAUSE goto :pymanual
where winget >nul 2>&1
if errorlevel 1 goto :pymanual
echo.
echo Setup can install it now: the official Python 3.13 from python.org, for this Windows user only
echo (no admin rights needed), with winget. Answering Y accepts the Python license:
echo https://docs.python.org/3/license.html
choice /c YN /m "Install Python 3.13 now"
if errorlevel 2 goto :pymanual
winget install --exact --id Python.Python.3.13 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
rem winget's exit code is not reliable here (it is non-zero when Python is there already): look for the new Python itself.
rem It is not in this window's PATH yet, so try the folder the per-user installer uses.
call :try "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :tryv -3.13
if defined PYEXE goto :pyfound
echo Python was not found after the installation.
goto :pymanual

:pymanual
echo.
echo Install Python yourself, it takes two minutes:
echo   1. On the page that opens, download "Windows installer (64-bit)" of Python 3.13.
echo   2. Run it and keep the default options (tcl/tk stays ticked).
echo   3. Then double-click setup-windows.bat again.
echo Page: https://www.python.org/downloads/windows/
if not defined NOPAUSE start "" "https://www.python.org/downloads/windows/"
call :waitkey
exit /b 1

:pipfail
echo pip install failed. Check the messages above.
call :waitkey
exit /b 1
