@echo off
REM =============================================================
REM  Sesi 7 — ERP Narrative Report Generate (Port 8007)
REM  Butuh Sesi 5 ERP API (port 8005)
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt

start "Sesi5-ERP-CRUD" cmd /k "cd /d ""%~dp0..\Sesi_5_Knowledge_ERP_CRUD"" && call run.bat"
timeout /t 5 /nobreak

uvicorn app.main:app --port 8007 --reload
