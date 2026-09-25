"""
app/database.py - Knowledge base lokal Sesi 3.
Disalin dan disesuaikan dari Sesi 2 agar Sesi 3 dapat berjalan mandiri
tanpa harus menjalankan service Sesi 2 (port 8001) secara terpisah.

Data seed mencakup seluruh SEED_DATA dari Sesi 2:
FAQ produk (NocBook, NocMouse), pengiriman, pembayaran, refund,
SOP klaim garansi, SOP return, dan artikel teknis RAM DDR4.
"""
import duckdb
import uuid
from app.config import settings
from app.embeddings import encode

# ---------------------------------------------------------------------------
# Seed data - identik dengan Sesi 2 agar knowledge base konsisten
# ---------------------------------------------------------------------------
SEED_DATA = [
    ("FAQ_Produk_NocBook",
     "Pertanyaan: Apa garansi NocBook Pro 14?\n"
     "Jawaban: Garansi resmi 2 tahun pabrik, termasuk servis komponen dan pergantian battery "
     "jika capacity di bawah 80% dalam 12 bulan pertama."),
    ("FAQ_Produk_NocMouse",
     "Pertanyaan: Apakah NocMouse X1 tahan air?\n"
     "Jawaban: NocMouse X1 memiliki sertifikasi IP54 (tahan percikan air dan debu ringan), "
     "tidak untuk direndam."),
    ("FAQ_Shipping",
     "Pertanyaan: Berapa lama pengiriman ke luar Jawa?\n"
     "Jawaban: Estimasi 3-5 hari kerja untuk Sumatera, 5-7 hari kerja untuk Sulawesi, Maluku, Papua. "
     "Beban ongkir dihitung otomatis di checkout."),
    ("FAQ_Pembayaran",
     "Pertanyaan: Metode pembayaran apa yang didukung?\n"
     "Jawaban: Transfer bank (BCA, BNI, Mandiri, BRI), virtual account, e-wallet "
     "(GoPay, OVO, ShopeePay), dan kartu kredit melalui Midtrans / Xendit."),
    ("FAQ_Refund",
     "Pertanyaan: Bagaimana prosedur refund?\n"
     "Jawaban: Refund dapat diajukan dalam 30 hari setelah barang diterima, dengan syarat barang "
     "dalam kondisi segel asli, belum teraktivasi, dan disertai foto unboxing lengkap. "
     "Proses refund 5-7 hari kerja setelah approval."),
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
     "RAM DDR4 16GB NocMem memiliki clock 3200MHz, CL16 latency, dan tegangan operasi 1.2V. "
     "Kompatibel dengan prosesor Intel 10th/11th gen dan AMD Ryzen 3000/4000/5000 series. "
     "Tidak cocok untuk laptop DDR5. Lifetime warranty."),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def init_duckdb():
    con = duckdb.connect(settings.duckdb_path)
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS documents (
        id      VARCHAR PRIMARY KEY,
        source  VARCHAR,
        content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    return con


def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """Memecah teks panjang menjadi potongan dengan overlap."""
    words = text.split()
    chunks: list[str] = []
    step = max(size - overlap, 1)
    for i in range(0, max(len(words), 1), step):
        chunk_words = words[i: i + size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
    return chunks


# ---------------------------------------------------------------------------
# DocStore - interface tunggal ke DuckDB
# ---------------------------------------------------------------------------
class DocStore:
    def __init__(self):
        self.con = init_duckdb()

    # --- tulis ---
    def insert(self, source: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        emb = encode(content)
        self.con.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
            [doc_id, source, content, emb],
        )
        return doc_id

    def insert_chunks(self, source: str, chunks: list[str]) -> list[str]:
        return [self.insert(source, c) for c in chunks if c.strip()]

    def update(self, doc_id: str, source: str, content: str):
        emb = encode(content)
        self.con.execute(
            "UPDATE documents SET content=?, source=?, embedding=? WHERE id=?",
            [content, source, emb, doc_id],
        )

    def delete(self, doc_id: str):
        self.con.execute("DELETE FROM documents WHERE id=?", [doc_id])

    # --- baca ---
    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def get(self, doc_id: str):
        return self.con.execute(
            "SELECT id, source, content FROM documents WHERE id=?", [doc_id]
        ).fetchone()

    def list(self, limit: int = 20, offset: int = 0):
        return self.con.execute(
            "SELECT id, source, content FROM documents "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [limit, offset],
        ).fetchall()

    def search(self, query: str, k: int = 5):
        q_emb = encode(query)
        return self.con.execute(f"""
            SELECT id, source, content,
                   array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
            FROM documents
            ORDER BY dist ASC
            LIMIT ?
        """, [q_emb, k]).fetchall()

    # --- seed ---
    def seed_if_empty(self) -> int:
        if self.count() > 0:
            return 0
        total = 0
        for src, text in SEED_DATA:
            total += len(self.insert_chunks(src, chunk_text(text)))
        return total


store = DocStore()
