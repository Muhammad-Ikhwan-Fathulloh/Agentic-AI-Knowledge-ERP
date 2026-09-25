# Sesi 7 - Knowledge ERP Generate (Laporan Naratif via Qwen)

## Ringkasan
Menggunakan Qwen lokal untuk **mengubah data ERP terstruktur (angka) menjadi narasi bahasa natural** laporan bisnis yang siap kirim / presentasikan.

## Tiga Laporan yang Didukung
| Endpoint                                   | Input               | Output                                                                                   |
| ------------------------------------------ | ------------------- | ---------------------------------------------------------------------------------------- |
| `POST /report/sales`                       | `{"days": 7}`       | Ringkasan 4 paragraf: total revenue, 3 terlaris, tren, 1 rekomendasi actionable          |
| `POST /report/low-stock`                   | `{"threshold": 10}` | Notulensi 6 kalimat: SKU count, 3 terendah, dampak, usulan restock, prioritas, next step |
| `GET /report/combined?days=7&threshold=10` | query param         | Gabungan kedua laporan di atas                                                           |

## Aliran Data
```
[SQL / ERP API Sesi 5]  →  serialisasi → summary TEXT  →  prompt Qwen  →  narasi final
```

## Cara Run
```cmd
run.bat
```
(Otomatis spawning Sesi 5 + Sesi 7)

## Persiapan llama.cpp & Model Lokal

Proyek ini menggunakan LLM secara lokal (Local AI). Ikuti langkah ini agar LLM bisa berjalan:

**1. Siapkan Binary llama-server**
- Download *release* terbaru dari **[GitHub llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)**.
- Ambil file `llama-server.exe` (di Windows) atau `llama-server` (di Mac/Linux).
- Letakkan binary tersebut di folder `../End-to-End LLM Serving/backend/bin/`. (Buat foldernya jika belum ada).

**2. Siapkan File Model GGUF**
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**
- Letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.
- Periksa isian `LLM_MODEL_GGUF` di `.env` Anda agar persis dengan file model yang terinstal.

## Struktur
```
Sesi_7_Knowledge_ERP_Generate/
├── app/
│   ├── config.py / schemas.py / llm.py   (llama port 8083)
│   ├── report_data.py  # ERPReportData: HTTP client ke Sesi 5 /report
│   ├── generators.py   # Prompt SALES_PROMPT / LOW_STOCK_PROMPT + ringkasan data
│   └── main.py
└── tests/test_generators.py  # Test helper _summarize_sales / _summarize_lowstock
```

## Tips Prompt Engineering
- Karena model kecil (Qwen 0.5B–3B), **sangat eksplisit** dengan format jumlah paragraf/kalimat.
- Prefilter data: Jangan kirim 100 baris sekaligus - sort + TOP N saja.
- Bila jawaban terlalu pendek / jelek: naïkan `temperature` sedikit (0.4–0.6) dan tambahkan **few-shot example** di prompt.

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Prasyarat Wajib Sebelum Mulai

1. **Sesi 5 ERP CRUD API (port 8005)** - `run.bat` akan spawn Sesi 5 otomatis
2. **Model GGUF Qwen** di folder `../models/`
3. **Binary `llama-server`** di folder `../bin/`

### Langkah 1 - Setup Folder & Environment

```cmd
mkdir Sesi_7_Knowledge_ERP_Generate
cd Sesi_7_Knowledge_ERP_Generate
mkdir app tests
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn[standard] pydantic pydantic-settings python-dotenv httpx pytest sentence-transformers
```

### Langkah 2 - Buat `.env`

```env
ERP_API_BASE=http://127.0.0.1:8005
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384

LLM_MODEL_GGUF=qwen2.5-0.5b-instruct-q4_k_m.gguf
LLAMA_PORT=8083
LLAMA_CTX=2048
LLAMA_NGL=0
LLAMA_THREADS=3
LLAMA_READY_TIMEOUT=90
LLAMA_BASE_URL=http://127.0.0.1:8083

APP_PORT=8007
DEFAULT_REPORT_DAYS=7
LOW_STOCK_THRESHOLD=10
```

### Langkah 3 - Buat `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    erp_api_base: str = "http://127.0.0.1:8005"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8083
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8083"

    app_port: int = 8007
    default_report_days: int = 7
    low_stock_threshold: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 - Buat `app/report_data.py`

HTTP client yang mengambil data dari Sesi 5 ERP API:

```python
import httpx
from .config import settings

class ERPReportData:
    def __init__(self):
        self.base = settings.erp_api_base

    def get_sales(self, days: int = 7) -> dict:
        r = httpx.get(f"{self.base}/report/sales", params={"days": days}, timeout=10)
        return r.json() if r.status_code == 200 else {}

    def get_low_stock(self, threshold: int = 10) -> list:
        r = httpx.get(f"{self.base}/report/low-stock",
                      params={"threshold": threshold}, timeout=10)
        return r.json() if r.status_code == 200 else []
```

### Langkah 5 - Buat `app/generators.py` (Prompt Engineering Inti)

```python
from .llm import llm_complete
from .config import settings

# ── Prompt untuk Laporan Penjualan ───────────────────────────────────────────
SALES_PROMPT = """Kamu adalah analis bisnis profesional. Buat laporan penjualan dalam Bahasa Indonesia.

DATA PENJUALAN:
{data_summary}

INSTRUKSI FORMAT (WAJIB DIIKUTI PERSIS):
Tulis laporan dalam TEPAT 4 paragraf pendek:
1. Total revenue dan periode laporan
2. Tiga produk terlaris dengan angka penjualan
3. Analisis tren singkat (naik/turun/stabil)
4. SATU rekomendasi actionable yang konkret

Jangan tambahkan bagian lain di luar 4 paragraf ini.
LAPORAN:"""

# ── Prompt untuk Laporan Stok Menipis ───────────────────────────────────────
LOW_STOCK_PROMPT = """Kamu adalah manajer inventory profesional. Buat notulensi stok menipis dalam Bahasa Indonesia.

DATA STOK MENIPIS:
{data_summary}

INSTRUKSI FORMAT (WAJIB DIIKUTI PERSIS):
Tulis notulensi dalam TEPAT 6 kalimat:
1. Jumlah SKU yang stoknya menipis
2. Tiga produk dengan stok terendah (sebut angkanya)
3. Dampak potensial jika tidak segera direstok
4. Usulan jumlah restock minimum
5. Produk yang harus diprioritaskan
6. Next step operasional yang harus diambil hari ini

NOTULENSI:"""


def _summarize_sales(data: dict) -> str:
    """Konversi dict sales report ke teks ringkasan untuk prompt."""
    if not data:
        return "Tidak ada data penjualan tersedia."
    total = data.get("total_revenue", 0)
    days  = data.get("days", 7)
    prods = data.get("products", [])
    lines = [f"Periode: {days} hari terakhir",
             f"Total Revenue: Rp {total:,.0f}",
             "Produk:"]
    for p in prods[:5]:  # top 5 saja
        lines.append(f"  - {p['name']}: {p['qty_sold']} terjual, "
                     f"Rp {p['revenue']:,.0f}")
    return "\n".join(lines)


def _summarize_low_stock(items: list) -> str:
    """Konversi list low-stock ke teks ringkasan untuk prompt."""
    if not items:
        return "Tidak ada produk dengan stok menipis."
    lines = [f"Total {len(items)} SKU stok menipis:"]
    for p in items[:10]:  # max 10
        lines.append(f"  - {p['name']}: stok = {p['stock']} unit")
    return "\n".join(lines)


async def generate_sales_report(days: int = 7) -> str:
    from .report_data import ERPReportData
    data = ERPReportData().get_sales(days)
    summary = _summarize_sales(data)
    prompt = SALES_PROMPT.format(data_summary=summary)
    return await llm_complete(prompt, max_tokens=500, temperature=0.4)


async def generate_low_stock_report(threshold: int = 10) -> str:
    from .report_data import ERPReportData
    items = ERPReportData().get_low_stock(threshold)
    summary = _summarize_low_stock(items)
    prompt = LOW_STOCK_PROMPT.format(data_summary=summary)
    return await llm_complete(prompt, max_tokens=400, temperature=0.4)
```

### Langkah 6 - Buat `app/schemas.py` & `app/main.py`

```python
# schemas.py
from pydantic import BaseModel

class SalesReportRequest(BaseModel):
    days: int = 7

class LowStockReportRequest(BaseModel):
    threshold: int = 10

class ReportResponse(BaseModel):
    report_type: str
    narrative: str
    raw_data_summary: str
```

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .llm import start_llama, stop_llama
from .generators import (generate_sales_report, generate_low_stock_report,
                          _summarize_sales, _summarize_low_stock)
from .report_data import ERPReportData
from .schemas import SalesReportRequest, LowStockReportRequest, ReportResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_llama()
    yield
    stop_llama()

app = FastAPI(title="Sesi 7 - ERP Narrative Report Generator", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/report/sales", response_model=ReportResponse)
async def sales_report(req: SalesReportRequest):
    data = ERPReportData().get_sales(req.days)
    summary = _summarize_sales(data)
    narrative = await generate_sales_report(req.days)
    return ReportResponse(
        report_type="sales",
        narrative=narrative,
        raw_data_summary=summary,
    )

@app.post("/report/low-stock", response_model=ReportResponse)
async def low_stock_report(req: LowStockReportRequest):
    items = ERPReportData().get_low_stock(req.threshold)
    summary = _summarize_low_stock(items)
    narrative = await generate_low_stock_report(req.threshold)
    return ReportResponse(
        report_type="low_stock",
        narrative=narrative,
        raw_data_summary=summary,
    )

@app.get("/report/combined")
async def combined_report(days: int = 7, threshold: int = 10):
    sales_narrative = await generate_sales_report(days)
    stock_narrative = await generate_low_stock_report(threshold)
    return {
        "sales_report": sales_narrative,
        "low_stock_report": stock_narrative,
    }
```

### Langkah 7 - Jalankan & Uji

```cmd
run.bat
```

Buka **http://localhost:8007/docs**

**Langkah uji yang tepat:**

1. **Pastikan ada data di Sesi 5 dulu!** Buka `http://localhost:8005/docs` dan buat beberapa order.

2. **`POST /report/sales`:**
   ```json
   { "days": 7 }
   ```
   Periksa field `narrative` - harus berisi 4 paragraf alami tentang penjualan.

3. **`POST /report/low-stock`:**
   ```json
   { "threshold": 30 }
   ```
   Periksa `narrative` - harus berisi 6 kalimat notulensi stok, bukan bullet point mentah.

4. **`GET /report/combined?days=7&threshold=30`** - kedua laporan sekaligus.

5. **Eksperimen prompt:**
   - Ubah `temperature` dari `0.4` → `0.7` di `generators.py` → apakah narasi lebih kreatif/bervariasi?
   - Tambahkan satu few-shot example di prompt → apakah format lebih konsisten?

### Langkah 8 - Unit Test (Tanpa LLM)

```python
# tests/test_generators.py
from app.generators import _summarize_sales, _summarize_low_stock

def test_summarize_sales_empty():
    result = _summarize_sales({})
    assert "Tidak ada data" in result

def test_summarize_sales_with_data():
    data = {
        "days": 7,
        "total_revenue": 5_000_000,
        "products": [
            {"name": "NocMouse", "qty_sold": 10, "revenue": 3_500_000},
            {"name": "NocSSD",   "qty_sold": 5,  "revenue": 1_500_000},
        ]
    }
    result = _summarize_sales(data)
    assert "NocMouse" in result
    assert "5,000,000" in result or "5.000.000" in result or "5000000" in result

def test_summarize_low_stock_empty():
    result = _summarize_low_stock([])
    assert "Tidak ada" in result

def test_summarize_low_stock_with_data():
    items = [{"name": "NocMouse", "stock": 3}, {"name": "NocSSD", "stock": 7}]
    result = _summarize_low_stock(items)
    assert "NocMouse" in result
    assert "3 unit" in result
```

```cmd
pytest tests/ -v
```

> ✅ **Checkpoint**: `POST /report/sales` mengembalikan paragraf narasi (bukan JSON mentah), `POST /report/low-stock` mengembalikan 6 kalimat notulensi, dan unit test helper functions semua hijau → Sesi 7 selesai!

## Tiga Laporan yang Didukung
| Endpoint                                   | Input               | Output                                                                                   |
| ------------------------------------------ | ------------------- | ---------------------------------------------------------------------------------------- |
| `POST /report/sales`                       | `{"days": 7}`       | Ringkasan 4 paragraf: total revenue, 3 terlaris, tren, 1 rekomendasi actionable          |
| `POST /report/low-stock`                   | `{"threshold": 10}` | Notulensi 6 kalimat: SKU count, 3 terendah, dampak, usulan restock, prioritas, next step |
| `GET /report/combined?days=7&threshold=10` | query param         | Gabungan kedua laporan di atas                                                           |

## Aliran Data
```
[SQL / ERP API Sesi 5]  →  serialisasi → summary TEXT  →  prompt Qwen  →  narasi final
```

## Cara Run
```cmd
run.bat
```
(Otomatis spawning Sesi 5 + Sesi 7)

## Download Model Qwen
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**

Setelah download, letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.

## Struktur
```
Sesi_7_Knowledge_ERP_Generate/
├── app/
│   ├── config.py / schemas.py / llm.py   (llama port 8083)
│   ├── report_data.py  # ERPReportData: HTTP client ke Sesi 5 /report
│   ├── generators.py   # Prompt SALES_PROMPT / LOW_STOCK_PROMPT + ringkasan data
│   └── main.py
└── tests/test_generators.py  # Test helper _summarize_sales / _summarize_lowstock
```

## Tips Prompt Engineering
- Karena model kecil (Qwen 0.5B–3B), **sangat eksplisit** dengan format jumlah paragraf/kalimat.
- Prefilter data: Jangan kirim 100 baris sekaligus - sort + TOP N saja.
- Bila jawaban terlalu pendek / jelek: naïkan `temperature` sedikit (0.4–0.6) dan tambahkan **few-shot example** di prompt.
