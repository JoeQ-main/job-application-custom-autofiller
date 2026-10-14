@echo off
REM ==========================================================================
REM  Run Job App Manager.cmd
REM  Double-click this file to open Job App Manager.
REM  (A .cmd file is used instead of a PowerShell script, so Windows'
REM   PowerShell "execution policy" can never block it.)
REM
REM  It looks for a Python that includes Tkinter (the window library), in
REM  this order: the "py" launcher, "python" on PATH, then common Anaconda /
REM  Miniconda install folders.
REM  Keep this black window open while you use the program; closing the
REM  program window closes it too.
REM ==========================================================================
cd /d "%~dp0"
set PY=

py -3 -c "import tkinter" >nul 2>nul && set PY=py -3
if not defined PY (python -c "import tkinter" >nul 2>nul && set PY=python)
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set PY="%USERPROFILE%\miniconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\anaconda3\python.exe" set PY="%LOCALAPPDATA%\anaconda3\python.exe"
if not defined PY if exist "%ProgramData%\anaconda3\python.exe" set PY="%ProgramData%\anaconda3\python.exe"

if not defined PY (
    echo.
    echo ERROR in "Run Job App Manager.cmd": no usable Python was found.
    echo   Tried: "py -3", "python", and the Anaconda/Miniconda folders in
    echo   %USERPROFILE%, %LOCALAPPDATA% and %ProgramData%.
    echo   Fix: install Python from https://www.python.org/downloads/windows/
    echo        and tick "Add python.exe to PATH" during setup, then run this again.
    echo.
    pause
    exit /b 1
)

echo Starting Job App Manager with %PY% ...
%PY% job_app_manager.py
if errorlevel 1 (
    echo.
    echo ERROR: Job App Manager stopped with an error. The details are printed above.
    echo   Python used: %PY%
    echo   Folder:      %~dp0
    echo.
    pause
)
