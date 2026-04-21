@echo off
setlocal

cd /d "%~dp0"

set "ENV_NAME=microct_gui"
set "CONDA_BAT="

if exist "%USERPROFILE%\miniforge3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniforge3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\AppData\Local\miniforge3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\AppData\Local\miniforge3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\mambaforge\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\mambaforge\condabin\conda.bat"
if not defined CONDA_BAT if exist "%ProgramData%\miniforge3\condabin\conda.bat" set "CONDA_BAT=%ProgramData%\miniforge3\condabin\conda.bat"

if not defined CONDA_BAT (
    for /f "delims=" %%i in ('where conda 2^>nul') do (
        if exist "%%i" (
            set "CONDA_BAT=%%i"
            goto :found_conda
        )
    )
)

:found_conda
if not defined CONDA_BAT (
    echo Could not find conda.bat.
    echo Please open Miniforge Prompt and run:
    echo where conda
    pause
    exit /b 1
)

call "%CONDA_BAT%" activate %ENV_NAME%
if errorlevel 1 (
    echo.
    echo Could not activate environment "%ENV_NAME%".
    echo Please run install_ring_removal_env.bat first.
    pause
    exit /b 1
)

python run_gui.py
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo GUI exited with code %EXITCODE%.
    pause
)

exit /b %EXITCODE%
