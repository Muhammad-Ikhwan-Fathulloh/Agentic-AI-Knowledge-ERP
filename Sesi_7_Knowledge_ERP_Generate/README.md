# Sesi 7 — Knowledge ERP Generate (Laporan Naratif via Qwen)

## Ringkasan
Menggunakan Qwen lokal untuk **mengubah data ERP terstruktur (angka) menjadi narasi bahasa natural** laporan bisnis yang siap kirim / presentasikan.

## Tiga Laporan yang Didukung
| Endpoint | Input | Output |
|---|---|---|
| `POST /report/sales` | `{"days": 7}` | Ringkasan 4 paragraf: total revenue, 3 terlaris, tren, 1 rekomendasi actionable |
| `POST /report/low-stock` | `{"threshold": 10}` | Notulensi 6 kalimat: SKU count, 3 terendah, dampak, usulan restock, prioritas, next step |
| `GET /report/combined?days=7&threshold=10` | query param | Gabungan kedua laporan di atas |

## Aliran Data
```
[SQL / ERP API Sesi 5]  →  serialisasi → summary TEXT  →  prompt Qwen  →  narasi final
```

## Cara Run
```cmd
run.bat
```
(Otomatis spawning Sesi 5 + Sesi 7)

## Download Model Qwen
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**

Setelah download, letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.

## Struktur
```
Sesi_7_Knowledge_ERP_Generate/
├── app/
│   ├── config.py / schemas.py / llm.py   (llama port 8083)
│   ├── report_data.py  # ERPReportData: HTTP client ke Sesi 5 /report
│   ├── generators.py   # Prompt SALES_PROMPT / LOW_STOCK_PROMPT + ringkasan data
│   └── main.py
└── tests/test_generators.py  # Test helper _summarize_sales / _summarize_lowstock
```

## Tips Prompt Engineering
- Karena model kecil (Qwen 0.5B–3B), **sangat eksplisit** dengan format jumlah paragraf/kalimat.
- Prefilter data: Jangan kirim 100 baris sekaligus — sort + TOP N saja.
- Bila jawaban terlalu pendek / jelek: naïkan `temperature` sedikit (0.4–0.6) dan tambahkan **few-shot example** di prompt.
