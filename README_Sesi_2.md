# Sesi 2 — Knowledge Agent: CRUD REST API

**File notebook:** `Sesi_2_Knowledge_Agent_CRUD_API.ipynb`

## Tentang Sesi Ini
Data di `knowledge.duckdb` (hasil Sesi 1) dibungkus menjadi REST API penuh memakai FastAPI, sehingga bisa diakses via HTTP — bukan hanya dipanggil langsung sebagai fungsi Python. API ini nantinya jadi *tool* yang dipanggil oleh agent di Sesi 3 dan 4.

## Prasyarat
- Sudah menyelesaikan Sesi 1 (paham konsep chunking, embedding, DuckDB vector store).
- Familiar dengan konsep REST API dasar (GET/POST/PUT/DELETE).

## Yang Akan Dipelajari
- Desain endpoint RESTful untuk resource `documents`.
- Validasi payload otomatis dengan Pydantic.
- Endpoint `/documents/search` sebagai endpoint semantic search (di luar pola CRUD klasik).
- Cara menguji FastAPI di dalam Colab tanpa server eksternal, memakai `TestClient`.

## Struktur Notebook
1. Setup environment (`fastapi`, `httpx`, `nest_asyncio`, `uvicorn`).
2. Rekonstruksi koneksi DuckDB & embedding model dari Sesi 1 (auto-seed jika kosong).
3. Endpoint `POST/GET/PUT/DELETE /documents` + `GET /documents/search`.
4. **TODO 1**: implementasi `POST /documents/bulk` untuk insert banyak dokumen sekaligus.
5. Uji API dengan `TestClient` (tanpa perlu ngrok).
6. (Opsional) sel untuk menjalankan sebagai server publik via `pyngrok`.

## Cara Menjalankan
Jalankan sel berurutan. `app` (objek FastAPI) dan `client` (TestClient) akan tersedia di memori notebook — keduanya dipakai lagi sebagai referensi pola di Sesi 3.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Pydantic model | Skema validasi otomatis untuk request/response body |
| TestClient | Cara menguji FastAPI tanpa menjalankan server sungguhan — cocok untuk Colab |
| ngrok | Tool opsional untuk expose server lokal ke internet publik |

## Output / Deliverable
- API CRUD + search lengkap (`app`), teruji lewat `TestClient`.
- Endpoint `/documents/bulk` (hasil TODO 1).

## Lanjut ke Sesi Berikutnya
Sesi 3 memakai endpoint `/documents/search` ini sebagai *tool* yang dipanggil oleh agent Qwen lewat pola ReAct.
