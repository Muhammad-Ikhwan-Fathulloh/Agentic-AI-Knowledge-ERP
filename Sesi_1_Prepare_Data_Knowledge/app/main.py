"""
Sesi 1 - Prepare Data Knowledge & Create Vector DB (Port 8000 untuk Sesi 1 standalone,
namun bila ingin pakai Sesi 2 sebagai knowledge API, gunakan port 8001 milik Sesi 2).
Sesi ini fokus ke pipeline: Load → Clean → Chunk → Embed → Store.

Cara run:
    cd Sesi_1_Prepare_Data_Knowledge
    run.bat
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import (
    init_db, close_db, search as db_search, insert_document, insert_chunks,
    chunk_text, count, list_all, delete_all,
)
from app.ingest import extract_text_from_file
from app.schemas import (
    IngestTextRequest, SearchRequest, ChunkInfoResponse, SearchResult,
)

SAMPLE_FAQ = [
    ("FAQ_Produk_NocBook",
     "Pertanyaan: Apa garansi NocBook Pro 14?\n"
     "Jawaban: Garansi resmi 2 tahun pabrik, termasuk servis komponen dan pergantian battery jika capacity di bawah 80% dalam 12 bulan pertama."),
    ("FAQ_Produk_NocMouse",
     "Pertanyaan: Apakah NocMouse X1 tahan air?\n"
     "Jawaban: NocMouse X1 memiliki sertifikasi IP54 (tahan percikan air dan debu ringan), tidak untuk direndam."),
    ("FAQ_Shipping",
     "Pertanyaan: Berapa lama pengiriman ke luar Jawa?\n"
     "Jawaban: Estimasi 3-5 hari kerja untuk Sumatera, 5-7 hari kerja untuk Sulawesi, Maluku, Papua. Beban ongkir dihitung otomatis di checkout."),
    ("FAQ_Pembayaran",
     "Pertanyaan: Metode pembayaran apa yang didukung?\n"
     "Jawaban: Transfer bank (BCA, BNI, Mandiri, BRI), virtual account, e-wallet (GoPay, OVO, ShopeePay), dan kartu kredit melalui Midtrans / Xendit."),
    ("FAQ_Refund",
     "Pertanyaan: Bagaimana prosedur refund?\n"
     "Jawaban: Refund dapat diajukan dalam 30 hari setelah barang diterima, dengan syarat barang dalam kondisi segel asli, belum teraktivasi, dan disertai foto unboxing lengkap. Proses refund 5-7 hari kerja setelah approval."),
    ("SOP_Claim_Garansi",
     "SOP Klaim Garansi NocBook:\n"
     "1. Hubungi customer service via WhatsApp +62-811-0000-123 dengan melampirkan foto serial number.\n"
     "2. CS akan memberikan nomor tiket klaim dan alamat service center terdekat.\n"
     "3. Kirim unit via ekspedisi yang ditunjuk (biaya tanggung sendiri jika di luar masa DOA 7 hari).\n"
     "4. Estimasi perbaikan 5-14 hari kerja, unit baru akan dikirim jika tidak dapat diperbaiki."),
    ("SOP_Pengembalian_Barang",
     "SOP Pengembalian Barang (Return):\n"
     "1. Ajukan return melalui dashboard pesanan maksimal 30 hari setelah terima barang.\n"
     "2. Upload foto unboxing, video keluhan, dan alasan return.\n"
     "3. Tim Quality Assurance akan memproses dalam 2x24 jam (approve / reject).\n"
     "4. Jika approve, kirim barang kembali ke gudang (resi diunggah ke dashboard).\n"
     "5. Barang diterima gudang → dana refund cair dalam 5-7 hari kerja."),
    ("Artikel_Teknologi_RAM_DDR4",
     "RAM DDR4 16GB NocMem memiliki clock 3200MHz, CL16 latency, dan tegangan operasi 1.2V. Kompatibel dengan prosesor Intel 10th/11th gen dan AMD Ryzen 3000/4000/5000 series. Tidak cocok untuk laptop DDR5. Lifetime warranty."),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[S1] DuckDB siap: {settings.duckdb_path}")
    if count() == 0:
        print("[S1] Mengisi seed data FAQ + SOP contoh ...")
        for src, text in SAMPLE_FAQ:
            chunks = chunk_text(text)
            insert_chunks(src, chunks)
        print(f"[S1] Seed selesai. Total dokumen: {count()}")
    yield
    close_db()


app = FastAPI(
    title="Sesi 1 - Prepare Data Knowledge & Vector DB",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "app": "ok",
        "duckdb": settings.duckdb_path,
        "documents_count": count(),
        "embed_model": settings.embed_model,
        "embed_dim": settings.embed_dim,
    }


@app.get("/stats")
async def stats():
    rows = list_all(limit=1000)
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r[1]] = by_source.get(r[1], 0) + 1
    return {
        "total_chunks": count(),
        "chunking": {"size": settings.chunk_size, "overlap": settings.chunk_overlap},
        "chunks_by_source": by_source,
    }


@app.post("/ingest/text", response_model=ChunkInfoResponse)
async def ingest_text(req: IngestTextRequest):
    if not req.content.strip():
        raise HTTPException(400, "content kosong")
    chunks = chunk_text(
        req.content,
        size=req.chunk_size or settings.chunk_size,
        overlap=req.chunk_overlap or settings.chunk_overlap,
    )
    if not chunks:
        raise HTTPException(400, "tidak ada chunk yang bisa disimpan")
    ids = insert_chunks(req.source, chunks)
    return ChunkInfoResponse(
        source=req.source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/ingest/file", response_model=ChunkInfoResponse)
async def ingest_file(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "file kosong")
    source, text = extract_text_from_file(raw, file.filename or "unknown")
    if not text:
        raise HTTPException(400, "tidak bisa ekstrak teks dari file")
    chunks = chunk_text(text)
    ids = insert_chunks(source, chunks)
    return ChunkInfoResponse(
        source=source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/search", response_model=list[SearchResult])
async def search(req: SearchRequest):
    rows = db_search(req.q, req.k)
    return [
        {"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
        for r in rows
    ]


@app.get("/documents")
async def list_documents(limit: int = 100):
    rows = list_all(limit)
    return [
        {"id": r[0], "source": r[1], "content": r[2]}
        for r in rows
    ]


@app.delete("/documents")
async def reset_documents():
    deleted = delete_all()
    return {"status": "reset_done", "deleted_chunks": deleted}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
