@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title GoHumanize - Adaptive All-in-One Launcher

echo ==========================================================
echo    GoHumanize HR Assistant - Starting All Services...
echo ==========================================================
echo.

:: 1. Multi-strategy Python discovery
set "PYTHON_EXE="

where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_EXE=python"
    goto :FoundPython
)

where py >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_EXE=py -3"
    goto :FoundPython
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :FoundPython
)
if exist "%~dp0backend\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0backend\.venv\Scripts\python.exe"
    goto :FoundPython
)
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
    goto :FoundPython
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :FoundPython
    )
)

for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :FoundPython
    )
)

:FoundPython
if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python was not found on your system.
    echo Please install Python 3.9+ from https://www.python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Dynamic discovery of start.py
set "START_PY="
if exist "%~dp0start.py" set "START_PY=%~dp0start.py"
if "%START_PY%"=="" if exist "%~dp0..\start.py" set "START_PY=%~dp0..\start.py"

if "%START_PY%"=="" (
    for /r "%~dp0" %%F in (start.py) do (
        if exist "%%F" (
            set "START_PY=%%F"
            goto :RunScript
        )
    )
)

:RunScript
if "%START_PY%"=="" (
    echo [ERROR] Could not find start.py script.
    pause
    exit /b 1
)

%PYTHON_EXE% "%START_PY%" %*

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [INFO] Process exited with code !ERRORLEVEL!.
    pause
)
