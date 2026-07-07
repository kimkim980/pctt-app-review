@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_FILE=%~dp0desktop_app.py"
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "REQ_FILE=%~dp0requirements.txt"

set "SYS_PY="
where python >nul 2>nul
if not errorlevel 1 set "SYS_PY=python"
if "%SYS_PY%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 set "SYS_PY=py -3"
)
if "%SYS_PY%"=="" (
    echo Khong tim thay Python. Cai Python 3.10+ va tick Add Python to PATH.
    pause
    exit /b 1
)

if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; print(sys.executable)"
    if errorlevel 1 (
        echo .venv hong/copy tu may khac. Dang xoa va tao lai...
        rmdir /s /q "%VENV_DIR%"
    )
)

if not exist "%VENV_PY%" (
    %SYS_PY% -m venv .venv
)

"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r "%REQ_FILE%"
"%VENV_PY%" "%APP_FILE%"
pause
