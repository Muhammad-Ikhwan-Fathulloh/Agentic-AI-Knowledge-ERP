@echo off
REM =============================================================
REM  Sesi 6 - ERP ReAct Agent & ERP API (Merged Port 8006)
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt

uvicorn app.main:app --port 8006 --reload
