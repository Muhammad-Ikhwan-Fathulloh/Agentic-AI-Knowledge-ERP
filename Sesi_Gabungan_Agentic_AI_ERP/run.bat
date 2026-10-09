@echo off
chcp 65001 >nul
echo ============================================================
echo   Agentic AI ERP - Gabungan Sesi 1 + Sesi 7
echo   Port: 8080 | Docs: http://127.0.0.1:8080/docs
echo ============================================================
echo.

if not exist venv (
    echo [1/3] Membuat virtual environment...
    python -m venv venv || goto :error
)

echo [2/3] Mengaktifkan virtual env & install dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt || goto :error

echo.
echo [3/3] Menjalankan FastAPI (Agentic AI ERP)...
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

goto :eof

:error
echo.
echo [ERROR] Gagal menjalankan Agentic AI ERP.
exit /b 1
