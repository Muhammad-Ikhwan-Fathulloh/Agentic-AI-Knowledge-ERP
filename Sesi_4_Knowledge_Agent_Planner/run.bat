@echo off
REM =============================================================
REM  Sesi 4 — Knowledge Agent Planner (Port 8003)
REM  Butuh Sesi 2 API (port 8001) sebagai Knowledge Tool
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt

start "Sesi2-KnowledgeAPI" cmd /k "cd ..\Sesi_2 && call .venv\Scripts\activate.bat && uvicorn app.main:app --port 8001"
timeout /t 5 /nobreak

uvicorn app.main:app --port 8003 --reload
