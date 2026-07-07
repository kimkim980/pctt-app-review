@echo off
cd /d %~dp0

if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install --upgrade pyinstaller pyinstaller-hooks-contrib

REM Xoa ban build cu de tranh thieu module do cache
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist BTS_PCTT_ThamDinh.spec del /q BTS_PCTT_ThamDinh.spec

pyinstaller ^
  --noconsole ^
  --onefile ^
  --clean ^
  --name BTS_PCTT_ThamDinh ^
  --add-data "rules;rules" ^
  --add-data "src;src" ^
  --collect-all pandas ^
  --collect-all openpyxl ^
  --collect-all xlsxwriter ^
  --collect-all tabulate ^
  --collect-all docx ^
  --collect-all pypdf ^
  --collect-all dotenv ^
  --hidden-import pandas ^
  --hidden-import openpyxl ^
  --hidden-import xlsxwriter ^
  --hidden-import tabulate ^
  --hidden-import docx ^
  --hidden-import pypdf ^
  --hidden-import dotenv ^
  desktop_app.py

echo.
echo File EXE nam trong thu muc dist\BTS_PCTT_ThamDinh.exe
echo Neu Windows Defender canh bao, chon More info ^> Run anyway vi day la exe build local.
pause
