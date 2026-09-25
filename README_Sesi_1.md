# Sesi 1 - Prepare Data Knowledge & Create Vector DB

**File notebook:** `Sesi_1_Prepare_Data_Knowledge_VectorDB.ipynb`

## Tentang Sesi Ini
Sesi pembuka ini membangun fondasi untuk seluruh Knowledge Agent (Sesi 1–4): mengubah dokumen mentah (FAQ, SOP, artikel) menjadi data yang bisa dicari secara **semantik** (berdasarkan makna, bukan sekadar kata kunci) dengan menyimpannya sebagai vektor di DuckDB.

## Prasyarat
- Python dasar, familiar dengan `pip install`.
- Tidak perlu API key - semua berjalan lokal/offline setelah paket ter-install.

## Yang Akan Dipelajari
- Kenapa semantic search (vector) lebih unggul dari keyword search untuk RAG.
- Strategi **chunking** dokumen (fixed-size + overlap) dan trade-off ukuran chunk.
- Cara memakai DuckDB sebagai vector store dengan ekstensi `vss` (tanpa server database terpisah).
- Cara meng-generate embedding dengan `sentence-transformers` (model `all-MiniLM-L6-v2`, 384 dimensi).

## Struktur Notebook
1. Setup environment (`duckdb`, `sentence-transformers`, `pypdf`).
2. Konsep vector database.
3. Membuat skema tabel `documents` di DuckDB + index HNSW.
4. Load embedding model.
5. Contoh data mentah berbahasa Indonesia.
6. Chunking teks - termasuk **TODO 1**: eksperimen ukuran chunk.
7. Ingest: embed & simpan ke DuckDB.
8. Fungsi `search(query, k)` untuk semantic search - termasuk **TODO 2**: uji query lain.

## Cara Menjalankan
Buka di Google Colab, jalankan sel dari atas ke bawah secara berurutan. Tidak butuh GPU. Output akhirnya adalah file `knowledge.duckdb` yang berisi dokumen ter-embed.

## Konsep Kunci
| Istilah    | Penjelasan Singkat                                                            |
| ---------- | ----------------------------------------------------------------------------- |
| Chunking   | Memecah dokumen panjang jadi potongan kecil agar pas dengan konteks pencarian |
| Overlap    | Irisan antar-chunk supaya konteks tidak terputus di batas potongan            |
| Embedding  | Representasi numerik (vektor) dari makna teks                                 |
| HNSW index | Struktur index untuk mempercepat pencarian similarity pada data vektor besar  |

## Output / Deliverable
- File `knowledge.duckdb` terisi dokumen contoh.
- Fungsi `ingest()` dan `search()` yang siap dipakai ulang di Sesi 2.

## Lanjut ke Sesi Berikutnya
Sesi 2 akan membungkus tabel `documents` ini menjadi REST API penuh (CRUD + search) memakai FastAPI.
