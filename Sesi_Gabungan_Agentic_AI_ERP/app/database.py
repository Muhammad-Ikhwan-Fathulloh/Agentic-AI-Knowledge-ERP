import uuid
from datetime import datetime, timedelta

import duckdb

from app.config import settings
from app.embeddings import encode

_state_con = {"con": None}


def get_con():
    if _state_con["con"] is None:
        _state_con["con"] = duckdb.connect(settings.duckdb_path)
    return _state_con["con"]


def close_db():
    if _state_con["con"] is not None:
        _state_con["con"].close()
        _state_con["con"] = None


def init_db():
    con = get_con()
    con.execute("INSTALL vss; LOAD vss;")

    # =====================================================================
    # KNOWLEDGE BASE #1 : SOP (Standar Operasional Prosedur)
    #    -> Panduan langkah demi langkah, aturan bisnis, FAQ prosedural.
    #       Agentic AI membaca SOP ini TERLEBIH DAHULU untuk memutuskan
    #       action ERP apa yang perlu dijalankan.
    # =====================================================================
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS sop_documents (
        id VARCHAR PRIMARY KEY,
        source VARCHAR,
        content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    # =====================================================================
    # KNOWLEDGE BASE #2 : ERP (Pengetahuan tentang data & master ERP)
    #    -> Spesifikasi produk, katalog, deskripsi item, informasi pendukung
    #       yang diluar tabel transaksi ERP (products/customers/orders).
    # =====================================================================
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS erp_documents (
        id VARCHAR PRIMARY KEY,
        source VARCHAR,
        content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    # =====================================================================
    # ERP TRANSACTIONAL TABLES (Sesi 5)
    # =====================================================================
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS products (
        id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL,
        price DOUBLE NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id VARCHAR PRIMARY KEY, 
        name VARCHAR NOT NULL,
        email VARCHAR, phone VARCHAR,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    con.execute(f"""
    CREATE TABLE IF NOT EXISTS chat_customers (
        id VARCHAR PRIMARY KEY, 
        customer_id VARCHAR REFERENCES customers(id),
        chat_history TEXT,
        embedding FLOAT[{settings.embed_dim}],
        last_chat_time TIMESTAMP DEFAULT current_timestamp,
        last_chat_message VARCHAR,
        last_chat_response VARCHAR,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id VARCHAR PRIMARY KEY, customer_id VARCHAR,
        status VARCHAR DEFAULT 'pending', total_amount DOUBLE DEFAULT 0,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id VARCHAR PRIMARY KEY, order_id VARCHAR, product_id VARCHAR,
        qty INTEGER, price DOUBLE, subtotal DOUBLE
    );
    """)

    # =====================================================================
    # CHAT CONVERSATION MEMORY (ChatGPT-style session + messages)
    #   -> Lebih scalable daripada chat_customers kolom tunggal.
    #      chat_customers (tabel user) DIpertahankan untuk backward compat.
    # =====================================================================
    con.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id VARCHAR PRIMARY KEY,
        title VARCHAR NOT NULL,
        customer_id VARCHAR,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id VARCHAR PRIMARY KEY,
        session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
        role VARCHAR NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        agentic_steps TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)

    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON chat_messages(session_id);")
    except Exception:
        pass

    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_sop_emb ON sop_documents USING HNSW (embedding);")
    except Exception:
        pass
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_erpdoc_emb ON erp_documents USING HNSW (embedding);")
    except Exception:
        pass
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_prod_emb ON products USING HNSW (embedding);")
    except Exception:
        pass

    _seed_sop(con)
    _seed_erp_docs(con)
    _seed_erp(con)

    return con


# ========================================================================
# SEED : SOP Knowledge (KB #1)
# ========================================================================
SOP_SEED = [
    ("SOP_Klaim_Garansi",
     "SOP KLAIM GARANSI (semua produk NocStore):\n"
     "JIKA ada pertanyaan tentang klaim garansi, kerusakan barang, atau klaim DOA (Dead on Arrival):\n"
     "  1. SELESAIKAN langkah SOP ini, LALU jalankan ACTION ERP berikut:\n"
     "     -> lookup_product: cari produk yang disebutkan user untuk cek kategori dan stoknya.\n"
     "  Langkah SOP klaim garansi:\n"
     "  a. Customer hubungi CS WhatsApp +62-811-0000-123 lampirkan FOTO SERIAL NUMBER dan KELUHAN.\n"
     "  b. CS menerbitkan NOMOR TIKET dan ALAMAT SERVICE CENTER terdekat.\n"
     "  c. Jika unit < 7 hari (DOA) → penggantian unit baru gratis ongkir.\n"
     "  d. Jika unit > 7 hari → customer kirim via ekspedisi yang ditunjuk (biaya sendiri).\n"
     "  e. Estimasi perbaikan 5-14 hari; unit baru dikirim jika tidak dapat diperbaiki.\n"
     "  Catatan: Garansi NocBook = 2 tahun (battery coverage 12 bulan capacity < 80%)."),

    ("SOP_Pengembalian_Barang_Return",
     "SOP PENGEMBALIAN BARANG / RETURN:\n"
     "JIKA user tanya tentang retur, refund, pengembalian barang, atau batal pesanan:\n"
     "  1. Sebutkan SOP berikut, LALU jalankan ACTION:\n"
     "     -> lookup_order: jika user menyebutkan order_id, atau\n"
     "     -> lookup_customer: jika user menyebut nama/email, atau\n"
     "     -> no_erp_needed (jika hanya tanya prosedur umum).\n"
     "  Langkah SOP return:\n"
     "  a. Ajukan return via dashboard pesanan, MAKSIMAL 30 HARI setelah terima barang.\n"
     "  b. Upload foto unboxing, video keluhan, dan ALASAN RETURN.\n"
     "  c. Quality Approval dalam 2x24 jam (approve / reject).\n"
     "  d. Jika approve: kirim barang kembali ke gudang (upload resi ke dashboard).\n"
     "  e. Barang diterima gudang → DANA REFUND cair 5-7 hari kerja.\n"
     "  Syarat barang: segel asli utuh, BELUM TERAKTIVASI, lengkap bukti unboxing."),

    ("SOP_Pemesanan_Pembayaran",
     "SOP PEMESANAN & PEMBAYARAN:\n"
     "JIKA user tanya tentang cara order, metode bayar, atau checkout:\n"
     "  -> ACTION yang mungkin: lookup_product (cek harga/stok produk) ATAU no_erp_needed.\n"
     "  Alur pemesanan umum:\n"
     "  1. Tambah produk ke keranjang → pastikan stok tersedia.\n"
     "  2. Isi alamat pengiriman (nama lengkap, no HP, alamat lengkap, provinsi, kode pos).\n"
     "  3. Pilih kurir / ekspedisi (JNE, J&T, SiCepat, Gosend Instant untuk Jabodetabek).\n"
     "  4. Pilih METODE PEMBAYARAN: Transfer Bank (BCA/BNI/Mandiri/BRI), Virtual Account, "
     "E-Wallet (GoPay/OVO/ShopeePay), atau Kartu Kredit via Midtrans.\n"
     "  5. Lanjut bayar → invoice otomatis diterbitkan via email."),

    ("SOP_Pengiriman_Shipping",
     "SOP INFORMASI PENGIRIMAN & ONGKIR:\n"
     "JIKA user tanya estimasi kirim, ongkir, atau lama sampai:\n"
     "  -> ACTION: lookup_product jika menanyakan produk tertentu, ATAU no_erp_needed.\n"
     "  Estimasi wilayah Indonesia:\n"
     "  - Jabodetabek: 1-2 hari kerja.\n"
     "  - Pulau Jawa (non Jabodetabek): 2-4 hari kerja.\n"
     "  - Sumatera, Bali, Nusa Tenggara: 3-5 hari kerja.\n"
     "  - Sulawesi, Maluku, Papua: 5-7 hari kerja.\n"
     "  Ongkir dihitung OTOMATIS saat checkout berdasarkan berat & jarak (tabel kurir).\n"
     "  Gratis ongkir min. belanja Rp500.000 untuk Jabodetabek; Rp1.000.000 luar Jawa."),

    ("SOP_Stok_Kritis_Reorder",
     "SOP MANAJEMEN STOK & REORDER (internal):\n"
     "JIKA user (staf gudang / manager) bertanya stok menipis, reorder point, atau barang habis:\n"
     "  -> ACTION WAJIB: check_low_stock dengan threshold sesuai permintaan (default 10).\n"
     "  Prosedur restock:\n"
     "  1. Lihat daftar produk di bawah threshold stok.\n"
     "  2. Prioritaskan produk dengan HARGATINGGI dan VOLUME PENJUALAN tinggi.\n"
     "  3. Reorder qty = 2 x rata-rata penjualan 7 hari terakhir (minimum safety stock).\n"
     "  4. PO (Purchase Order) diterbitkan ke supplier utama (lead time ± 3 hari)."),

    ("SOP_Analisa_Penjualan",
     "SOP LAPORAN & ANALISA PENJUALAN:\n"
     "JIKA user meminta laporan penjualan, pendapatan, atau produk terlaris:\n"
     "  -> ACTION WAJIB: check_sales_report dengan periode hari sesuai user (default 7 hari).\n"
     "  Elemen yang harus ada di jawaban laporan:\n"
     "  a. TOTAL REVENUE periode tersebut.\n"
     "  b. TOP 3 PRODUK terlaris (unit + kontribusi revenue).\n"
     "  c. TREND: apakah produk gaming / produktivitas / aksesoris yang mendominasi.\n"
     "  d. REKOMENDASI BISNIS 1 action point yang spesifik (bukan umum)."),
]


def _seed_sop(con):
    n = con.execute("SELECT COUNT(*) FROM sop_documents").fetchone()[0]
    if n == 0:
        print("[DB] Mengisi seed SOP Knowledge Base ...")
        for src, text in SOP_SEED:
            for chunk in chunk_text(text):
                if chunk.strip():
                    doc_id = str(uuid.uuid4())
                    emb = encode(chunk)
                    con.execute(
                        "INSERT INTO sop_documents VALUES (?, ?, ?, ?, current_timestamp)",
                        [doc_id, src, chunk, emb],
                    )
        print(f"[DB] SOP seed selesai.")


# ========================================================================
# SEED : ERP Knowledge (KB #2)
# ========================================================================
ERP_DOCS_SEED = [
    ("ERP_Spesifikasi_NocBook_Pro_14",
     "SPESIFIKASI NocBook Pro 14:\n"
     "- CPU: Intel Core Ultra 7 155H (16-core, up to 4.8GHz)\n"
     "- RAM: 16GB LPDDR5X 6400MHz (onboard, tidak upgradeable)\n"
     "- Storage: 512GB NVMe Gen4 SSD (slot kedua tersedia)\n"
     "- Layar: 14-inch OLED 2.8K 90Hz, 100% DCI-P3, 400 nits, touchscreen opsional\n"
     "- Battery: 75Wh, fast charge 65W USB-C (0-50% dalam 30 menit)\n"
     "- Berat: 1.4 kg\n"
     "- I/O: 2x Thunderbolt 4, 1x USB-A 3.2, 1x HDMI 2.1, 1x SD card reader, 3.5mm combo\n"
     "- Warranty: 2 tahun resmi NocStore Indonesia, battery 12 bulan\n"
     "- Harga ERP: Rp12.500.000 / unit"),

    ("ERP_Spesifikasi_NocMouse_X1",
     "SPESIFIKASI NocMouse X1 Wireless:\n"
     "- Sensor: PAW3395 Optical 26.000 DPI, 650 IPS, 50G acceleration\n"
     "- Konektivitas: 2.4GHz dongle + Bluetooth 5.3 + wired USB-C (tri-mode)\n"
     "- Battery: 800mAh (hingga 80 jam 2.4GHz, 120 jam Bluetooth)\n"
     "- Berat: 58 gram (honeycomb shell)\n"
     "- Tahan air: IP54 (tahan percikan & debu ringan) — BUKAN untuk direndam\n"
     "- Switch: Kailh GM 8.0 (80M klik rating)\n"
     "- Dimensi: 122 x 67 x 39 mm\n"
     "- Warranty: 1 tahun pabrik\n"
     "- Harga ERP: Rp249.000 / unit"),

    ("ERP_Kategori_Produk_NocStore",
     "KATEGORI PRODUK NocStore (untuk analisa & pencarian):\n"
     "- KOMPUTER / LAPTOP: NocBook Pro 14\n"
     "- AKSESORIS INPUT: NocMouse X1, NocBoard K7, NocCam Pro\n"
     "- DISPLAY: NocView 4K 27\"\n"
     "- AUDIO: NocSound H500\n"
     "- STORAGE & MEMORI: NocStorage SSD NVMe, NocMem DDR4/DDR5 RAM\n"
     "- CONNECTIVITY: NocHub USB-C (coming soon)\n"
     "Setiap produk memiliki ID ERP unik, stok gudang terpusat di Jakarta Pusat."),

    ("ERP_Info_Supplier_Lead_Time",
     "INFORMASI SUPPLIER DAN LEAD TIME (untuk SOP reorder):\n"
     "- NocBook / NocView: PT NocTech Indonesia — lead time 3 hari kerja\n"
     "- NocMouse / NocBoard / NocSound: PT Aksesoris Nusantara — lead time 2 hari kerja\n"
     "- NocStorage / NocMem: PT Memory Distribusi Prima — lead time 1 hari kerja\n"
     "- NocCam: vendor campuran, stok aman 2x buffer\n"
     "Minimum Order Quantity (MOQ): nilai PO min Rp5.000.000 untuk free ongkir supplier."),
]


def _seed_erp_docs(con):
    n = con.execute("SELECT COUNT(*) FROM erp_documents").fetchone()[0]
    if n == 0:
        print("[DB] Mengisi seed ERP Knowledge Base ...")
        for src, text in ERP_DOCS_SEED:
            for chunk in chunk_text(text):
                if chunk.strip():
                    doc_id = str(uuid.uuid4())
                    emb = encode(chunk)
                    con.execute(
                        "INSERT INTO erp_documents VALUES (?, ?, ?, ?, current_timestamp)",
                        [doc_id, src, chunk, emb],
                    )
        print(f"[DB] ERP Knowledge seed selesai.")


# ========================================================================
# SEED : ERP Transactional (Products, Customers)
# ========================================================================
ERP_PRODUCTS = [
    ("Laptop NocBook Pro 14", 12500000, 25),
    ("Mouse Wireless NocMouse X1", 249000, 120),
    ("Keyboard Mechanical NocBoard K7", 899000, 45),
    ('Monitor 27" NocView 4K', 5750000, 18),
    ("Headset NocSound H500", 599000, 60),
    ("Webcam NocCam Pro 1080p", 325000, 80),
    ("SSD NVMe 1TB NocStorage", 1250000, 90),
    ("RAM DDR4 16GB NocMem", 650000, 75),
]

ERP_CUSTOMERS = [
    ("Budi Santoso", "budi@example.com", "081234567890"),
    ("Siti Rahayu", "siti@example.com", "081298765432"),
    ("PT. Teknologi Nusantara", "admin@nusantara.tech", "0211234567"),
]


def _seed_erp(con):
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        print("[DB] Mengisi seed data Produk ERP ...")
        for name, price, stock in ERP_PRODUCTS:
            emb = encode(name)
            con.execute(
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, current_timestamp)",
                [str(uuid.uuid4()), name, price, stock, emb],
            )

    if con.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        print("[DB] Mengisi seed data Customer ERP ...")
        for name, email, phone in ERP_CUSTOMERS:
            con.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?, current_timestamp)",
                [str(uuid.uuid4()), name, email, phone],
            )


# ========================================================================
# CHUNKING
# ========================================================================
def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    words = text.split()
    chunks: list[str] = []
    step = size - overlap
    if step <= 0:
        step = size
    for i in range(0, max(len(words), 1), step):
        chunk_words = words[i : i + size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
    return chunks


# ========================================================================
# CRUD : SOP Knowledge Base (KB #1)
# ========================================================================
def sop_insert_document(source: str, content: str) -> str:
    con = get_con()
    doc_id = str(uuid.uuid4())
    emb = encode(content)
    con.execute(
        "INSERT INTO sop_documents VALUES (?, ?, ?, ?, current_timestamp)",
        [doc_id, source, content, emb],
    )
    return doc_id


def sop_insert_chunks(source: str, chunks: list[str]) -> list[str]:
    ids = []
    for chunk in chunks:
        if chunk.strip():
            ids.append(sop_insert_document(source, chunk))
    return ids


def sop_search(query: str, k: int = 5) -> list:
    """Semantic search di KB SOP — untuk dicantumkan ke LLM SEBELUM action ERP."""
    con = get_con()
    emb = encode(query)
    return con.execute(f"""
        SELECT id, source, content,
               array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
        FROM sop_documents ORDER BY dist ASC LIMIT ?
    """, [emb, k]).fetchall()


def sop_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM sop_documents").fetchone()[0]


def sop_list_all(limit: int = 100) -> list:
    con = get_con()
    return con.execute(
        "SELECT id, source, content FROM sop_documents ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()


def sop_delete_all() -> int:
    con = get_con()
    n = sop_count()
    con.execute("DELETE FROM sop_documents")
    return n


# ========================================================================
# CRUD : ERP Knowledge Base (KB #2)
# ========================================================================
def erpdoc_insert_document(source: str, content: str) -> str:
    con = get_con()
    doc_id = str(uuid.uuid4())
    emb = encode(content)
    con.execute(
        "INSERT INTO erp_documents VALUES (?, ?, ?, ?, current_timestamp)",
        [doc_id, source, content, emb],
    )
    return doc_id


def erpdoc_insert_chunks(source: str, chunks: list[str]) -> list[str]:
    ids = []
    for chunk in chunks:
        if chunk.strip():
            ids.append(erpdoc_insert_document(source, chunk))
    return ids


def erpdoc_search(query: str, k: int = 5) -> list:
    """Semantic search di KB ERP (spesifikasi produk, katalog, supplier info)."""
    con = get_con()
    emb = encode(query)
    return con.execute(f"""
        SELECT id, source, content,
               array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
        FROM erp_documents ORDER BY dist ASC LIMIT ?
    """, [emb, k]).fetchall()


def erpdoc_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM erp_documents").fetchone()[0]


def erpdoc_list_all(limit: int = 100) -> list:
    con = get_con()
    return con.execute(
        "SELECT id, source, content FROM erp_documents ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()


def erpdoc_delete_all() -> int:
    con = get_con()
    n = erpdoc_count()
    con.execute("DELETE FROM erp_documents")
    return n


# ========================================================================
# COMPATIBILITY : fungsi k_* untuk backward-compat dengan kode lama
# (merge hasil dari sop_documents + erp_documents)
# ========================================================================
def k_search(query: str, k: int = 5) -> list:
    s = sop_search(query, k=k)
    e = erpdoc_search(query, k=k)
    merged = s + e
    merged.sort(key=lambda r: r[3])
    return merged[:k]


def k_count() -> int:
    return sop_count() + erpdoc_count()


def k_list_all(limit: int = 100) -> list:
    s = sop_list_all(limit)
    e = erpdoc_list_all(limit)
    return (s + e)[:limit]


def k_insert_chunks(source: str, chunks: list[str]) -> list[str]:
    return erpdoc_insert_chunks(source, chunks)


def k_delete_all() -> int:
    return sop_delete_all() + erpdoc_delete_all()


# ========================================================================
# ERP: PRODUCTS
# ========================================================================
def p_insert(name, price, stock) -> str:
    con = get_con()
    pid = str(uuid.uuid4())
    emb = encode(name)
    con.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, current_timestamp)",
        [pid, name, price, stock, emb],
    )
    return pid


def p_list(name=None) -> list:
    con = get_con()
    if name:
        q_emb = encode(name)
        return con.execute(
            f"SELECT id, name, price, stock, array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist FROM products ORDER BY dist ASC LIMIT 10",
            [q_emb],
        ).fetchall()
    return con.execute("SELECT id, name, price, stock FROM products ORDER BY name").fetchall()


def p_get(pid):
    con = get_con()
    return con.execute(
        "SELECT id, name, price, stock FROM products WHERE id=?", [pid]
    ).fetchone()


def p_update(pid, name, price, stock):
    con = get_con()
    emb = encode(name)
    con.execute(
        "UPDATE products SET name=?, price=?, stock=?, embedding=? WHERE id=?",
        [name, price, stock, emb, pid],
    )


def p_delete(pid):
    con = get_con()
    con.execute("DELETE FROM products WHERE id=?", [pid])


def p_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM products").fetchone()[0]


# ========================================================================
# ERP: CUSTOMERS
# ========================================================================
def c_insert(name, email=None, phone=None) -> str:
    con = get_con()
    cid = str(uuid.uuid4())
    con.execute(
        "INSERT INTO customers VALUES (?, ?, ?, ?, current_timestamp)",
        [cid, name, email, phone],
    )
    return cid


def c_list(name=None) -> list:
    con = get_con()
    if name:
        return con.execute(
            "SELECT id, name, email, phone FROM customers WHERE LOWER(name) LIKE ? ORDER BY name",
            [f"%{name.lower()}%"],
        ).fetchall()
    return con.execute(
        "SELECT id, name, email, phone FROM customers ORDER BY name"
    ).fetchall()


def c_get(cid):
    con = get_con()
    return con.execute(
        "SELECT id, name, email, phone FROM customers WHERE id=?", [cid]
    ).fetchone()


def c_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]


# ========================================================================
# ERP: ORDERS
# ========================================================================
def o_create(customer_id, items):
    con = get_con()
    cust = con.execute("SELECT id FROM customers WHERE id=?", [customer_id]).fetchone()
    if not cust:
        raise ValueError("Customer tidak ditemukan")
    total = 0.0
    prepared = []
    for it in items:
        p = con.execute(
            "SELECT id, name, price, stock FROM products WHERE id=?", [it["product_id"]]
        ).fetchone()
        if not p:
            raise ValueError(f"Produk {it['product_id']} tidak ditemukan")
        if it["qty"] <= 0:
            raise ValueError(f"Qty produk {p[1]} harus > 0")
        if p[3] < it["qty"]:
            raise ValueError(f"Stok {p[1]} kurang: tersedia {p[3]}, diminta {it['qty']}")
        subtotal = p[2] * it["qty"]
        total += subtotal
        prepared.append({
            "product_id": p[0], "price": p[2],
            "qty": it["qty"], "stock": p[3], "subtotal": subtotal,
        })
    oid = str(uuid.uuid4())
    con.execute(
        "INSERT INTO orders VALUES (?, ?, 'pending', ?, current_timestamp)",
        [oid, customer_id, total],
    )
    for it in prepared:
        con.execute(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), oid, it["product_id"], it["qty"], it["price"], it["subtotal"]],
        )
        con.execute(
            "UPDATE products SET stock = stock - ? WHERE id=?",
            [it["qty"], it["product_id"]],
        )
    return {"order_id": oid, "total_amount": total, "status": "pending"}


def o_get(oid):
    con = get_con()
    order = con.execute("""
        SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
        FROM orders o LEFT JOIN customers c ON c.id = o.customer_id WHERE o.id=?
    """, [oid]).fetchone()
    if not order:
        return None
    items = con.execute("""
        SELECT oi.id, oi.product_id, p.name, oi.qty, oi.price, oi.subtotal
        FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id=?
    """, [oid]).fetchall()
    return {"order": order, "items": items}


def o_list(limit=20, status=None):
    con = get_con()
    if status:
        return con.execute("""
            SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
            FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
            WHERE o.status = ? ORDER BY o.created_at DESC LIMIT ?
        """, [status, limit]).fetchall()
    return con.execute("""
        SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
        FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
        ORDER BY o.created_at DESC LIMIT ?
    """, [limit]).fetchall()


def o_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def o_set_status(oid, status):
    con = get_con()
    con.execute("UPDATE orders SET status=? WHERE id=?", [status, oid])


# ========================================================================
# ERP: REPORTS
# ========================================================================
def report_sales(days=7):
    con = get_con()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = con.execute("""
        SELECT p.name, COALESCE(SUM(oi.qty),0) qty, COALESCE(SUM(oi.subtotal),0) rev
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN orders o ON o.id = oi.order_id
        WHERE o.created_at >= ? AND o.status != 'cancelled'
        GROUP BY p.name ORDER BY rev DESC
    """, [since]).fetchall()
    total = con.execute("""
        SELECT COALESCE(SUM(oi.subtotal),0) FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.created_at >= ? AND o.status != 'cancelled'
    """, [since]).fetchone()[0]
    return {
        "period_days": days,
        "total_revenue": float(total),
        "by_product": [
            {"product": r[0], "qty": int(r[1]), "revenue": float(r[2])}
            for r in rows
        ],
    }


def report_low_stock(threshold=10):
    con = get_con()
    rows = con.execute("""
        SELECT id, name, price, stock FROM products WHERE stock <= ? ORDER BY stock ASC
    """, [threshold]).fetchall()
    return {
        "threshold": threshold,
        "products": [
            {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]}
            for r in rows
        ],
    }


# ========================================================================
# CHAT: Chat Sessions (ChatGPT-style sidebar list percakapan)
# ========================================================================
def chat_session_create(title: str = "Percakapan baru", customer_id=None) -> str:
    con = get_con()
    sid = str(uuid.uuid4())
    if not title or len(title.strip()) == 0:
        title = "Percakapan baru"
    con.execute(
        "INSERT INTO chat_sessions (id, title, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, current_timestamp, current_timestamp)",
        [sid, title[:120], customer_id],
    )
    return sid


def chat_session_update_title(sid: str, title: str):
    con = get_con()
    con.execute(
        "UPDATE chat_sessions SET title = ?, updated_at = current_timestamp WHERE id = ?",
        [title[:120] if title else "Percakapan baru", sid],
    )


def chat_session_bump_updated(sid: str):
    con = get_con()
    con.execute(
        "UPDATE chat_sessions SET updated_at = current_timestamp WHERE id = ?", [sid]
    )


def chat_session_list(customer_id=None, limit=100) -> list:
    con = get_con()
    if customer_id:
        rows = con.execute("""
            SELECT s.id, s.title, s.customer_id, s.created_at, s.updated_at,
                   COALESCE(COUNT(m.id),0) msg_count,
                   (SELECT content FROM chat_messages
                     WHERE session_id=s.id AND role='assistant'
                     ORDER BY created_at DESC LIMIT 1) last_msg
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id
            WHERE s.customer_id = ?
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, [customer_id, limit]).fetchall()
    else:
        rows = con.execute("""
            SELECT s.id, s.title, s.customer_id, s.created_at, s.updated_at,
                   COALESCE(COUNT(m.id),0) msg_count,
                   (SELECT m2.content FROM chat_messages m2
                     WHERE m2.session_id=s.id AND m2.role='assistant'
                     ORDER BY m2.created_at DESC LIMIT 1) last_msg
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, [limit]).fetchall()
    return [
        {
            "id": r[0], "title": r[1], "customer_id": r[2],
            "created_at": r[3], "updated_at": r[4],
            "messages_count": int(r[5] or 0),
            "last_message": r[6],
        }
        for r in rows
    ]


def chat_session_get(sid: str):
    con = get_con()
    r = con.execute("""
        SELECT s.id, s.title, s.customer_id, s.created_at, s.updated_at,
               (SELECT COUNT(*) FROM chat_messages WHERE session_id=s.id),
               (SELECT content FROM chat_messages
                 WHERE session_id=s.id AND role='assistant'
                 ORDER BY created_at DESC LIMIT 1)
        FROM chat_sessions s WHERE s.id = ?
    """, [sid]).fetchone()
    if not r:
        return None
    return {
        "id": r[0], "title": r[1], "customer_id": r[2],
        "created_at": r[3], "updated_at": r[4],
        "messages_count": int(r[5] or 0),
        "last_message": r[6],
    }


def chat_session_delete(sid: str):
    con = get_con()
    con.execute("DELETE FROM chat_messages WHERE session_id = ?", [sid])
    con.execute("DELETE FROM chat_sessions WHERE id = ?", [sid])


def chat_sessions_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]


# ========================================================================
# CHAT: Messages (user / assistant)
# ========================================================================
def chat_message_add(
    sid: str, role: str, content: str,
    tokens_used: int = 0, agentic_steps=None,
) -> str:
    """Satu pesan baru di session."""
    con = get_con()
    mid = str(uuid.uuid4())
    import json
    steps_json = json.dumps(agentic_steps, ensure_ascii=False) if agentic_steps else None
    con.execute("""
        INSERT INTO chat_messages (id, session_id, role, content, tokens_used, agentic_steps, created_at)
        VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
    """, [mid, sid, role, content, int(tokens_used or 0), steps_json])
    con.execute(
        "UPDATE chat_sessions SET updated_at = current_timestamp WHERE id = ?", [sid]
    )
    return mid


def chat_messages_list(sid: str, limit: int | None = None, since_order: int | None = None) -> list:
    """
    Ambil semua pesan di satu session, ordered by created_at ASC.
    - limit: hanya N pesan TERAKHIR (untuk context memory).
    - since_order: reserved.
    """
    con = get_con()
    import json
    rows = con.execute("""
        SELECT id, session_id, role, content, tokens_used, agentic_steps, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
    """, [sid]).fetchall()
    out = []
    for r in rows:
        try:
            steps = json.loads(r[5]) if r[5] else None
        except Exception:
            steps = None
        out.append({
            "id": r[0], "session_id": r[1], "role": r[2], "content": r[3],
            "tokens_used": int(r[4] or 0), "agentic_steps": steps,
            "created_at": r[6],
        })
    if limit:
        return out[-int(limit):]
    return out


def chat_messages_count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]


# ========================================================================
# COMPAT: chat_customers tabel existing user (tambahkan helper minimal)
# ========================================================================
def chat_customer_link(customer_id, summary=None):
    """Insert / update ringkasan di chat_customers (backward compat)."""
    con = get_con()
    row = con.execute(
        "SELECT id FROM chat_customers WHERE customer_id = ?", [customer_id]
    ).fetchone()
    if not summary:
        summary = ""
    import json as _j
    summary = _j.dumps(summary, ensure_ascii=False) if not isinstance(summary, str) else summary
    summary_emb = encode(summary[:1000]) if summary and len(summary) > 0 else None
    if row:
        con.execute("""
            UPDATE chat_customers
            SET chat_history = ?,
                embedding = ?,
                last_chat_time = current_timestamp
            WHERE customer_id = ?
        """, [summary, summary_emb, customer_id])
        return row[0]
    cid = str(uuid.uuid4())
    con.execute("""
        INSERT INTO chat_customers (id, customer_id, chat_history, embedding, last_chat_time, created_at)
        VALUES (?, ?, ?, ?, current_timestamp, current_timestamp)
    """, [cid, customer_id, summary, summary_emb])
    return cid
