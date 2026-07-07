@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ==========================================================
REM BTS PCTT - ONE CLICK RUNNER - PORTABLE VERSION
REM - Tu tao lai .venv neu bi copy tu may khac / hong duong dan Python
REM - Tu cai/cap nhat thu vien neu thieu
REM - Mo app desktop bang pythonw.exe de an cua so console khi app chay
REM ==========================================================

set "APP_FILE=%~dp0desktop_app.py"
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "VENV_PYW=%~dp0.venv\Scripts\pythonw.exe"
set "REQ_FILE=%~dp0requirements.txt"
set "FAST_MODE=1"

if not exist "%APP_FILE%" (
    echo Khong tim thay desktop_app.py trong thu muc hien tai.
    echo Hay giai nen day du bo tool roi chay lai.
    pause
    exit /b 1
)

REM Tim Python tren may hien tai
set "SYS_PY="
where python >nul 2>nul
if not errorlevel 1 set "SYS_PY=python"
if "%SYS_PY%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 set "SYS_PY=py -3"
)
if "%SYS_PY%"=="" (
    echo Khong tim thay Python tren may.
    echo Vui long cai Python 3.10+ va tick Add Python to PATH, sau do chay lai file nay.
    pause
    exit /b 1
)

REM Neu .venv da co nhung bi copy tu may khac, python.exe se tro vao duong dan cu va bi loi.
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; print(sys.executable)" >nul 2>nul
    if errorlevel 1 (
        echo Phat hien .venv bi hong hoac copy tu may khac. Dang tao lai .venv...
        rmdir /s /q "%VENV_DIR%" >nul 2>nul
    )
)

if not exist "%VENV_PY%" (
    echo Lan dau chay tool - dang tao moi truong ao .venv...
    %SYS_PY% -m venv .venv
    if errorlevel 1 (
        echo Tao .venv that bai. Hay chay bang quyen Administrator hoac kiem tra Python.
        pause
        exit /b 1
    )
)

REM Kiem tra goi bat buoc bang Python trong .venv, khong dung activate de tranh loi launcher.
"%VENV_PY%" -c "import pandas, openpyxl, docx, pypdf, xlsxwriter, dotenv, tabulate, rapidfuzz" >nul 2>nul
if errorlevel 1 (
    echo Dang cai/cap nhat thu vien can thiet, vui long doi...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r "%REQ_FILE%"
    if errorlevel 1 (
        echo Cai thu vien that bai. Hay kiem tra mang hoac chay run_desktop_debug.bat de xem loi chi tiet.
        pause
        exit /b 1
    )
)

if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" "%APP_FILE%"
) else (
    start "" /min "%VENV_PY%" "%APP_FILE%"
)

exit /b 0
