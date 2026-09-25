# Sesi 6 - Knowledge ERP ReAct Agent (Port 8006)

## Ringkasan
Menyambungkan **loop ReAct** dengan **tool registry ERP** (Sesi 5 API). Agent sekarang bisa **melakukan aksi bisnis** bukan cuma mencari informasi.

## Tool yang Tersedia
| Tool                   | Kapan dipakai                                            |
| ---------------------- | -------------------------------------------------------- |
| `list_products`        | User ingin lihat daftar produk / "tampilkan semua"       |
| `check_stock`          | User nanya stok / ketersediaan produk                    |
| `list_customers`       | Sebelum create_order (agent harus dapat `customer_id`)   |
| `get_order_status`     | User nanya status order berdasarkan ID                   |
| `create_order`         | Agent "stage" order (BELUM final, perlu konfirmasi user) |
| `confirm_create_order` | Finalisasi order bila jawaban user = YA/SETUJU           |

## Guardrail Penting
- **Human-in-the-loop**: `create_order` hanya distage → user harus jawab **YA** via field `confirm_answer` di request berikutnya.
- Agent di-prod (via prompt) **wajib** panggil `check_stock` dan `list_customers` sebelum `create_order`.

## Cara Run
```cmd
run.bat
```
(Otomatis spawning Sesi 5 ERP CRUD + Sesi 6 Agent ReAct)

## Persiapan llama.cpp & Model Lokal

Proyek ini menggunakan LLM secara lokal (Local AI). Ikuti langkah ini agar LLM bisa berjalan:

**1. Siapkan Binary llama-server**
- Download *release* terbaru dari **[GitHub llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)**.
- Ambil file `llama-server.exe` (di Windows) atau `llama-server` (di Mac/Linux).
- Letakkan binary tersebut di folder `../bin/`. (Buat foldernya jika belum ada).

**2. Siapkan File Model GGUF**
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**
- Letakkan file `.gguf` di folder `../models/`.
- Periksa isian `LLM_MODEL_GGUF` di `.env` Anda agar persis dengan file model yang terinstal.

## Endpoint
| Endpoint           | Method | Body                                               |
| ------------------ | ------ | -------------------------------------------------- |
| `POST /agent/chat` | POST   | `{"query":"...","confirm_answer":"ya"}` (opsional) |

Contoh percakapan 2-langkah:
1. Request 1: `{"query":"Saya ingin beli 2 NocMouse untuk Budi Santoso"}`
   → Response: `need_human_confirm: true`, prompt_confirm minta konfirmasi.
2. Request 2: `{"query":"lanjutkan","confirm_answer":"ya"}`
   → Order final disimpan.

## Struktur
```
Sesi_6_Knowledge_ERP_ReAct/
├── app/
│   ├── config.py / schemas.py / llm.py   (llama port 8082)
│   ├── tools.py       # ERPTools class (panggil HTTP Sesi 5)
│   ├── react_erp.py   # ReAct loop + ERP_REACT_SYSTEM prompt + parse step
│   └── main.py
└── tests/test_erp_react.py  # Test parser Thought/Action/Action Input
```

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Prasyarat Wajib Sebelum Mulai

1. **Sesi 5 ERP CRUD API (port 8005) harus bisa distart** - `run.bat` akan spawn Sesi 5 otomatis
2. **Model GGUF Qwen** di folder `../models/`
3. **Binary `llama-server`** di folder `../bin/`

### Langkah 1 - Setup Folder & Environment

```cmd
mkdir Sesi_6_Knowledge_ERP_ReAct
cd Sesi_6_Knowledge_ERP_ReAct
mkdir app tests
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn[standard] pydantic pydantic-settings python-dotenv httpx pytest
```

### Langkah 2 - Buat `.env`

```env
ERP_API_BASE=http://127.0.0.1:8005

LLM_MODEL_GGUF=qwen2.5-0.5b-instruct-q4_k_m.gguf
LLAMA_PORT=8082
LLAMA_CTX=2048
LLAMA_NGL=0
LLAMA_THREADS=3
LLAMA_READY_TIMEOUT=90
LLAMA_BASE_URL=http://127.0.0.1:8082

APP_PORT=8006
MAX_REACT_STEPS=5
REQUIRE_HUMAN_CONFIRM_FOR_CREATE_ORDER=true
```

### Langkah 3 - Buat `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    erp_api_base: str = "http://127.0.0.1:8005"

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8082
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8082"

    app_port: int = 8006
    max_react_steps: int = 5
    require_human_confirm_for_create_order: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 - Buat `app/tools.py` (ERP Tool Registry)

```python
import httpx, json
from .config import settings

BASE = settings.erp_api_base

class ERPTools:
    def call(self, action: str, action_input: str) -> str:
        a = action.lower()
        if a == "list_products":     return self._list_products()
        if a == "check_stock":       return self._check_stock(action_input)
        if a == "list_customers":    return self._list_customers()
        if a == "create_order":      return self._stage_order(action_input)
        if a == "get_order_status":  return self._get_order(action_input)
        return f"Tool '{action}' tidak dikenal."

    def _list_products(self) -> str:
        r = httpx.get(f"{BASE}/products", timeout=10)
        prods = r.json()
        lines = [f"- [{p['id'][:8]}] {p['name']} | Stok: {p['stock']} | Harga: Rp {p['price']:,.0f}"
                 for p in prods]
        return "\n".join(lines) if lines else "Tidak ada produk."

    def _check_stock(self, product_name: str) -> str:
        r = httpx.get(f"{BASE}/products", params={"name": product_name}, timeout=10)
        prods = r.json()
        if not prods:
            return f"Produk '{product_name}' tidak ditemukan."
        p = prods[0]
        return (f"Produk: {p['name']}\n"
                f"ID: {p['id']}\n"
                f"Stok: {p['stock']} unit\n"
                f"Harga: Rp {p['price']:,.0f}")

    def _list_customers(self) -> str:
        r = httpx.get(f"{BASE}/customers", timeout=10)
        custs = r.json()
        lines = [f"- [{c['id'][:8]}] {c['name']} ({c['email']})" for c in custs]
        return "\n".join(lines) if lines else "Tidak ada pelanggan."

    def _stage_order(self, json_str: str) -> str:
        """Stage order - kembalikan data untuk dikonfirmasi user, belum simpan ke DB."""
        try:
            data = json.loads(json_str)
            return (f"[STAGED] Order siap dikonfirmasi:\n"
                    f"Customer ID: {data.get('customer_id')}\n"
                    f"Items: {data.get('items')}\n"
                    f"Ketik 'ya' di field confirm_answer untuk finalisasi.")
        except Exception as e:
            return f"Format order salah: {e}"

    def confirm_order(self, customer_id: str, items: list) -> str:
        """Finalisasi order ke Sesi 5 API."""
        try:
            r = httpx.post(f"{BASE}/orders",
                           json={"customer_id": customer_id, "items": items},
                           timeout=10)
            if r.status_code == 200:
                d = r.json()
                return f"✅ Order berhasil! ID: {d['order_id']}, Total: Rp {d['total_price']:,.0f}"
            return f"❌ Gagal: {r.text}"
        except Exception as e:
            return f"Error: {e}"

    def _get_order(self, order_id: str) -> str:
        r = httpx.get(f"{BASE}/orders/{order_id.strip()}", timeout=10)
        if r.status_code == 200:
            o = r.json()
            return f"Order {o['id'][:8]}: status={o['status']}, total=Rp {o['total_price']:,.0f}"
        return "Order tidak ditemukan."
```

### Langkah 5 - Buat `app/react_erp.py`

```python
import re, json
from .llm import llm_complete
from .tools import ERPTools
from .schemas import StepLog

ERP_REACT_SYSTEM = """Kamu adalah ERP Agent yang membantu user mengelola produk dan pesanan.

Tool yang TERSEDIA:
- list_products[]: tampilkan semua produk dan stok
- check_stock[nama_produk]: cek ketersediaan produk tertentu
- list_customers[]: tampilkan daftar pelanggan
- create_order[{"customer_id":"...","items":[{"product_id":"...","qty":N}]}]: siapkan order (perlu konfirmasi)
- get_order_status[order_id]: cek status pesanan

FORMAT WAJIB:
Thought: <reasoning>
Action: <nama_tool atau FINISH>
Action Input: <parameter atau jawaban final>

ATURAN ORDER:
1. Selalu cek stok dengan check_stock SEBELUM create_order
2. Selalu ambil customer_id dari list_customers SEBELUM create_order
3. create_order hanya MENSTAGE order - user harus konfirmasi
4. Jika user sudah konfirmasi (confirm_answer=ya), lanjut finalisasi
"""

def _parse_step(output: str):
    t  = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    a  = re.search(r"Action:\s*(\w+)", output)
    ai = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)
    return (
        t.group(1).strip()  if t  else "",
        a.group(1).strip()  if a  else "",
        ai.group(1).strip() if ai else "",
    )

async def erp_react_loop(query: str, confirm_answer: str = "",
                          max_steps: int = 5, temperature: float = 0.3):
    tools = ERPTools()
    history = ERP_REACT_SYSTEM + f"\nPermintaan user: {query}\n"
    if confirm_answer:
        history += f"[User telah mengkonfirmasi: {confirm_answer}]\n"

    steps = []
    staged_order = None  # menyimpan order yang di-stage

    for step_num in range(1, max_steps + 1):
        raw = await llm_complete(history, max_tokens=400, temperature=temperature,
                                  stop=["Observation:"])
        thought, action, action_input = _parse_step(raw)
        log = StepLog(step=step_num, thought=thought, action=action,
                      action_input=action_input, observation="")

        valid_actions = {"list_products","check_stock","list_customers",
                         "create_order","get_order_status","finish"}
        if not action or action.lower() not in valid_actions:
            log.observation = "Format invalid. Gunakan Action yang valid."
            steps.append(log)
            history += raw + f"\nObservation: {log.observation}\n"
            continue

        if action.upper() == "FINISH":
            steps.append(log)
            # Cek apakah ada order staged + user konfirmasi
            need_confirm = staged_order is not None and not confirm_answer.lower() in ("ya","yes","setuju")
            return action_input, steps, need_confirm, staged_order

        if action.lower() == "create_order":
            obs = tools.call(action, action_input)
            try:
                staged_order = json.loads(action_input)
            except Exception:
                pass
        else:
            obs = tools.call(action, action_input)

        log.observation = obs
        steps.append(log)
        history += raw + f"\nObservation: {obs}\n"

    final = steps[-1].observation if steps else "(tidak ada jawaban)"
    return f"[Max steps] {final}", steps, False, staged_order
```

### Langkah 6 - Buat `app/schemas.py` & `app/main.py`

```python
# schemas.py
from pydantic import BaseModel
from typing import Optional

class StepLog(BaseModel):
    step: int
    thought: str
    action: str
    action_input: str
    observation: str

class ERPChatRequest(BaseModel):
    query: str
    confirm_answer: str = ""
    max_steps: int = 5

class ERPChatResponse(BaseModel):
    query: str
    final_answer: str
    need_human_confirm: bool
    prompt_confirm: Optional[str] = None
    steps: list[StepLog]
```

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .llm import start_llama, stop_llama
from .react_erp import erp_react_loop
from .tools import ERPTools
from .schemas import ERPChatRequest, ERPChatResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_llama()
    yield
    stop_llama()

app = FastAPI(title="Sesi 6 - ERP ReAct Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/agent/chat", response_model=ERPChatResponse)
async def chat(req: ERPChatRequest):
    answer, steps, need_confirm, staged = await erp_react_loop(
        req.query, req.confirm_answer, req.max_steps
    )

    # Jika ada order staged + konfirmasi diterima → finalisasi
    if staged and req.confirm_answer.lower() in ("ya","yes","setuju"):
        tools = ERPTools()
        result = tools.confirm_order(staged["customer_id"], staged["items"])
        answer = result
        need_confirm = False

    return ERPChatResponse(
        query=req.query,
        final_answer=answer,
        need_human_confirm=need_confirm,
        prompt_confirm="Ketik 'ya' di field confirm_answer untuk melanjutkan." if need_confirm else None,
        steps=steps,
    )
```

### Langkah 7 - Jalankan & Uji Percakapan Multi-Turn

```cmd
run.bat
```

Buka **http://localhost:8006/docs** → `POST /agent/chat`

**Skenario lengkap order:**

**Turn 1 - Minta order:**
```json
{ "query": "Saya ingin beli 2 NocMouse Wireless untuk pelanggan Budi Santoso" }
```
Harapan: agent memanggil `list_customers` → `check_stock` → `create_order` → response `need_human_confirm: true`

**Turn 2 - Konfirmasi:**
```json
{
  "query": "lanjutkan pesanan",
  "confirm_answer": "ya"
}
```
Harapan: order disimpan ke Sesi 5, response `"✅ Order berhasil!"`

**Verifikasi di Sesi 5:** buka `http://localhost:8005/docs` → `GET /orders` → pastikan order tadi muncul dengan `status: pending`.

### Langkah 8 - Unit Test Parser

```python
# tests/test_erp_react.py
from app.react_erp import _parse_step

def test_parse_action():
    output = "Thought: Cek stok dulu\nAction: check_stock\nAction Input: NocMouse"
    t, a, ai = _parse_step(output)
    assert a == "check_stock"
    assert "NocMouse" in ai

def test_parse_finish():
    output = "Thought: Semua selesai\nAction: FINISH\nAction Input: Order berhasil dibuat."
    _, a, ai = _parse_step(output)
    assert a == "FINISH"
    assert "berhasil" in ai
```

```cmd
pytest tests/ -v
```

> ✅ **Checkpoint**: Agent berhasil menjalankan skenario order 2-turn (request order → konfirmasi), stok berkurang di Sesi 5, dan order muncul di `GET /orders` → Sesi 6 selesai!
