# Agentic Knowledge System — FastAPI + DuckDB + Qwen (Local, 100% Offline-Capable)

**Referensi:** [End-to-End-LLM-Serving](https://github.com/Muhammad-Ikhwan-Fathulloh/End-to-End-LLM-Serving) — diadaptasi dari pola *RAG + semantic layer* pada repo tersebut (yang aslinya pakai PostgreSQL/pgvector) menjadi versi **ringan berbasis DuckDB** (embedded, cocok untuk lab/bootcamp tanpa server DB terpisah). Seluruh reasoning memakai **Qwen 2.5 lokal** (via `llama.cpp`/`llama-cpp-python`, GGUF) — tidak ada dependensi ke LLM cloud/API berbayar, sehingga cocok untuk data sensitif dan environment tanpa akses internet stabil.

## Peta Besar Kurikulum

Kurikulum ini punya **2 domain paralel** yang dibangun dengan pola yang sama (CRUD → ReAct → LLM Reasoning/Generate), lalu digabung di sesi terakhir:

| Domain | Fokus | Sesi |
|---|---|---|
| **Knowledge Agent** | Basis pengetahuan bebas (dokumen, FAQ, artikel) + RAG | 1–4 |
| **Knowledge ERP** | Data transaksional/bisnis (produk, stok, order) + agent aksi | 5–7 |
| **Integrasi** | Menyatukan kedua agent jadi satu orchestrator | 8 |

**Stack teknis dipakai konsisten di semua sesi:**
- **FastAPI** — REST API & tool-serving layer
- **DuckDB** — penyimpanan data + vector search (ekstensi `vss`), embedded, file `.duckdb`
- **Qwen 2.5 (GGUF, via llama.cpp/llama-cpp-python)** — satu-satunya LLM di seluruh kurikulum, dipakai dengan **dua pola prompting berbeda**:
  - **ReAct loop** (Sesi 3, 6) — reasoning iteratif berbasis teks bebas (`Thought/Action/Observation`).
  - **Structured/JSON prompting** (Sesi 4, 7, 8) — Qwen dipaksa mengeluarkan output JSON terstruktur untuk emulasi *function calling*, lalu di-parse dan dieksekusi oleh kode Python (karena model kecil seperti Qwen 0.5B–7B tidak punya native function calling seperti model cloud besar).
- **Sentence-Transformers / text-embedding model** — untuk embedding dokumen

---

## Sesi 1 — Prepare Data Knowledge & Create Vector DB

### Tujuan Pembelajaran
- Peserta memahami pipeline data untuk RAG: ingest → chunking → embedding → simpan vektor.
- Peserta bisa membuat DuckDB sebagai vector store menggunakan ekstensi `vss`.

### Konsep Kunci
- Kenapa perlu vector DB (semantic search vs keyword search).
- Chunking strategy (fixed-size vs recursive/semantic chunking) dan trade-off ukuran chunk.
- Embedding model: pakai model lokal seperti `sentence-transformers` (offline, gratis) — bahas trade-off ukuran model vs kualitas embedding.
- Skema tabel DuckDB untuk dokumen + metadata + vektor.

### Arsitektur
```
[Sumber data: PDF/txt/markdown]
        │
        ▼
   Loader & Cleaner
        │
        ▼
   Chunker (± 300-500 token/chunk, overlap 50-100)
        │
        ▼
   Embedding Model
        │
        ▼
   DuckDB (tabel documents + vss index)
```

### Implementasi Inti
```bash
pip install duckdb sentence-transformers fastapi uvicorn pypdf
```

```python
import duckdb

con = duckdb.connect("knowledge.duckdb")
con.execute("INSTALL vss; LOAD vss;")
con.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR PRIMARY KEY,
    source VARCHAR,
    content TEXT,
    embedding FLOAT[384],
    created_at TIMESTAMP DEFAULT current_timestamp
);
""")
con.execute("CREATE INDEX IF NOT EXISTS idx_emb ON documents USING HNSW (embedding);")
```

```python
from sentence_transformers import SentenceTransformer
import uuid

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dim

def chunk_text(text, size=400, overlap=80):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunks.append(" ".join(words[i:i+size]))
    return chunks

def ingest(text, source):
    for chunk in chunk_text(text):
        emb = model.encode(chunk).tolist()
        con.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
            [str(uuid.uuid4()), source, chunk, emb]
        )
```

### Latihan
1. Siapkan 5–10 dokumen contoh (FAQ produk, SOP, artikel Indonesia).
2. Uji dua ukuran chunk berbeda, bandingkan hasil retrieval untuk query yang sama.
3. Tulis query similarity search manual:
```sql
SELECT source, content,
       array_distance(embedding, ?::FLOAT[384]) AS dist
FROM documents
ORDER BY dist ASC
LIMIT 5;
```

### Deliverable
`knowledge.duckdb` terisi, notebook ingestion + fungsi `search(query, k)` yang mengembalikan top-k chunk.

---

## Sesi 2 — Knowledge Agent: CRUD REST API

### Tujuan Pembelajaran
- Membungkus tabel `documents` di Sesi 1 menjadi REST API penuh (Create, Read, Update, Delete, Search) memakai FastAPI.

### Konsep Kunci
- Desain endpoint RESTful untuk resource `documents`.
- Validasi payload dengan Pydantic.
- Endpoint `/search` sebagai endpoint semantic (bukan CRUD klasik, tapi krusial untuk agent nanti).

### Implementasi Inti
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import duckdb, uuid

app = FastAPI(title="Knowledge Agent API")
con = duckdb.connect("knowledge.duckdb")

class DocIn(BaseModel):
    source: str
    content: str

class DocOut(DocIn):
    id: str

@app.post("/documents", response_model=DocOut)
def create_document(doc: DocIn):
    doc_id = str(uuid.uuid4())
    emb = model.encode(doc.content).tolist()
    con.execute("INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
                [doc_id, doc.source, doc.content, emb])
    return {**doc.dict(), "id": doc_id}

@app.get("/documents/{doc_id}", response_model=DocOut)
def get_document(doc_id: str):
    row = con.execute("SELECT id, source, content FROM documents WHERE id=?", [doc_id]).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    return {"id": row[0], "source": row[1], "content": row[2]}

@app.put("/documents/{doc_id}", response_model=DocOut)
def update_document(doc_id: str, doc: DocIn):
    emb = model.encode(doc.content).tolist()
    con.execute("UPDATE documents SET content=?, source=?, embedding=? WHERE id=?",
                [doc.content, doc.source, emb, doc_id])
    return {**doc.dict(), "id": doc_id}

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    con.execute("DELETE FROM documents WHERE id=?", [doc_id])
    return {"status": "deleted", "id": doc_id}

@app.get("/documents/search")
def search_documents(q: str, k: int = 5):
    q_emb = model.encode(q).tolist()
    rows = con.execute("""
        SELECT id, source, content, array_distance(embedding, ?::FLOAT[384]) AS dist
        FROM documents ORDER BY dist ASC LIMIT ?
    """, [q_emb, k]).fetchall()
    return [{"id": r[0], "source": r[1], "content": r[2], "score": r[3]} for r in rows]
```

### Latihan
1. Lengkapi endpoint `GET /documents` (list + pagination).
2. Tambahkan endpoint `POST /documents/bulk` untuk upload banyak dokumen sekaligus.
3. Uji semua endpoint via Swagger UI (`/docs`).

### Deliverable
API `port 8001` lengkap CRUD + search, terdokumentasi via OpenAPI, siap dipakai sebagai *tool* agent di sesi berikutnya.

---

## Sesi 3 — Knowledge Agent: Prompting ReAct

### Tujuan Pembelajaran
- Peserta memahami pola **ReAct** (Reason → Act → Observe → repeat) untuk agent yang memanggil API sebagai *tool*.
- Implementasi ReAct loop manual dengan **Qwen** lokal (tanpa native function calling, karena model kecil sering tidak reliable dengan format function-call bawaan).

### Konsep Kunci
- Struktur prompt ReAct: `Thought / Action / Action Input / Observation`.
- Parsing output model kecil (Qwen 0.5B–7B) rawan format error → perlu regex parsing yang toleran + guardrail retry.
- Tool registry: memetakan nama tool ke fungsi Python yang memanggil endpoint REST Sesi 2.

### Arsitektur
```
User Query
   │
   ▼
Qwen (ReAct prompt) ──Thought──▶ tentukan Action
   │
   ▼
Tool Executor ──▶ panggil GET /documents/search (REST API Sesi 2)
   │
   ▼
Observation dikembalikan ke prompt ──▶ Qwen lanjut reasoning
   │
   ▼
Final Answer
```

### Implementasi Inti
```python
import requests, re

REACT_SYSTEM = """Kamu adalah agent yang menjawab pertanyaan memakai tool.
Tool tersedia:
- search_knowledge[query]: mencari dokumen relevan di knowledge base.

Format WAJIB setiap langkah:
Thought: <pemikiranmu>
Action: search_knowledge
Action Input: <query pencarian>

Jika sudah cukup informasi:
Thought: <pemikiran akhir>
Final Answer: <jawaban ke user>
"""

def call_tool(action, action_input):
    if action == "search_knowledge":
        r = requests.get("http://localhost:8001/documents/search", params={"q": action_input, "k": 3})
        return r.json()
    return {"error": "unknown tool"}

def react_loop(query, llm_call, max_steps=4):
    history = f"{REACT_SYSTEM}\nQuestion: {query}\n"
    for step in range(max_steps):
        output = llm_call(history)
        if "Final Answer:" in output:
            return output.split("Final Answer:")[-1].strip()

        action_match = re.search(r"Action:\s*(\w+)", output)
        input_match = re.search(r"Action Input:\s*(.+)", output)
        if not action_match or not input_match:
            history += output + "\nThought: Format salah, saya ulangi.\n"
            continue

        observation = call_tool(action_match.group(1).strip(), input_match.group(1).strip())
        history += output + f"\nObservation: {observation}\n"
    return "Maaf, saya belum menemukan jawaban dalam batas langkah."
```

```python
# llm_call untuk Qwen via llama.cpp server (OpenAI-compatible endpoint)
def qwen_llm_call(prompt):
    resp = requests.post("http://localhost:8080/completion", json={
        "prompt": prompt, "n_predict": 256, "stop": ["Observation:"]
    })
    return resp.json()["content"]
```

### Latihan
1. Tambahkan tool kedua: `create_document[content]` yang memanggil `POST /documents`.
2. Buat 5 skenario pertanyaan dan catat berapa kali model gagal format → hitung *success rate*.
3. Tambahkan guardrail: batasi jumlah loop dan log setiap step ke file.

### Deliverable
Fungsi `react_loop()` yang bisa menjawab pertanyaan berbasis knowledge base dengan minimal 1 tool call, plus log trace percakapan.

---

## Sesi 4 — Knowledge Agent dengan LLM Reasoning (Qwen — Structured Prompting)

### Tujuan Pembelajaran
- Peserta memahami pola **structured/JSON prompting** sebagai alternatif ReAct free-text (Sesi 3) untuk mengemulasi *function calling* pada model lokal kecil.
- Peserta bisa membandingkan trade-off dua gaya prompting: ReAct iteratif vs single-shot planner + JSON schema.

### Konsep Kunci
- Model kecil seperti Qwen 0.5B–7B tidak punya native function calling (beda dari model cloud besar) — solusinya: paksa output JSON dengan instruksi ketat + validasi/parsing yang toleran (`json.loads` dengan fallback regex).
- Pola *planner-executor*: satu prompt untuk memutuskan tool + parameter (`need_tool`, `tool`, `args`), lalu satu prompt terpisah untuk menyusun jawaban akhir dari hasil tool.
- Retry strategy ketika output JSON tidak valid (re-prompt dengan pesan error).

### Implementasi Inti
```python
import json, re

PLANNER_PROMPT = """Kamu adalah planner. Tugasmu memutuskan apakah pertanyaan berikut
butuh pencarian di knowledge base, dan menyusun keputusan dalam format JSON PERSIS seperti ini
(tanpa teks lain di luar JSON):

{{"need_tool": true/false, "tool": "search_knowledge", "query": "<isi jika perlu>"}}

Pertanyaan: {question}
JSON:"""

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

def qwen_reasoning_agent(question, qwen_llm_call):
    plan_raw = qwen_llm_call(PLANNER_PROMPT.format(question=question))
    plan = extract_json(plan_raw)

    context = ""
    if plan and plan.get("need_tool"):
        result = call_tool(plan["tool"], plan["query"])
        context = f"\nHasil pencarian: {result}\n"

    final_prompt = f"""Jawab pertanyaan berikut dalam Bahasa Indonesia, gunakan konteks jika tersedia.
{context}
Pertanyaan: {question}
Jawaban:"""
    return qwen_llm_call(final_prompt, stop=None)
```

### Latihan
1. Tambahkan retry: jika `extract_json` mengembalikan `None`, re-prompt Qwen dengan pesan "Output sebelumnya tidak valid JSON, ulangi." (maksimal 2x).
2. Bandingkan 5 pertanyaan yang sama antara `react_loop` (Sesi 3, iteratif) dan `qwen_reasoning_agent` (single-shot planner) — catat jumlah pemanggilan LLM, latency, dan kualitas jawaban.
3. Diskusikan: untuk kasus apa pola ReAct lebih unggul (butuh banyak langkah/informasi bertahap), dan untuk kasus apa planner tunggal sudah cukup?

### Deliverable
Fungsi `qwen_reasoning_agent()` yang berjalan tanpa loop berulang (1–2 kali panggilan LLM), plus tabel perbandingan singkat terhadap pendekatan ReAct Sesi 3.

---

## Sesi 5 — Knowledge ERP: CRUD REST API

### Tujuan Pembelajaran
- Membangun domain kedua: data ERP sederhana (produk, stok, pelanggan, order) dengan DuckDB + FastAPI, sebagai fondasi *action-taking agent* (bukan cuma retrieval seperti Sesi 1–4).

### Konsep Kunci
- Perbedaan Knowledge Agent (baca dokumen) vs Knowledge ERP (baca **dan** menulis data transaksional — perlu validasi lebih ketat).
- Relasi antar tabel di DuckDB (products, customers, orders, order_items).

### Skema Data
```python
con.execute("""
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR PRIMARY KEY, name VARCHAR, price DOUBLE, stock INTEGER
);
CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR PRIMARY KEY, name VARCHAR, email VARCHAR
);
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR PRIMARY KEY, customer_id VARCHAR, status VARCHAR,
    created_at TIMESTAMP DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS order_items (
    id VARCHAR PRIMARY KEY, order_id VARCHAR, product_id VARCHAR,
    qty INTEGER, price DOUBLE
);
""")
```

### Implementasi Inti (contoh: produk & order)
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import duckdb, uuid

erp_app = FastAPI(title="Knowledge ERP API")
erp_con = duckdb.connect("erp.duckdb")

class ProductIn(BaseModel):
    name: str
    price: float
    stock: int

@erp_app.post("/products")
def create_product(p: ProductIn):
    pid = str(uuid.uuid4())
    erp_con.execute("INSERT INTO products VALUES (?, ?, ?, ?)", [pid, p.name, p.price, p.stock])
    return {"id": pid, **p.dict()}

@erp_app.get("/products")
def list_products():
    rows = erp_con.execute("SELECT id, name, price, stock FROM products").fetchall()
    return [{"id": r[0], "name": r[1], "price": r[2], "stock": r[3]} for r in rows]

class OrderIn(BaseModel):
    customer_id: str
    items: list[dict]  # [{"product_id":..., "qty":...}]

@erp_app.post("/orders")
def create_order(o: OrderIn):
    order_id = str(uuid.uuid4())
    erp_con.execute("INSERT INTO orders VALUES (?, ?, 'pending', current_timestamp)",
                     [order_id, o.customer_id])
    for item in o.items:
        price = erp_con.execute("SELECT price FROM products WHERE id=?", [item["product_id"]]).fetchone()[0]
        erp_con.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                         [str(uuid.uuid4()), order_id, item["product_id"], item["qty"], price])
        erp_con.execute("UPDATE products SET stock = stock - ? WHERE id=?", [item["qty"], item["product_id"]])
    return {"order_id": order_id, "status": "pending"}
```

### Latihan
1. Lengkapi CRUD penuh untuk `customers` dan `products` (update & delete).
2. Tambahkan validasi: order ditolak (`HTTPException 400`) jika stok tidak cukup.
3. Buat endpoint `GET /orders/{id}` yang menggabungkan order + item + nama produk (JOIN).

### Deliverable
API ERP (`port 8005`) dengan CRUD produk, pelanggan, order, siap dipakai sebagai *tool* agent ERP.

---

## Sesi 6 — Knowledge ERP: Prompting ReAct

### Tujuan Pembelajaran
- Menghubungkan ReAct loop (pola Sesi 3) ke tool-tool ERP (Sesi 5), sehingga agent bisa **melakukan aksi** (buat order, cek stok) bukan cuma mencari informasi.

### Konsep Kunci
- Agent yang "menulis" data butuh **guardrail lebih ketat** dibanding agent baca-saja: konfirmasi sebelum eksekusi, validasi parameter, logging untuk audit.
- Tool registry ERP: `check_stock`, `create_order`, `get_order_status`.

### Implementasi Inti
```python
ERP_REACT_SYSTEM = """Kamu adalah agent ERP. Tool tersedia:
- check_stock[product_name]: cek stok produk.
- create_order[customer_id, product_id, qty]: buat order baru.
- get_order_status[order_id]: cek status order.

PENTING: sebelum memanggil create_order, pastikan stok cukup (panggil check_stock dulu).

Format:
Thought: ...
Action: <nama_tool>
Action Input: <parameter dalam format JSON>

Jika selesai:
Thought: ...
Final Answer: ...
"""

def call_erp_tool(action, params: dict):
    base = "http://localhost:8005"
    if action == "check_stock":
        products = requests.get(f"{base}/products").json()
        match = [p for p in products if params["product_name"].lower() in p["name"].lower()]
        return match
    if action == "create_order":
        payload = {"customer_id": params["customer_id"],
                   "items": [{"product_id": params["product_id"], "qty": params["qty"]}]}
        return requests.post(f"{base}/orders", json=payload).json()
    if action == "get_order_status":
        return requests.get(f"{base}/orders/{params['order_id']}").json()
    return {"error": "unknown tool"}
```

Loop utamanya sama seperti `react_loop()` di Sesi 3, hanya `call_tool` diganti `call_erp_tool` dan `Action Input` di-parse sebagai JSON, bukan teks bebas.

### Latihan
1. Tambahkan langkah **konfirmasi manusia** (human-in-the-loop) sebelum `create_order` benar-benar dieksekusi.
2. Uji kasus stok tidak cukup — pastikan agent menjawab dengan sopan, bukan error mentah.
3. Log setiap `Action` + `Observation` ke tabel `agent_logs` di DuckDB untuk audit trail.

### Deliverable
`erp_react_loop()` yang bisa menjawab "cek stok" dan membuat order sederhana lewat bahasa natural, dengan log audit.

---

## Sesi 7 — Knowledge ERP dengan LLM Generate (Qwen)

### Tujuan Pembelajaran
- Memakai Qwen lokal bukan untuk tool-calling saja, tapi untuk **generate** — ringkasan laporan, insight, narasi dari data ERP mentah, sepenuhnya on-premise.

### Konsep Kunci
- Perbedaan *reasoning agent* (Sesi 4/6, menentukan aksi) vs *generative reporting* (mengubah data terstruktur jadi narasi/insight bahasa natural).
- Pola: query data → serialisasi ke ringkasan teks → prompt Qwen untuk narasi (single-shot, tanpa perlu ReAct).
- Karena model lokal cenderung lebih pendek/kurang natural dibanding model cloud besar, perlu *prompt engineering* lebih eksplisit (instruksi format, jumlah kalimat, gaya bahasa).

### Implementasi Inti
```python
def generate_sales_report(period_days, qwen_llm_call):
    rows = erp_con.execute("""
        SELECT p.name, SUM(oi.qty) AS total_qty, SUM(oi.qty*oi.price) AS revenue
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN orders o ON o.id = oi.order_id
        WHERE o.created_at >= current_date - INTERVAL ? DAY
        GROUP BY p.name ORDER BY revenue DESC
    """, [period_days]).fetchall()

    data_summary = "\n".join([f"- {r[0]}: {r[1]} unit terjual, revenue Rp{r[2]:,.0f}" for r in rows])

    prompt = f"""Kamu adalah analis bisnis. Berikut data penjualan {period_days} hari terakhir:
{data_summary}

Tulis ringkasan eksekutif TEPAT 3-4 kalimat dalam Bahasa Indonesia formal, mencakup:
produk terlaris, tren yang terlihat, dan satu rekomendasi bisnis yang actionable.
Jangan mengulang data mentah, langsung ke insight."""

    return qwen_llm_call(prompt, stop=None)
```

### Latihan
1. Tambahkan endpoint `GET /erp/report/weekly` yang memanggil `generate_sales_report()`.
2. Buat versi laporan untuk stok kritis (produk dengan stok < 10).
3. Bandingkan: laporan yang dibuat manual (SQL only) vs versi narasi Qwen — diskusikan kualitas bahasa yang dihasilkan model kecil, dan trik prompting apa yang membantu (few-shot example, batasan panjang, dsb).

### Deliverable
Endpoint laporan otomatis berbasis data DuckDB + narasi Qwen lokal, contoh output untuk minimal 2 jenis laporan (penjualan, stok).

---

## Sesi 8 — Finalize Agentic AI

### Tujuan Pembelajaran
- Menggabungkan **Knowledge Agent** (Sesi 1–4) dan **Knowledge ERP** (Sesi 5–7) menjadi satu orchestrator agent, lengkap dengan routing, evaluasi, dan dokumentasi akhir.

### Konsep Kunci
- **Router/orchestrator agent**: menentukan pertanyaan user harus dijawab oleh Knowledge Agent (informasi/dokumen) atau Knowledge ERP (data transaksional/aksi).
- Evaluasi end-to-end: akurasi tool/domain selection, latency, dan perbandingan pola ReAct vs structured prompting.
- Dokumentasi & deployment (docker-compose, seperti pola di repo referensi).

### Arsitektur Akhir
```
                     ┌─────────────────────┐
        User Query ─▶│   Orchestrator Agent │
                     └─────────┬────────────┘
                     Router (rule-based / LLM classifier)
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
     Knowledge Agent (RAG)          Knowledge ERP (Action)
     - search_knowledge             - check_stock
     - Qwen (ReAct/planner)         - create_order
                                     - get_order_status / report
                 └─────────────┬─────────────┘
                                ▼
                        Final Answer to User
```

### Implementasi Inti (router berbasis Qwen — structured prompting)
```python
ROUTER_PROMPT = """Klasifikasikan pertanyaan berikut ke salah satu domain dalam format JSON PERSIS:
{{"domain": "knowledge"}} — untuk pertanyaan informasi umum/dokumen (FAQ, SOP, kebijakan)
{{"domain": "erp"}} — untuk pertanyaan data transaksional (stok, harga, order, laporan penjualan)

Pertanyaan: {query}
JSON:"""

def route_query(query: str, qwen_llm_call) -> str:
    raw = qwen_llm_call(ROUTER_PROMPT.format(query=query))
    parsed = extract_json(raw)  # fungsi dari Sesi 4
    if parsed and parsed.get("domain") in ("knowledge", "erp"):
        return parsed["domain"]
    # fallback rule-based kalau parsing gagal
    erp_keywords = ["stok", "order", "beli", "harga", "pesan", "laporan penjualan"]
    return "erp" if any(kw in query.lower() for kw in erp_keywords) else "knowledge"

@app.post("/agent/orchestrate")
def orchestrate(query: str):
    domain = route_query(query, qwen_llm_call)
    if domain == "erp":
        return {"domain": "erp", "answer": erp_react_loop(query)}
    return {"domain": "knowledge", "answer": react_loop(query)}
```

### Checklist Finalisasi
- [ ] `docker-compose.yml` menjalankan: FastAPI Knowledge Agent, FastAPI ERP, dan server `llama.cpp` untuk Qwen (satu server model bisa dipakai bersama oleh kedua service).
- [ ] Volume mount untuk file `.duckdb` agar data persisten antar restart.
- [ ] Endpoint `/health` di tiap service.
- [ ] Dashboard frontend sederhana (mirip `frontend/index.html` pada repo referensi) untuk uji coba manual kedua agent.
- [ ] README lengkap: cara run, arsitektur, contoh query.
- [ ] Tabel evaluasi: 10 skenario query campuran (knowledge + ERP), catat domain routing benar/salah, pola prompting dipakai (ReAct vs structured), waktu respons.

### Deliverable Akhir
1. Repo terstruktur (`backend/knowledge_agent`, `backend/knowledge_erp`, `frontend/`, `docker-compose.yml`).
2. Orchestrator agent yang bisa menjawab kombinasi pertanyaan (misal: "Apa itu produk X?" → knowledge; "Stok produk X berapa?" → ERP) — seluruhnya berjalan dengan satu model Qwen lokal, tanpa dependensi ke LLM cloud.
3. Laporan evaluasi singkat (markdown) merangkum akurasi routing dan perbandingan pola ReAct vs structured prompting.

---

## Ringkasan Struktur Folder yang Disarankan
```
project/
├── backend/
│   ├── knowledge_agent/
│   │   ├── main.py            # Sesi 2
│   │   ├── ingest.py          # Sesi 1
│   │   ├── react_agent.py     # Sesi 3
│   │   └── planner_agent.py   # Sesi 4
│   └── knowledge_erp/
│       ├── main.py            # Sesi 5
│       ├── react_agent.py     # Sesi 6
│       └── report.py          # Sesi 7
├── frontend/
│   └── index.html             # dashboard uji manual
├── orchestrator/
│   └── main.py                # Sesi 8
├── models/                    # file GGUF Qwen
├── docker-compose.yml
└── README.md
```

---

# LAMPIRAN A — Implementasi Produksi Riil (Folder per-Sesi)

Untuk melengkapi notebook, setiap sesi (mulai Sesi 2) sekarang punya **folder kode standalone production-ready**
dengan pola struktur **identik** (mirip `Sesi_2/` yang sudah ada), diadaptasi dari pola
[End-to-End-LLM-Serving](https://github.com/Muhammad-Ikhwan-Fathulloh/End-to-End-LLM-Serving).

## Konsistensi Struktur tiap Folder Sesi
```
Sesi_<Nama>/
├── app/
│   ├── __init__.py       (kosong)
│   ├── config.py         pydantic-settings → baca .env + default masuk akal
│   ├── schemas.py        Pydantic BaseModel request/response
│   ├── database.py       (jika perlu) DuckDB connection, schema, seed data, business logic
│   ├── llm.py            (jika pakai LLM) lifespan: llama-server lifecycle + llm_complete wrapper
│   ├── tools.py / react.py / planner.py / generators.py / router.py / dispatch.py   (logic bisnis spesifik sesi)
│   └── main.py           FastAPI entrypoint: CORS, /health, endpoint bisnis
├── tests/
│   └── test_*.py         Unit test yang TIDAK bergantung LLM nyala (parser, summary, fallback)
├── .env                  default port, duckdb path, llama config, dependency URL
├── .gitignore            .venv, .duckdb, .log, __pycache__
├── requirements.txt      fastapi + uvicorn + pydantic + duckdb + sentence-transformers + httpx + pytest
├── run.bat               Auto venv → install → spawn dependency service → uvicorn app.main:app
└── README.md             Ringkasan, fitur, cara run, daftar endpoint, struktur file, uji manual
```

## Daftar Folder Implementasi + Port + Mapping End-to-End LLM Serving

| Sesi | Folder Implementasi | Port App | Port LLM | Pola yang Diadopsi dari E2E LLM Serving |
|---|---|---|---|---|
| 2 | `Sesi_2/` (sebelumnya sudah ada) | **8001** | - | REST API + Pydantic Validator (pola dasar semua service) |
| 3 | `Sesi_3_Knowledge_Agent_ReAct/` | **8002** | 8080 | **P1 Basic LLM**: `lifespan` start/stop llama-server, health check, `/completion` wrapper |
| 4 | `Sesi_4_Knowledge_Agent_Planner/` | **8003** | 8081 | Pola `P1 + Structured JSON Prompting` + retry mechanism |
| 5 | `Sesi_5_Knowledge_ERP_CRUD/` | **8005** | - | DuckDB embedded schema + validasi stok (business logic di layer database.py) |
| 6 | `Sesi_6_Knowledge_ERP_ReAct/` | **8006** | 8082 | Tool Registry HTTP Client (mirip cara P3/P4 panggil internal API) |
| 7 | `Sesi_7_Knowledge_ERP_Generate/` | **8007** | 8083 | Prompt Engineering laporan naratif (P1 pola generation + template prompt ketat) |
| 8 | `Sesi_8_Orchestrator/` | **8000** | 8088 | **P3 Semantic Cache** (DuckDB VSS menggantikan pgvector) + **P4 Feedback Loop** (interactions table + like/dislike) + Router LLM + Dispatch Agent |

## Cara Menjalankan Full Stack (End to End)

**Cukup 1 perintah**:
```cmd
cd Sesi_8_Orchestrator
run.bat
```

Yang dijalankan script secara otomatis:
1. `Sesi_2 (8001)` — Knowledge CRUD + vector search
2. `Sesi_5 (8005)` — ERP CRUD + validasi stok
3. `Sesi_7 (8007)` — Narrative Report Generator via Qwen
4. `Sesi_8 (8000)` — Orchestrator utama (user pakai ini): Router → Cache → Dispatch → Feedback

Swagger UI endpoint utama: **`http://localhost:8000/docs`**
- `POST /agent/orchestrate` — kirim query, dapat jawaban end-to-end.
- `POST /agent/feedback` — `{interaction_id, is_like: true/false}`
- `GET /agent/stats` — total interaksi, likes, cache entries.

---

# LAMPIRAN B — Checklist Evaluasi Kualitas (Rubrik Penilaian)

| Komponen | Bobot | 1 (Kurang) | 3 (Cukup) | 5 (Sangat Baik) |
|---|---|---|---|---|
| **Domain Routing Accuracy** (10 skenario) | 25% | < 6/10 benar | 7–8/10 benar | 9–10/10 benar (fallback rule tetap akurat walau LLM gagal) |
| **Semantic Cache Hit Rate** | 10% | < 10% | 30–50% | > 50% untuk FAQ / query berulang |
| **ReAct Step Efficiency** | 15% | > 5 langkah / gagal FINISH | 3–4 langkah | ≤ 2 langkah untuk task sederhana |
| **Planner JSON Validity** | 10% | Sering gagal parse | Retry 1x lolos | Selalu valid tanpa retry |
| **ERP Create Order Guardrail** | 15% | Langsung eksekusi tanpa confirm | Konfirmasi tapi tidak log | Human-in-the-loop + log audit jelas |
| **Narrative Report Quality** | 15% | Hanya ulang angka | 3 paragraf bagus | 4 paragraf + rekomendasi actionable + bahasa formal |
| **Code Structure (app/config/tests)** | 10% | Semua logic di main.py | 2–3 modul terpisah | ≥ 5 modul: config/schemas/db/tools/router/dispatch, tests lulus pytest |
