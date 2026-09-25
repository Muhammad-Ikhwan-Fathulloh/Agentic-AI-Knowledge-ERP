@echo off
REM =============================================================
REM  Sesi 1 - Prepare Data Knowledge & Vector DB (Port 8000)
REM  Pipeline: Load → Clean → Chunk → Embed → Store (DuckDB VSS)
REM  Seed otomatis 8 contoh FAQ + SOP bila DB kosong.
REM =============================================================
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo [Sesi 1] Jalankan FastAPI:
echo   - GET  /health                 -> cek koneksi + jumlah dokumen
echo   - GET  /stats                  -> ringkasan chunk per source
echo   - POST /ingest/text            -> simpan teks + chunking otomatis
echo   - POST /ingest/file            -> upload PDF/TXT/MD (via Swagger /docs)
echo   - POST /search                 -> semantic search
echo   - GET  /documents              -> lihat semua chunk
echo.
uvicorn app.main:app --port 8000 --reload
