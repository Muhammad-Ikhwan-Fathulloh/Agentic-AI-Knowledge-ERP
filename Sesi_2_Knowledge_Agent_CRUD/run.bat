@echo off
REM =============================================================
REM  Sesi 2 - Knowledge Agent CRUD REST API (Port 8001)
REM  Menyediakan CRUD + semantic search untuk tabel documents
REM  (DuckDB knowledge.duckdb).
REM  File .venv dan knowledge.duckdb tidak perlu dibuat ulang
REM  jika sudah ada dari Sesi 1 (karena path .env default = ./knowledge.duckdb).
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo [Sesi 2] Knowledge Agent CRUD siap.
echo   Port: 8001
echo   Swagger UI: http://localhost:8001/docs
echo.
uvicorn app.main:app --port 8001 --reload
