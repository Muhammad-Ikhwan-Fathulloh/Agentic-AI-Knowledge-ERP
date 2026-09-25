# Sesi 5 - Knowledge ERP: CRUD REST API (Port 8005)

## Ringkasan
Membangun **domain data transaksional ERP sederhana** (Produk, Pelanggan, Order) dengan DuckDB embedded. Tidak ada LLM di sini - service ini murni sebagai **data layer** yang nantinya jadi tool agent di Sesi 6, 7, dan 8.

## Fitur
| Entity    | Endpoint                                                                       | Keterangan                                      |
| --------- | ------------------------------------------------------------------------------ | ----------------------------------------------- |
| Products  | `POST /products`, `GET /products?name=`, `GET /products/{id}`, `PUT`, `DELETE` | Seed 8 produk contoh otomatis                   |
| Customers | `POST /customers`, `GET /customers?name=`, `GET /customers/{id}`               | Seed 3 pelanggan contoh                         |
| Orders    | `POST /orders`, `GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` | Validasi stok: otomatis reject bila stok kurang |
| Reports   | `GET /report/sales?days=7`                                                     | Laporan total revenue + per produk              |
| Reports   | `GET /report/low-stock?threshold=10`                                           | Produk dengan stok di bawah threshold           |

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
1. `GET /products` - pastikan 8 produk contoh muncul.
2. `GET /customers` - pastikan 3 pelanggan muncul.
3. Ambil salah satu `customer_id` dan `product_id`.
4. `POST /orders`:
   ```json
   {"customer_id":"<cid>","items":[{"product_id":"<pid>","qty":1}]}
   ```
5. Coba `qty` lebih besar dari stok → pastikan **HTTP 400 error message** ramah.

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Langkah 1 - Setup Folder & Environment

```cmd
mkdir Sesi_5_Knowledge_ERP_CRUD
cd Sesi_5_Knowledge_ERP_CRUD
mkdir app tests
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn[standard] pydantic pydantic-settings python-dotenv duckdb httpx pytest
```

### Langkah 2 - Buat `.env`

```env
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384
DUCKDB_PATH=./erp.duckdb
APP_PORT=8005
```

### Langkah 3 - Buat `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    duckdb_path: str = "./erp.duckdb"
    app_port: int = 8005

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 - Buat `app/schemas.py`

```python
from pydantic import BaseModel
from typing import Optional

class ProductIn(BaseModel):
    name: str
    category: str
    price: float
    stock: int

class ProductOut(ProductIn):
    id: str

class CustomerIn(BaseModel):
    name: str
    email: str

class CustomerOut(CustomerIn):
    id: str

class OrderItem(BaseModel):
    product_id: str
    qty: int

class OrderIn(BaseModel):
    customer_id: str
    items: list[OrderItem]
```

### Langkah 5 - Buat `app/database.py`

Ini jantung Sesi 5 - berisi seluruh logika bisnis ERP:

```python
import duckdb, uuid
from .config import settings

SEED_PRODUCTS = [
    ("NocBook Pro 14", "Laptop",  12_500_000, 15),
    ("NocMouse Wireless", "Mouse",    350_000, 50),
    ("NocKeyboard TKL", "Keyboard",   450_000, 30),
    ("NocHeadset Pro", "Audio",       750_000, 20),
    ("NocMem DDR4 16GB", "RAM",       450_000, 40),
    ("NocSSD 512GB", "Storage",       650_000, 25),
    ("NocWebcam HD", "Aksesoris",     280_000, 35),
    ("NocHub USB-C 7in1", "Aksesoris",220_000, 60),
]

SEED_CUSTOMERS = [
    ("Budi Santoso",  "budi@example.com"),
    ("Siti Rahma",    "siti@example.com"),
    ("Reza Pratama",  "reza@example.com"),
]

class ERPDatabase:
    def __init__(self):
        self.path = settings.duckdb_path
        self._init()

    def _conn(self):
        return duckdb.connect(self.path)

    def _init(self):
        c = self._conn()
        c.execute("""
            CREATE TABLE IF NOT EXISTS products(
                id VARCHAR PRIMARY KEY,
                name VARCHAR, category VARCHAR,
                price DOUBLE, stock INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS customers(
                id VARCHAR PRIMARY KEY,
                name VARCHAR, email VARCHAR UNIQUE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders(
                id VARCHAR PRIMARY KEY,
                customer_id VARCHAR,
                status VARCHAR DEFAULT 'pending',
                total_price DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS order_items(
                id VARCHAR PRIMARY KEY,
                order_id VARCHAR, product_id VARCHAR,
                qty INTEGER, unit_price DOUBLE
            )
        """)
        c.close()

    def seed(self):
        c = self._conn()
        if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            for name, cat, price, stock in SEED_PRODUCTS:
                c.execute("INSERT INTO products VALUES(?,?,?,?,?)",
                          [str(uuid.uuid4()), name, cat, price, stock])
        if c.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
            for name, email in SEED_CUSTOMERS:
                c.execute("INSERT INTO customers VALUES(?,?,?)",
                          [str(uuid.uuid4()), name, email])
        c.close()

    # PRODUCTS
    def list_products(self, name_filter=""):
        c = self._conn()
        q = "SELECT id,name,category,price,stock FROM products"
        if name_filter:
            q += f" WHERE name ILIKE '%{name_filter}%'"
        rows = c.execute(q).fetchall()
        c.close()
        return [{"id":r[0],"name":r[1],"category":r[2],"price":r[3],"stock":r[4]} for r in rows]

    def get_product(self, pid):
        c = self._conn()
        r = c.execute("SELECT * FROM products WHERE id=?", [pid]).fetchone()
        c.close()
        return {"id":r[0],"name":r[1],"category":r[2],"price":r[3],"stock":r[4]} if r else None

    # CUSTOMERS
    def list_customers(self, name_filter=""):
        c = self._conn()
        q = "SELECT id,name,email FROM customers"
        if name_filter:
            q += f" WHERE name ILIKE '%{name_filter}%'"
        rows = c.execute(q).fetchall()
        c.close()
        return [{"id":r[0],"name":r[1],"email":r[2]} for r in rows]

    # ORDERS - validasi stok
    def create_order(self, customer_id: str, items: list) -> dict:
        c = self._conn()
        total = 0
        # Validasi stok dulu
        for item in items:
            r = c.execute("SELECT stock, price FROM products WHERE id=?",
                          [item["product_id"]]).fetchone()
            if not r:
                raise ValueError(f"Produk {item['product_id']} tidak ditemukan")
            if r[0] < item["qty"]:
                name = c.execute("SELECT name FROM products WHERE id=?",
                                 [item["product_id"]]).fetchone()[0]
                raise ValueError(f"Stok {name} tidak cukup (ada: {r[0]}, diminta: {item['qty']})")
            total += r[1] * item["qty"]

        order_id = str(uuid.uuid4())
        c.execute("INSERT INTO orders(id, customer_id, total_price) VALUES(?,?,?)",
                  [order_id, customer_id, total])
        for item in items:
            price = c.execute("SELECT price FROM products WHERE id=?",
                              [item["product_id"]]).fetchone()[0]
            c.execute("INSERT INTO order_items VALUES(?,?,?,?,?)",
                      [str(uuid.uuid4()), order_id,
                       item["product_id"], item["qty"], price])
            c.execute("UPDATE products SET stock=stock-? WHERE id=?",
                      [item["qty"], item["product_id"]])
        c.close()
        return {"order_id": order_id, "total_price": total}

    # REPORTS
    def sales_report(self, days=7):
        c = self._conn()
        rows = c.execute(f"""
            SELECT p.name, SUM(oi.qty) AS qty_sold,
                   SUM(oi.qty * oi.unit_price) AS revenue
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            JOIN orders o ON o.id = oi.order_id
            WHERE o.created_at >= NOW() - INTERVAL '{days} days'
            GROUP BY p.name ORDER BY revenue DESC
        """).fetchall()
        total = sum(r[2] for r in rows)
        c.close()
        return {"days": days, "total_revenue": total,
                "products": [{"name":r[0],"qty_sold":r[1],"revenue":r[2]} for r in rows]}

    def low_stock_report(self, threshold=10):
        c = self._conn()
        rows = c.execute(
            "SELECT id,name,stock FROM products WHERE stock<=? ORDER BY stock ASC",
            [threshold]
        ).fetchall()
        c.close()
        return [{"id":r[0],"name":r[1],"stock":r[2]} for r in rows]
```

### Langkah 6 - Buat `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from .database import ERPDatabase
from .schemas import ProductIn, CustomerIn, OrderIn

db = ERPDatabase()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.seed()
    yield

app = FastAPI(title="Sesi 5 - Knowledge ERP CRUD", lifespan=lifespan)

# --- PRODUCTS ---
@app.get("/products")
def list_products(name: str = ""):
    return db.list_products(name)

@app.get("/products/{pid}")
def get_product(pid: str):
    p = db.get_product(pid)
    if not p: raise HTTPException(404, "Produk tidak ditemukan")
    return p

# --- CUSTOMERS ---
@app.get("/customers")
def list_customers(name: str = ""):
    return db.list_customers(name)

# --- ORDERS ---
@app.post("/orders")
def create_order(req: OrderIn):
    try:
        return db.create_order(req.customer_id, [i.dict() for i in req.items])
    except ValueError as e:
        raise HTTPException(400, str(e))

# --- REPORTS ---
@app.get("/report/sales")
def sales_report(days: int = 7):
    return db.sales_report(days)

@app.get("/report/low-stock")
def low_stock(threshold: int = 10):
    return db.low_stock_report(threshold)
```

### Langkah 7 - Jalankan & Uji Step-by-Step

```cmd
uvicorn app.main:app --port 8005 --reload
```

**Buka:** http://localhost:8005/docs

**Urutan uji yang benar:**

1. **`GET /products`** → catat salah satu `id` produk (misal NocMouse)
2. **`GET /customers`** → catat salah satu `id` pelanggan (misal Budi Santoso)
3. **`POST /orders`** → buat order:
   ```json
   {
     "customer_id": "<id_dari_langkah_2>",
     "items": [{ "product_id": "<id_dari_langkah_1>", "qty": 2 }]
   }
   ```
   → Response berisi `order_id` dan `total_price`

4. **`GET /report/sales?days=7`** → lihat laporan penjualan (order tadi masuk)
5. **`GET /report/low-stock?threshold=50`** → lihat produk dengan stok di bawah 50

6. **Uji validasi stok** - buat order dengan `qty` melebihi stok:
   ```json
   { "customer_id": "...", "items": [{ "product_id": "...", "qty": 9999 }] }
   ```
   → Harus dapat **HTTP 400** dengan pesan stok tidak cukup

### Langkah 8 - Unit Test

```python
# tests/test_erp.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_seed():
    r = client.get("/products")
    assert len(r.json()) >= 8   # 8 produk dari seed

def test_order_stock_validation():
    prods = client.get("/products").json()
    custs = client.get("/customers").json()
    r = client.post("/orders", json={
        "customer_id": custs[0]["id"],
        "items": [{"product_id": prods[0]["id"], "qty": 99999}]
    })
    assert r.status_code == 400   # Stok tidak cukup
```

```cmd
pytest tests/ -v
```

> ✅ **Checkpoint**: `GET /products` mengembalikan 8 produk, order dengan stok cukup berhasil dibuat, order dengan stok kurang mengembalikan HTTP 400 → Sesi 5 selesai dan siap jadi data layer untuk Sesi 6 & 7!
