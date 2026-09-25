@echo off
REM =============================================================
REM  Sesi 8 - Agentic AI Orchestrator (Port 8000)
REM  Akan menjalankan 4 service sekaligus:
REM    Sesi 2 (KA CRUD 8001)
REM    Sesi 5 (ERP CRUD 8005)
REM    Sesi 7 (ERP Report 8007)
REM    Sesi 8 (Orchestrator 8000)
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt

start "Sesi2-KaCrud"       cmd /k "cd /d ""%~dp0..\Sesi_2_Knowledge_Agent_CRUD"" && call run.bat"
start "Sesi5-ERP-CRUD"     cmd /k "cd /d ""%~dp0..\Sesi_5_Knowledge_ERP_CRUD"" && call run.bat"
start "Sesi7-ERP-Report"   cmd /k "cd /d ""%~dp0..\Sesi_7_Knowledge_ERP_Generate"" && call run.bat"
timeout /t 8 /nobreak

uvicorn app.main:app --port 8000 --reload
