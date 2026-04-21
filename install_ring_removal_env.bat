@echo off
setlocal

cd /d "%~dp0"

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

echo Using:
echo %CONDA_BAT%

call "%CONDA_BAT%" env update -f environment.yml --prune
if errorlevel 1 (
    echo.
    echo Environment creation/update failed.
    pause
    exit /b 1
)

echo.
echo Environment is ready.
pause
exit /b 0
