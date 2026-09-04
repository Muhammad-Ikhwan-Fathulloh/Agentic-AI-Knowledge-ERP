@echo off
REM =============================================================
REM  Sesi 5 — Knowledge ERP CRUD (Port 8005)
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --port 8005 --reload
