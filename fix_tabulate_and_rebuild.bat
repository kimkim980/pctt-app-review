@echo off
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install --upgrade tabulate pandas openpyxl xlsxwriter pyinstaller pyinstaller-hooks-contrib
call build_exe.bat
