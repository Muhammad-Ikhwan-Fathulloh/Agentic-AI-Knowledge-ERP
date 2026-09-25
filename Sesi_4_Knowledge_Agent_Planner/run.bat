@echo off
REM =============================================================
REM  Sesi 4 — Knowledge Agent Planner (Port 8003)
REM  Butuh Sesi 2 API (port 8001) sebagai Knowledge Tool
REM
REM  Catatan: Sesi ini bisa berdiri sendiri karena run.bat akan
REM  otomatis menyalin knowledge.duckdb dari Sesi 2 bila belum ada.
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt

REM -- Salin knowledge.duckdb dari Sesi 2 bila belum ada lokal --
if not exist knowledge.duckdb (
    if exist ..\Sesi_2_Knowledge_Agent_CRUD\knowledge.duckdb (
        echo [INFO] Menyalin knowledge.duckdb dari Sesi_2_Knowledge_Agent_CRUD...
        copy "..\Sesi_2_Knowledge_Agent_CRUD\knowledge.duckdb" "knowledge.duckdb"
    ) else (
        echo [WARN] knowledge.duckdb tidak ditemukan di Sesi_2_Knowledge_Agent_CRUD.
        echo [WARN] Pastikan Sesi 1 atau Sesi 2 sudah pernah dijalankan sekali.
    )
)

REM -- Jalankan Sesi 2 sebagai dependency (Knowledge API di port 8001) --
start "Sesi2-KnowledgeAPI" cmd /k "cd /d ""%~dp0..\Sesi_2_Knowledge_Agent_CRUD"" && call .venv\Scripts\activate.bat && uvicorn app.main:app --port 8001"
timeout /t 5 /nobreak

uvicorn app.main:app --port 8003 --reload
