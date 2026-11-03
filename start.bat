@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Откройте http://127.0.0.1:5000
.venv\Scripts\python.exe app.py
pause
exit /b
:error
echo Проверьте Python и интернет.
pause
