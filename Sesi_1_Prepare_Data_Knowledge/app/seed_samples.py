"""
CLI ingest: python -m app.seed_samples   (jika tidak mau jalankan FastAPI)
Tidak dieksekusi jika pakai uvicorn main:app - seed otomatis di lifespan main.py.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, insert_chunks, chunk_text, count


SEED = [
    ("FAQ_Produk_NocBook",
     "Pertanyaan: Apa garansi NocBook Pro 14?\n"
     "Jawaban: Garansi resmi 2 tahun pabrik, termasuk servis komponen dan pergantian battery jika capacity di bawah 80% dalam 12 bulan pertama."),
]

if __name__ == "__main__":
    init_db()
    for src, text in SEED:
        ids = insert_chunks(src, chunk_text(text))
        print(f"[seed] {src}: {len(ids)} chunks tersimpan")
    print(f"Total dokumen di knowledge.duckdb: {count()}")
