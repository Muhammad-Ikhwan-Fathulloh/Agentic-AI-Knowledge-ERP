# Agentic AI ERP v2.0 — Gabungan Sesi 1 & 7 (Dual Knowledge Base + Agentic SOP→ERP Router)

> **Unified FastAPI single instance** yang menyatukan **Knowledge Base Vector DB (Sesi 1)**, **ERP CRUD (Sesi 5)**, dan **LLM Narrative Generator + Agentic Router (Sesi 7)**.
>
> ⭐ **Fitur unggulan v2**: Sistem punya **2 Knowledge Base TERSEPAT** (SOP + ERP Docs). LLM **MEMBACA SOP DULUAN** untuk memahami prosedur, lalu **OTOMATIS memutuskan action ERP** mana yang harus dijalankan (cek stok, lookup produk, laporan penjualan, dll), baru memberikan jawaban final yang akurat — seperti CS manusia yang sungguhan.

---

## 🧱 Arsitektur v2.0 (3 Layer + Agentic Router)

```
┌───────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE (HTML/JS)                      │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    FASTAPI UNIFIED APP (Port 8080)                    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  🤖  AGENTIC LAYER (NEW v2)                                     │   │
│  │  ┌──────────────────┐    ┌──────────────────┐                   │   │
│  │  │ Step 1 : Read    │    │ Step 2 : Router  │                   │   │
│  │  │ SOP KB (search) │    │ LLM/Rule decide   │                   │   │
│  │  └─────────┬────────┘    │ action ERP apa   │                   │   │
│  │            │             └─────────┬────────┘                   │   │
│  │            ▼                       ▼                            │   │
│  │  ┌──────────────────┐    ┌──────────────────┐                   │   │
│  │  │ Step 4 : Final   │◄───│ Step 3 : Execute │                   │   │
│  │  │ LLM Answer       │    │ all ERP actions  │                   │   │
│  │  └──────────────────┘    └──────────────────┘                   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────┐  ┌─────────────────────┐                    │
│  │ 📘 KB #1 : SOP      │  │ 📗 KB #2 : ERP Docs │                    │
│  │  6 SOP seed (Sesi1) │  │  4 spec/supplier    │                    │
│  │  sop_documents table│  │  erp_documents tbl  │                    │
│  │  VSS HNSW index     │  │  VSS HNSW index     │                    │
│  └─────────────────────┘  └─────────────────────┘                    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ 💼 ERP MODULE (Sesi 5)                                           │   │
│  │  products • customers • orders • order_items                     │   │
│  │  report_sales • report_low_stock  (CRUD + Reports)              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ 🧠 LLM MODULE (Sesi 7)                                           │   │
│  │  LlamaClient → llama-server lokal (Qwen 2.5 0.5B Instruct)      │   │
│  │  Sales narrative • Low-stock notulensi • Agentic QA             │   │
│  └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        DUCKDB SINGLE FILE (VSS extension)
                        ─ agentic_ai_erp.duckdb
```

---

## ✨ Fitur Lengkap

### 📘 Knowledge Base #1 — SOP (Standar Operasional Prosedur)
**Tujuan**: Tempat menyimpan *aturan main* / prosedur. Agent BACA SOP DULU sebelum bertindak.

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/sop/ingest/text` | POST | Ingest SOP baru via teks |
| `/sop/ingest/file` | POST | Upload file SOP (PDF/TXT/MD) |
| `/sop/search` | POST | Semantic search HANYA di SOP |
| `/sop/documents` | GET / DELETE | List / reset semua SOP |

**Seed default (6 SOP):**
1. `SOP_Klaim_Garansi` → Auto trigger `lookup_product`
2. `SOP_Pengembalian_Barang_Return` → Auto trigger `lookup_order` / `lookup_customer`
3. `SOP_Pemesanan_Pembayaran` → Auto trigger `lookup_product`
4. `SOP_Pengiriman_Shipping` → Info ongkir & estimasi wilayah
5. `SOP_Stok_Kritis_Reorder` → ⭐ Auto trigger `check_low_stock`
6. `SOP_Analisa_Penjualan` → ⭐ Auto trigger `check_sales_report`

### 📗 Knowledge Base #2 — ERP Docs
**Tujuan**: Spesifikasi produk, katalog, supplier info, master data pendukung (tidak in table produk biasa).

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/erp-docs/ingest/text` | POST | Ingest ERP doc baru |
| `/erp-docs/ingest/file` | POST | Upload file ERP doc |
| `/erp-docs/search` | POST | Semantic search di ERP Docs |
| `/erp-docs/documents` | GET / DELETE | List / reset |

**Seed default (4 dokumen):** Spesifikasi NocBook, NocMouse, Kategori Produk, Supplier + Lead Time.

### 💼 ERP System (Sesi 5)
CRUD penuh untuk 3 entitas + 2 laporan real-time:
- `/products` — Produk dengan **semantic search by nama** (bukan `LIKE` biasa)
- `/customers` — Data customer filter nama
- `/orders` — Buat pesanan dengan **auto cek stok**, auto decrement stok
- `/report/sales?days=7` — Laporan penjualan N hari (total revenue + by product)
- `/report/low-stock?threshold=10` — Produk stok menipis

### 🧠 AI Generator + ⭐ Agentic Router
| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/ai/report/sales` | POST | **LLM Narrative**: Laporan eksekutif penjualan 4 paragraf formal |
| `/ai/report/low-stock` | POST | **LLM Narrative**: Notulensi stok kritis 6 poin |
| `/ai/report/combined` | GET | Gabungan keduanya (untuk manajemen) |
| `/ai/knowledge/qa` | POST | Legacy RAG (merge search SOP+ERP → jawab tanpa routing) |
| **⭐ `/ai/agentic/qa`** | **POST** | **ENDPOINT UTAMA v2**: SOP→Router→Execute→Final Answer |

**7 Action ERP yang bisa dijalankan Router secara OTOMATIS:**
| Action | Kapan Dipilih (berdasarkan SOP) |
|--------|---------------------------------|
| `lookup_product` | User tanya produk / harga / stok |
| `check_low_stock` | User tanya stok menipis / reorder (SOP Stok_Kritis) |
| `check_sales_report` | User minta laporan penjualan (SOP_Analisa_Penjualan) |
| `lookup_customer` | Menyebut nama / email customer |
| `lookup_order` | Menyebut order_id di pertanyaan return |
| `lookup_erp_knowledge` | Perlu spesifikasi detail / supplier info |
| `no_erp_needed` | Hanya tanya prosedur umum (cukup jawab dari SOP) |

---

## 🚀 Cara Menjalankan (Windows)

### 1. Quick Start via Batch
```bat
cd Sesi_Gabungan_Agentic_AI_ERP
run.bat
```

Batch script akan otomatis:
- Buat venv jika belum ada
- Install semua dependencies dari `requirements.txt`
- Jalankan `uvicorn` di `http://127.0.0.1:8080` dengan hot-reload

### 2. Manual via CLI
```bash
cd Sesi_Gabungan_Agentic_AI_ERP
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 3. Via Docker
```bash
cd Sesi_Gabungan_Agentic_AI_ERP
docker build -t agentic-ai-erp:v2 .
docker run -p 8080:8080 agentic-ai-erp:v2
```

### 4. Setelah Running
- **Swagger UI**: http://127.0.0.1:8080/docs  (test semua endpoint via browser)
- **Health**: http://127.0.0.1:8080/health
- **Stats (lengkap)**: http://127.0.0.1:8080/stats
- **Frontend (HTML)**: buka file `frontend/index.html` langsung di browser (atau via `/static` jika di-serve)

---

## 🧪 Contoh Test ⭐ Agentic Endpoint

### Contoh 1: Klaim Garansi (Router → lookup_product)
```http
POST /ai/agentic/qa
Content-Type: application/json

{
  "q": "Laptop NocBook Pro 14 saya layarnya pecah, bagaimana klaim garansinya?",
  "k": 4
}
```
**Yang terjadi dibelakang layar**:
1. 🔍 SOP Search → match `SOP_Klaim_Garansi`
2. 🧭 Router memutus `actions: [lookup_product(NocBook), lookup_erp_knowledge(spesifikasi)]`
3. ⚙️ Execute: Dapat data produk NocBook (harga Rp12.500.000, stok 25) + spesifikasi OLED/CPU/RAM
4. ✍️ Final: Jawaban CS + data produk aktual + SOP 4 langkah klaim

### Contoh 2: Staf Gudang Reorder (Router → check_low_stock)
```json
{ "q": "Ada barang apa saja stoknya dibawah 20 unit? Saya mau PO besok.", "k": 4 }
```
→ Router otomatis pilih `check_low_stock(20)` + `lookup_product` berdasarkan SOP Stok_Kritis_Reorder.

### Contoh 3: Manager Minta Laporan
```json
{ "q": "Berikan analisa penjualan 14 hari terakhir + produk terlarisnya!", "k": 4 }
```
→ Router pilih `check_sales_report(14)` menurut SOP_Analisa_Penjualan.

---

## 📦 Dependencies (requirements.txt)
| Paket | Versi | Fungsi |
|-------|-------|--------|
| `fastapi` | 0.115.0 | Web framework |
| `uvicorn[standard]` | 0.30.6 | ASGI server |
| `pydantic` / `pydantic-settings` | 2.9.2 / 2.5.2 | Validasi & Settings |
| `duckdb` | 1.1.2 | Database + VSS extension (vector search) |
| `sentence-transformers` | 3.2.1 | `all-MiniLM-L6-v2` → 384-dim embeddings |
| `pypdf` | 5.0.1 | Ekstraksi teks PDF |
| `httpx` | 0.27.2 | Async HTTP (ke llama-server) |
| `python-multipart` | 0.0.12 | Upload file |
| `numpy` | <2.0 | Kompatibilitas sentence-transformers |

---

## 🧪 Jalankan Unit Test
```bash
cd Sesi_Gabungan_Agentic_AI_ERP
pip install pytest httpx
pytest tests/test_agentic_erp.py -v
```

**Cakupan test (6 TestClass, 25+ testcase):**
1. `TestSystem` — health v2 info, stats dual KB
2. `TestKBSOP` — seed lengkap, search garansi, ingest SOP
3. `TestKBERPDocs` — seed ERP docs, search spesifikasi NocBook (harus match OLED)
4. `TestERP` — semantic search produk, full order flow + reports
5. **⭐ `TestAgenticSOPEPR`** — 5 kasus agentic: garansi→lookup_product, stok→check_low_stock, laporan→check_sales_report, return→no_erp_needed, produk→lookup_product
6. `TestAIGenerator` — struktur report sales/low-stock/combined

---

## 📁 Struktur Folder
```
Sesi_Gabungan_Agentic_AI_ERP/
├── app/
│   ├── __init__.py
│   ├── config.py           # Settings + .env loader (pydantic-settings)
│   ├── embeddings.py       # Shared SentenceTransformer singleton
│   ├── ingest.py           # PDF/TXT/MD extractor
│   ├── database.py         # ⭐ DUAL KB (sop_documents + erp_documents)
│   │                       #    + CRUD ERP + reports + SEED DATA
│   ├── schemas.py          # Pydantic models (Termasuk AgentAction/Plan/Response)
│   ├── llm.py              # LlamaClient → start llama-server lokal /health poll
│   ├── generators.py       # ⭐ Agentic pipeline + prompts + executor
│   └── main.py             # FastAPI semua endpoint (100+ route handlers)
├── frontend/
│   └── index.html          # Frontend Bootstrap 5 + Vanilla JS
├── tests/
│   └── test_agentic_erp.py # Suite lengkap 25+ testcase
├── .env                    # Default konfigurasi (app_port=8080, llama_port=8088)
├── .gitignore
├── requirements.txt
├── run.bat                 # Windows one-click runner
├── Dockerfile              # Python 3.11-slim image
└── README.md               # Dokumen yang sedang kamu baca 😊
```

---

## 🛠️ Konfigurasi (.env)

```env
APP_PORT=8080                                   # FastAPI port
EMBED_MODEL=all-MiniLM-L6-v2                    # SentenceTransformer model
EMBED_DIM=384                                    # Dimensi embedding
CHUNK_SIZE=400 ; CHUNK_OVERLAP=80                # Chunking params
DUCKDB_PATH=./agentic_ai_erp.duckdb              # Path database file

# LLM (llama-server lokal via bin/llama-server.exe)
LLM_MODEL_GGUF=qwen2.5-0.5b-instruct-q4_k_m.gguf  # Letakkan di ../models/
LLAMA_PORT=8088
LLAMA_CTX=2048 ; LLAMA_NGL=0 ; LLAMA_THREADS=3
LLAMA_BASE_URL=http://127.0.0.1:8088

# AI Generator defaults
DEFAULT_REPORT_DAYS=7
LOW_STOCK_THRESHOLD=10
```

> **Catatan LLM**: Jika model GGUF tidak ditemukan di `../models/`, sistem **tidak error fatal**.
> LLM hanya berstatus "not ready" dan Router otomatis fallback ke **rule-based heuristics** (keyword matching) yang juga akurat.
> Laporan narrative berisi fallback text, namun struktur + data ERP TETAP benar.

---

## 🔗 Perbandingan v1.0 → v2.0

| Aspek | v1.0 | v2.0 |
|-------|------|------|
| Knowledge Base | 1 tabel `documents` (campur) | ⭐ **2 tabel terpisah**: `sop_documents` + `erp_documents` |
| Alur QA | RAG 1-step: search → jawab | ⭐ **Agentic 4-step**: Read SOP → Decide Action → Execute ERP → Final Answer |
| ERP Access | Static via endpoint `/products` etc | ⭐ **Router OTOMATIS pilih & jalankan action** tanpa user intervention |
| Router / Planner | Tidak ada | LLM JSON parser + rule-based fallback (7 actions) |
| Seed SOP | 8 campuran FAQ+SOP | 6 SOP **dengan embedded instruction action** apa yang dijalankan |
| Seed ERP docs | Tidak ada | 4 dokumen (spesifikasi produk, supplier, kategori) |
| Endpoints | ~25 route | ~45 route (KB SOP terpisah + KB ERP Docs terpisah + ⭐ `/ai/agentic/qa`) |
| Test coverage | Basic | 25+ test termasuk 5 testcase agentic routing end-to-end |

---

## 📚 Referensi Modul Sesi Asal
- **Sesi 1 - Prepare Data Knowledge**: Embeddings, chunking, ingest text/file, semantic search → Diadaptasi menjadi **2 KB terpisah** (sop + erp_docs)
- **Sesi 5 - Knowledge ERP CRUD**: products/customers/orders + reports → Menjadi layer execution router
- **Sesi 7 - Knowledge ERP Generate**: LlamaClient + narrative prompts → Ditingkatkan dengan **router executor**

**Author**: Proyek Pembelajaran Agentic AI & Knowledge-Based ERP
**License**: Untuk keperluan pendidikan & riset.
