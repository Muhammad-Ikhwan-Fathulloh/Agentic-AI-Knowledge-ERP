# Sesi 5 — Knowledge ERP: CRUD REST API (Port 8005)

## Ringkasan
Membangun **domain data transaksional ERP sederhana** (Produk, Pelanggan, Order) dengan DuckDB embedded. Tidak ada LLM di sini — service ini murni sebagai **data layer** yang nantinya jadi tool agent di Sesi 6, 7, dan 8.

## Fitur
| Entity | Endpoint | Keterangan |
|---|---|---|
| Products | `POST /products`, `GET /products?name=`, `GET /products/{id}`, `PUT`, `DELETE` | Seed 8 produk contoh otomatis |
| Customers | `POST /customers`, `GET /customers?name=`, `GET /customers/{id}` | Seed 3 pelanggan contoh |
| Orders | `POST /orders`, `GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` | Validasi stok: otomatis reject bila stok kurang |
| Reports | `GET /report/sales?days=7` | Laporan total revenue + per produk |
| Reports | `GET /report/low-stock?threshold=10` | Produk dengan stok di bawah threshold |

## Cara Run
```cmd
run.bat
```
```cmd
uvicorn app.main:app --port 8005 --reload
```

## Struktur
```
Sesi_5_Knowledge_ERP_CRUD/
├── app/
│   ├── config.py      # Setting duckdb_path, app_port
│   ├── database.py    # Schema + seed + ERPDatabase class (business logic)
│   ├── schemas.py     # Pydantic ProductIn/Out, CustomerIn/Out, OrderIn
│   └── main.py        # FastAPI dengan 30+ endpoint
└── tests/test_erp.py  # Unit test: seed, create_customer, stok shortage validation
```

## Uji Manual via `/docs`
1. `GET /products` — pastikan 8 produk contoh muncul.
2. `GET /customers` — pastikan 3 pelanggan muncul.
3. Ambil salah satu `customer_id` dan `product_id`.
4. `POST /orders`:
   ```json
   {"customer_id":"<cid>","items":[{"product_id":"<pid>","qty":1}]}
   ```
5. Coba `qty` lebih besar dari stok → pastikan **HTTP 400 error message** ramah.
