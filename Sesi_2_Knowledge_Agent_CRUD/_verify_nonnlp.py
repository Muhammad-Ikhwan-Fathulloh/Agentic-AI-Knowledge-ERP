"""Verifikasi logic NON-EMBEDDING Sesi 2 - tidak butuh download embedding model."""
import sys
import os
import tempfile
import uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Override settings SEBELUM import apapun dari app.
from app.config import settings as _s

# JANGAN create file temp (DuckDB complain). Generate path TIDAK exist, biar DuckDB yg create.
_tmp_dir = tempfile.gettempdir()
_tmp_path = os.path.join(_tmp_dir, f"verify_s2_{uuid.uuid4().hex}.duckdb")
_s.duckdb_path = _tmp_path
_s.embed_dim = 384

# Override encode DENGAN CARA import embeddings module lebih dulu (sebelum database).
import app.embeddings as _emb_mod

_fake_vec = [0.123] * _s.embed_dim
_emb_mod.encode = lambda text: _fake_vec

# --- 1. chunk_text + SEED_DATA size ---
from app.database import chunk_text, SEED_DATA

text = " ".join(["word"] * 1000)
chunks = chunk_text(text, size=100, overlap=20)
assert len(chunks) >= 10, f"chunk count: {len(chunks)}"
for c in chunks:
    assert len(c.split()) <= 100
print("[OK] chunk_text: word-based chunking works correctly")
print(f"[INFO] SEED_DATA: {len(SEED_DATA)} entri FAQ + SOP siap disisipkan")

# --- 2. pdf_ingest graceful error handling ---
from app.pdf_ingest import extract_chunks_from_pdf

assert extract_chunks_from_pdf(b"") == []
assert extract_chunks_from_pdf(b"not a real pdf") == []
print("[OK] pdf_ingest: empty/invalid input returns [] gracefully")

# --- 3. Pydantic schemas ---
from app.schemas import DocIn, DocOut, DocSearchResult

doc = DocIn(source="test.txt", content="hello world")
assert doc.source == "test.txt" and doc.content == "hello world"
assert DocOut(source="x", content="y", id="123").id == "123"
assert DocSearchResult(source="x", content="y", id="1", score=0.5).score == 0.5
print("[OK] schemas: Pydantic models validate correctly")

# --- 4. config ---
from app.config import settings

assert settings.app_port == 8001
assert settings.embed_dim == 384
print(f"[OK] config: app_port={settings.app_port}, embed_dim={settings.embed_dim}")

# --- 5. Database import: encode sudah di-override, store module-level sekarang pakai vec fake.
from app.database import store as s2_store, DocStore

assert s2_store.count() == 0, f"fresh DB seharusnya 0, tapi {s2_store.count()}"

# --- 6. CRUD ---
did = s2_store.insert("t1", "content test")
assert s2_store.count() == 1
row = s2_store.get(did)
assert row[1] == "t1" and row[2] == "content test"
rows = s2_store.list()
assert len(rows) == 1
s2_store.update(did, "t1_v2", "updated content")
row2 = s2_store.get(did)
assert row2[1] == "t1_v2" and row2[2] == "updated content"
s2_store.delete(did)
assert s2_store.count() == 0
print("[OK] DocStore CRUD: insert/get/list/update/delete + count works")

# --- 7. insert_chunks ---
chunks_2 = chunk_text(" ".join(["kata"] * 1500), size=300, overlap=60)
ids = s2_store.insert_chunks("srcA", chunks_2)
assert len(ids) >= 5
print(f"[OK] insert_chunks: {len(chunks_2)} chunks -> {len(ids)} docs tersimpan")

# --- 8. seed_if_empty (NOT empty karena ada srcA chunks -> return 0) ---
before = s2_store.count()
seeded_now = s2_store.seed_if_empty()
assert seeded_now == 0 and s2_store.count() == before
print("[OK] seed_if_empty: tidak double-insert saat DB sudah ada isi")

# --- 9. VSS semantic search ---
k = 3
rows = s2_store.search("cari kata", k=k)
assert len(rows) == k
print(f"[OK] DuckDB VSS search top-{k}: skor pertama {rows[0][3]:.4f}")

# --- 10. FastAPI app import + route listing ---
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
paths = sorted({r.path for r in app.routes})
expected = [
    "/health",
    "/stats",
    "/documents",
    "/documents/search",
    "/documents/{doc_id}",
    "/documents/bulk",
    "/documents/upload-pdf",
    "/documents/ingest-text",
]
for e in expected:
    assert e in paths, f"Endpoint {e} TIDAK DITEMUKAN di app.routes"
print(f"[OK] FastAPI routes: {len(expected)} endpoint wajib terdaftar ✓")

# --- 11. /health tanpa start server ---
r = client.get("/health")
assert r.status_code == 200
body = r.json()
assert body["app"] == "ok"
assert body["documents_count"] >= len(ids)
print(f"[OK] /health -> count={body['documents_count']}, embed={body['embed_model']}")

# --- 12. /stats ---
r = client.get("/stats")
assert r.status_code == 200
assert "documents_by_source" in r.json()
print(f"[OK] /stats -> by_source: {list(r.json()['documents_by_source'].keys())}")

# --- 13. CRUD via HTTP ---
r = client.post(
    "/documents",
    json={"source": "http_test.txt", "content": "tes via HTTP endpoint"},
)
assert r.status_code == 200
http_id = r.json()["id"]
r2 = client.get(f"/documents/{http_id}")
assert r2.status_code == 200 and r2.json()["source"] == "http_test.txt"
r3 = client.get("/documents/search", params={"q": "HTTP", "k": 3})
assert r3.status_code == 200 and isinstance(r3.json(), list)
r4 = client.put(
    f"/documents/{http_id}",
    json={"source": "http_v2.txt", "content": "diupdate via PUT"},
)
assert r4.status_code == 200 and r4.json()["source"] == "http_v2.txt"
r5 = client.delete(f"/documents/{http_id}")
assert r5.status_code == 200
r6 = client.get(f"/documents/{http_id}")
assert r6.status_code == 404
print("[OK] CRUD via HTTP: POST / GET / search / PUT / DELETE (incl 404 check) ✓")

# --- 14. bulk + ingest-text via HTTP ---
rb = client.post(
    "/documents/bulk",
    json=[
        {"source": "bulk1.txt", "content": "b1"},
        {"source": "bulk2.txt", "content": "b2"},
    ],
)
assert rb.status_code == 200 and rb.json()["inserted"] == 2
longc = " ".join(["word"] * 1000)
ri = client.post(
    "/documents/ingest-text",
    params={"chunk_size": 200, "chunk_overlap": 40},
    json={"source": "long_text.txt", "content": longc},
)
assert ri.status_code == 200 and ri.json()["total_chunks"] >= 5
print(f"[OK] bulk={rb.json()['inserted']} docs, ingest-text={ri.json()['total_chunks']} chunks ✓")

# --- 15. upload-pdf: non-PDF rejected, empty PDF -> 422 ---
rnf = client.post(
    "/documents/upload-pdf",
    files={"file": ("a.txt", b"teks", "text/plain")},
)
assert rnf.status_code == 400
remp = client.post(
    "/documents/upload-pdf",
    files={"file": ("blank.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
)
assert remp.status_code == 422
print("[OK] upload-pdf validation: non-PDF 400 / PDF kosong 422 ✓")

try:
    s2_store.con.close()
except Exception:
    pass
try:
    os.unlink(_tmp_path)
    for ext in [".wal", ".tmp"]:
        p = _tmp_path + ext
        if os.path.exists(p):
            os.unlink(p)
except OSError:
    pass

print()
print("=" * 65)
print(" Sesi 2: SEMUA 15 TEST LOGIC LULUS ✓")
print("=" * 65)
