# Sesi 6 — Knowledge ERP: Prompting ReAct

**File notebook:** `Sesi_6_Knowledge_ERP_ReAct_Prompting.ipynb`

## Tentang Sesi Ini
Pola ReAct dari Sesi 3 diterapkan lagi, tapi kali ini ke tool-tool ERP (Sesi 5) — sehingga agent bisa **mengambil aksi nyata** (membuat order, mengubah data), bukan cuma mencari informasi. Ini menaikkan taruhannya: agent yang menulis data butuh guardrail yang jauh lebih ketat dibanding agent baca-saja.

## Prasyarat
- Sudah menyelesaikan Sesi 3 (paham pola ReAct dasar) dan Sesi 5 (API ERP).

## Yang Akan Dipelajari
- Kenapa agent "penulis data" butuh pengamanan ekstra: konfirmasi sebelum eksekusi, validasi parameter ketat, audit log.
- Format `Action Input` sebagai JSON (bukan teks bebas seperti Sesi 3) agar parameter multi-field bisa diparsing andal.
- Pola *human-in-the-loop*: meminta konfirmasi manusia sebelum aksi berisiko (mis. `create_order`) benar-benar dieksekusi.

## Struktur Notebook
1. Setup environment + load model Qwen (sama seperti Sesi 3).
2. Rekonstruksi ERP API dari Sesi 5 (ringkas).
3. Prompt ReAct khusus ERP (`ERP_REACT_SYSTEM`) dengan aturan wajib cek stok sebelum buat order.
4. Tool executor ERP (`call_erp_tool`): `check_stock`, `create_order`, `get_order_status`.
5. `erp_react_loop()` — ReAct loop dengan opsi konfirmasi manual (`input()`) sebelum aksi tulis data.
6. **TODO 1**: buat tabel `agent_logs` di DuckDB untuk audit trail setiap Action + Observation.
7. **TODO 2**: uji kasus stok habis — pastikan agent menolak dengan sopan, bukan tetap membuat order.

## Cara Menjalankan
Sama seperti Sesi 3, unduh model Qwen di awal (butuh koneksi Colab). Perhatikan: sel dengan `input()` untuk konfirmasi order butuh interaksi manual saat dijalankan.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Human-in-the-loop | Meminta persetujuan manusia sebelum aksi berisiko dieksekusi otomatis |
| Audit trail | Catatan setiap aksi agent (untuk keperluan investigasi/compliance) |
| Guardrail | Aturan pembatas agar agent tidak melakukan aksi yang salah/berbahaya |

## Output / Deliverable
- Fungsi `erp_react_loop()` yang bisa cek stok dan membuat order sederhana lewat bahasa natural.
- Tabel `agent_logs` (hasil TODO 1) untuk audit setiap langkah agent.

## Lanjut ke Sesi Berikutnya
Sesi 7 memakai Qwen (model yang sama) untuk **generate laporan naratif** dari data ERP — pola generative reporting, bukan lagi tool-calling/aksi.
