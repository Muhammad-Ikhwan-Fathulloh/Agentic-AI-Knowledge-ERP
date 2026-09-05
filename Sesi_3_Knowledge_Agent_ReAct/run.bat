@echo off
REM =============================================================
REM  Sesi 3 — Knowledge Agent ReAct  (Port 8002)
REM
REM  Knowledge base dikelola LOKAL (DuckDB di folder ini).
REM  Tidak perlu Sesi 2 (Port 8001) jalan terpisah.
REM
REM  Opsional — jika ingin pakai Sesi 2 sebagai sumber data:
REM    set USE_LOCAL_DB=false di .env, lalu jalankan Sesi 2 dulu.
REM
REM  Pastikan folder `End-to-End LLM Serving/models` berisi file GGUF Qwen.
REM  📥 Download model: https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing
REM =============================================================
cd /d "%~dp0"

if not exist .venv (
    echo [1/2] Membuat virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/2] Install dependencies + run Service ReAct (Port 8002)...
pip install -r requirements.txt

uvicorn app.main:app --port 8002 --reload
