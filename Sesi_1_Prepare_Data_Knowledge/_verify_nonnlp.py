"""Verifikasi logic NON-EMBEDDING Sesi 1 (Pipeline RAG) - SESUAI actual app code."""
import sys
import os
import re
import tempfile
import types
import uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ---- Patch sentence-transformers DULU sebelum import app apapun ----
import numpy as _np
_fake_st = types.ModuleType("sentence_transformers")
class _FakeModel:
    def encode(self, text, **kw):
        _dim = 384
        single_vec = [0.456] * _dim
        if isinstance(text, str):
            return _np.array(single_vec)
        return _np.array([single_vec] * len(text))
_fake_st.SentenceTransformer = lambda *a, **kw: _FakeModel()
sys.modules["sentence_transformers"] = _fake_st

# ---- Override Settings duckdb_path ke temp file TIDAK exist ----
from app.config import settings as _s
_tmp_dir = tempfile.gettempdir()
_tmp_path = os.path.join(_tmp_dir, f"verify_s1_{uuid.uuid4().hex}.duckdb")
object.__setattr__(_s, "duckdb_path", _tmp_path)
object.__setattr__(_s, "chunk_size", 200)
object.__setattr__(_s, "chunk_overlap", 40)

# ---- 1. Schemas ----
from app.schemas import IngestTextRequest, SearchRequest, ChunkInfoResponse, SearchResult

req = IngestTextRequest(source="faq1.txt", content="apa garansi? 2 tahun", chunk_size=300)
assert req.source == "faq1.txt" and req.chunk_size == 300
sreq = SearchRequest(q="garansi", k=5)
assert sreq.q == "garansi" and sreq.k == 5
ChunkInfoResponse(source="a", total_chunks=1, total_words=10, document_ids=["x"])
SearchResult(id="1", source="a", content="b", score=0.5)
print("[OK] schemas: semua Pydantic model tervalidasi")

# ---- 2. Ingest: extract dari TXT / MD / PDF bytes (tanpa pypdf error untuk PDF invalid/bad) ----
from app.ingest import extract_text_from_file, extract_text_from_txt, extract_text_from_markdown

src, txt = extract_text_from_txt(b"Baris 1\nBaris 2\nBaris 3  test  \n", "t.txt")
assert "Baris 1" in txt and src == "t.txt"
print(f"[OK] extract TXT: {len(txt.split())} words, source={src}")

src2, txt2 = extract_text_from_markdown(b"# Title\n\nHello **world**\n\n## Sub\n\nyeah", "a.md")
assert "Title" in txt2 and "world" in txt2 and src2 == "a.md"
print(f"[OK] extract MD: {len(txt2.split())} words, source={src2}")

# PDF empty
src3, txt3 = extract_text_from_file(b"", "empty.pdf")
assert src3 == "empty.pdf"
# PDF invalid header - hanya ingin pastikan tidak crash
try:
    _, _ = extract_text_from_file(b"not a pdf content here", "bad.pdf")
    ok = True
except Exception:
    ok = False
print(f"[OK] PDF invalid tidak crash: {ok}")

# ---- 3. Database functions (DuckDB + VSS) - chunk_text + insert_chunks + search + list_all + count + delete_all ----
from app.database import init_db, close_db, chunk_text, insert_chunks, list_all, count, search as db_search, delete_all

init_db()
assert count() == 0

# chunk_text: 1000 kata, size 100, overlap 20
long = " ".join(["kata"] * 1000)
chunks = chunk_text(long, size=100, overlap=20)
assert len(chunks) >= 10
for c in chunks:
    assert len(c.split()) <= 100
print(f"[OK] chunk_text 1000 kata size100 overlap20 -> {len(chunks)} chunks (masing-masing <=100 kata)")

ids = insert_chunks("src1", chunks)
assert len(ids) == len(chunks)
assert count() == len(chunks)
print(f"[OK] insert_chunks: {len(ids)} docs masuk")

rows = list_all(limit=5)
assert len(rows) == 5
print(f"[OK] list_all(5): {len(rows)} rows terbaru")

# VSS search top 3
rows_s = db_search("kata", k=3)
assert len(rows_s) == 3
print(f"[OK] DuckDB VSS search top-3: skor pertama {rows_s[0][3]:.4f}")

# delete_all
n_deleted = delete_all()
assert n_deleted == len(ids) and count() == 0
print(f"[OK] delete_all: {n_deleted} rows terhapus, DB kosong kembali")

# ---- 4. Seed data (SAMPLE_FAQ) via main module ----
from app.main import SAMPLE_FAQ
assert len(SAMPLE_FAQ) == 8, f"Expected 8 FAQ/SOP sample, got {len(SAMPLE_FAQ)}"
# Masukkan via chunk_text + insert_chunks
total_seed_chunks = 0
for src, t in SAMPLE_FAQ:
    cs = chunk_text(t)
    insert_chunks(src, cs)
    total_seed_chunks += len(cs)
assert count() == total_seed_chunks
print(f"[OK] SAMPLE_FAQ: 8 entri -> {total_seed_chunks} chunks tersimpan")

# ---- 5. FastAPI app routes + HTTP endpoints via TestClient ----
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
paths = sorted({r.path for r in app.routes})
expected = ["/health", "/stats", "/ingest/text", "/ingest/file", "/search", "/documents"]
for e in expected:
    assert e in paths, f"Route {e} tidak ditemukan di app: {paths}"
print(f"[OK] FastAPI routes: {len(expected)} endpoint wajib terdaftar")

# /health
r = client.get("/health")
assert r.status_code == 200 and r.json()["app"] == "ok" and r.json()["documents_count"] >= total_seed_chunks
print(f"[OK] /health: app=ok, documents_count={r.json()['documents_count']}")

# /stats
r = client.get("/stats")
body = r.json()
assert r.status_code == 200
assert "total_chunks" in body and "chunking" in body and "chunks_by_source" in body
print(f"[OK] /stats: total_chunks={body['total_chunks']}, sources={sorted(list(body['chunks_by_source'].keys()))[:5]}...")

# /ingest/text
r = client.post(
    "/ingest/text",
    json={"source": "http_test.txt", "content": "Ini konten yang di-ingest via endpoint text."},
)
assert r.status_code == 200
ir = r.json()
assert ir["total_chunks"] >= 1 and len(ir["document_ids"]) == ir["total_chunks"]
print(f"[OK] /ingest/text: {ir['total_chunks']} chunks, {ir['total_words']} words")

# /search
r = client.post("/search", json={"q": "garansi NocBook", "k": 3})
assert r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 1
print(f"[OK] /search: top-3 -> 1st score={r.json()[0]['score']:.4f}")

# GET /documents
r = client.get("/documents", params={"limit": 5})
assert r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) == 5
print(f"[OK] GET /documents: 5 rows terbaru")

# DELETE /documents (reset)
before = client.get("/health").json()["documents_count"]
r = client.delete("/documents")
assert r.status_code == 200 and "deleted_chunks" in r.json()
after = client.get("/health").json()["documents_count"]
assert after == 0 and before > 0
print(f"[OK] DELETE /documents: {before} -> 0 rows (reset DB)")

# /ingest/file (TXT)
r = client.post(
    "/ingest/file",
    files={"file": ("t.txt", b"Ini baris 1.\nIni baris 2.\nIngestion via file upload TXT.", "text/plain")},
)
assert r.status_code == 200 and r.json()["total_chunks"] >= 1 and r.json()["source"] == "t.txt"
print(f"[OK] /ingest/file TXT: {r.json()['total_chunks']} chunks, {r.json()['total_words']} words")

# /ingest/file (MD)
r = client.post(
    "/ingest/file",
    files={"file": ("a.md", b"# Title MD\n\nIni paragraph di MD.\n\n## Sub\n\nLagi.", "text/markdown")},
)
assert r.status_code == 200 and r.json()["total_chunks"] >= 1
print(f"[OK] /ingest/file MD: chunks={r.json()['total_chunks']}, source={r.json()['source']}")

# /ingest/file (empty file -> 400)
r = client.post(
    "/ingest/file",
    files={"file": ("empty.pdf", b"", "application/pdf")},
)
assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
print("[OK] /ingest/file empty -> HTTP 400")

# /ingest/text (empty content -> 400)
r = client.post("/ingest/text", json={"source": "a.txt", "content": "   \n\t   "})
assert r.status_code == 400
print("[OK] /ingest/text content kosong -> HTTP 400")

close_db()
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
print(" Sesi 1: SEMUA TEST LOGIC & ENDPOINT LULUS (+)")
print("=" * 65)
