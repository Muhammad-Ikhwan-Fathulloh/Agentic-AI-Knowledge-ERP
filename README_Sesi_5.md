# Sesi 5 — Knowledge ERP: CRUD REST API

**File notebook:** `Sesi_5_Knowledge_ERP_CRUD_API.ipynb`

## Tentang Sesi Ini
Domain kedua dari kurikulum ini dimulai: **Knowledge ERP** — data bisnis/transaksional (produk, pelanggan, order), berbeda karakter dari dokumen bebas di Sesi 1–4 karena agent nantinya akan **menulis** data (bukan cuma membaca), sehingga butuh validasi lebih ketat.

## Prasyarat
- Sudah menyelesaikan Sesi 1–4 (paham pola FastAPI + DuckDB dari Sesi 2, sebagai referensi struktur).

## Yang Akan Dipelajari
- Merancang skema data relasional sederhana di DuckDB (`products`, `customers`, `orders`, `order_items`).
- Validasi bisnis di level API (misalnya menolak order jika stok tidak cukup).
- Endpoint gabungan (JOIN) untuk menampilkan detail order lengkap dengan nama produk.

## Struktur Notebook
1. Setup environment (`duckdb`, `fastapi`, `httpx`).
2. Skema data ERP (4 tabel + relasi).
3. Seed data contoh (produk & pelanggan).
4. CRUD produk (`POST/GET /products`).
5. **TODO 1**: lengkapi `PUT` dan `DELETE /products/{pid}`.
6. Endpoint order dengan validasi stok (`POST /orders`, `GET /orders/{order_id}` dengan JOIN).
7. Uji API dengan `TestClient`.
8. **TODO 2**: uji kasus order dengan qty melebihi stok — pastikan error 400 yang informatif, bukan crash.

## Cara Menjalankan
Notebook ini murni offline-friendly (tidak butuh model LLM ataupun API key) — fokus penuh ke desain API dan validasi data.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Relational schema | Struktur tabel yang saling terhubung lewat foreign key (mis. `order_items.product_id`) |
| Business validation | Aturan bisnis yang dicek di level API, misal stok cukup sebelum order dibuat |
| JOIN query | Menggabungkan data dari beberapa tabel dalam satu query (mis. order + nama produk) |

## Output / Deliverable
- API ERP (`erp_app`) dengan CRUD produk + order lengkap validasi stok.
- File `erp.duckdb` terisi data contoh.

## Lanjut ke Sesi Berikutnya
Sesi 6 menghubungkan API ini ke ReAct agent Qwen yang bisa mengambil **aksi** (cek stok, buat order) lewat bahasa natural — bukan hanya menjawab pertanyaan seperti Sesi 3.
