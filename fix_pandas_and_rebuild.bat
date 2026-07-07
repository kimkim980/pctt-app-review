@echo off
cd /d %~dp0
call .venv\Scripts\activate 2>nul
if errorlevel 1 (
  python -m venv .venv
  call .venv\Scripts\activate
)
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install --upgrade pandas openpyxl xlsxwriter tabulate pyinstaller pyinstaller-hooks-contrib
pip install --upgrade pandas openpyxl xlsxwriter python-docx pypdf python-dotenv pyinstaller pyinstaller-hooks-contrib
call build_exe.bat
