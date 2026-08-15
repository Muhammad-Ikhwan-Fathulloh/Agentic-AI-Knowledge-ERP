# Sesi 7 — Knowledge ERP dengan LLM Generate (Qwen)

**File notebook:** `Sesi_7_Knowledge_ERP_LLM_Generate_Qwen.ipynb`

## Tentang Sesi Ini
Peran Qwen bergeser dari *tool-calling* (Sesi 4, 6) ke **generative reporting**: mengubah data ERP mentah (hasil query SQL) menjadi ringkasan/narasi bahasa natural — laporan penjualan, peringatan stok kritis, dsb. Seluruhnya berjalan lokal, tanpa data bisnis terkirim ke API eksternal.

## Prasyarat
- Sudah menyelesaikan Sesi 5–6 (paham skema data ERP dan cara query-nya).

## Yang Akan Dipelajari
- Perbedaan *reasoning agent* (menentukan aksi) vs *generative reporting* (menyusun narasi dari data terstruktur).
- Pola: query SQL → ringkasan teks → prompt LLM untuk narasi (single-shot, tanpa loop ReAct).
- Prompt engineering untuk model kecil: instruksi format eksplisit (jumlah kalimat, larangan mengulang data mentah) karena Qwen kecil cenderung kurang natural dibanding model besar.

## Struktur Notebook
1. Setup environment + load model Qwen.
2. Rekonstruksi data ERP (Sesi 5–6) + seed 20 order contoh (transaksi acak 7 hari terakhir) agar ada data untuk dilaporkan.
3. Query ringkasan penjualan murni SQL (`get_sales_summary`).
4. Generate narasi laporan dengan Qwen (`generate_sales_report`).
5. **TODO 1**: implementasikan `generate_stock_alert()` untuk produk stok < 10.
6. **TODO 2**: bandingkan laporan SQL-only vs narasi Qwen — diskusi kapan masing-masing lebih tepat.

## Cara Menjalankan
Model Qwen diunduh ulang di awal notebook (jalankan di Colab). Data transaksi contoh di-generate otomatis (random) jika `orders` masih kosong, sehingga laporan selalu punya isi untuk didemokan.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Generative reporting | Mengubah data terstruktur (angka, tabel) menjadi narasi bahasa natural |
| Single-shot prompting | Satu kali panggilan LLM tanpa loop, cocok untuk tugas ringkasan |
| Prompt constraint | Instruksi eksplisit (jumlah kalimat, larangan tertentu) untuk mengarahkan gaya output model kecil |

## Output / Deliverable
- Fungsi `generate_sales_report()` dan `generate_stock_alert()` (hasil TODO 1).
- Contoh output laporan penjualan & stok kritis dalam Bahasa Indonesia.

## Lanjut ke Sesi Berikutnya
Sesi 8 menggabungkan seluruh komponen — Knowledge Agent (Sesi 1–4) dan Knowledge ERP (Sesi 5–7) — menjadi satu **orchestrator agent** yang merutekan pertanyaan secara otomatis.
