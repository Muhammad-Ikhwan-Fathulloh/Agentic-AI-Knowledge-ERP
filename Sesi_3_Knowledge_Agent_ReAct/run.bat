@echo off
REM =============================================================
REM  Sesi 3 — Knowledge Agent ReAct  (Port 8002)
REM  Sebelum jalan: pastikan Sesi 2 Knowledge API (Port 8001) sudah jalan
REM  dan folder `End-to-End LLM Serving/models` berisi file GGUF Qwen.
REM =============================================================
cd /d "%~dp0"

if not exist .venv (
    echo [1/2] Membuat virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/2] Install dependencies + run Service ReAct...
pip install -r requirements.txt

start "Sesi2-KnowledgeAPI" cmd /k "cd ..\Sesi_2 && call .venv\Scripts\activate.bat && uvicorn app.main:app --port 8001"
timeout /t 5 /nobreak

uvicorn app.main:app --port 8002 --reload
