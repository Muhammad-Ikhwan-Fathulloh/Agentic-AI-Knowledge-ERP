"""
Sesi 5 - Knowledge ERP: CRUD REST API (Port 8005)
====================================================
CRUD Produk, Customer, Order, Laporan Penjualan, Low-Stock.
"""
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import db
from app.schemas import (
    ProductIn, ProductOut, CustomerIn, CustomerOut, OrderIn,
)

app = FastAPI(title="Sesi 5 - Knowledge ERP CRUD API", version="5.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "app": "ok",
        "duckdb": settings.duckdb_path,
        "counts": {
            "products": len(db.product_list()),
            "customers": len(db.customer_list()),
            "orders": len(db.order_list()),
        },
    }


# -------- Products --------
@app.post("/products", response_model=ProductOut)
def create_product(p: ProductIn):
    pid = db.product_insert(p.name, p.price, p.stock)
    return {"id": pid, "name": p.name, "price": p.price, "stock": p.stock}


@app.get("/products", response_model=List[ProductOut])
def list_products(name: Optional[str] = None):
    rows = db.product_list(name)
    return [{"id": r[0], "name": r[1], "price": r[2], "stock": r[3]} for r in rows]


@app.get("/products/{pid}", response_model=ProductOut)
def get_product(pid: str):
    r = db.product_get(pid)
    if not r:
        raise HTTPException(404, "Product not found")
    return {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]}


@app.put("/products/{pid}", response_model=ProductOut)
def update_product(pid: str, p: ProductIn):
    if not db.product_get(pid):
        raise HTTPException(404, "Product not found")
    db.product_update(pid, p.name, p.price, p.stock)
    return {"id": pid, "name": p.name, "price": p.price, "stock": p.stock}


@app.delete("/products/{pid}")
def delete_product(pid: str):
    db.product_delete(pid)
    return {"status": "deleted", "id": pid}


# -------- Customers --------
@app.post("/customers", response_model=CustomerOut)
def create_customer(c: CustomerIn):
    cid = db.customer_insert(c.name, c.email, c.phone)
    return {"id": cid, "name": c.name, "email": c.email, "phone": c.phone}


@app.get("/customers", response_model=List[CustomerOut])
def list_customers(name: Optional[str] = None):
    rows = db.customer_list(name)
    return [{"id": r[0], "name": r[1], "email": r[2], "phone": r[3]} for r in rows]


@app.get("/customers/{cid}", response_model=CustomerOut)
def get_customer(cid: str):
    r = db.customer_get(cid)
    if not r:
        raise HTTPException(404, "Customer not found")
    return {"id": r[0], "name": r[1], "email": r[2], "phone": r[3]}


# -------- Orders --------
@app.post("/orders")
def create_order(o: OrderIn):
    try:
        return db.order_create(o.customer_id, [it.model_dump() for it in o.items])
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/orders")
def list_orders(limit: int = 20, status: Optional[str] = None):
    rows = db.order_list(limit, status)
    return [
        {"id": r[0], "customer_id": r[1], "customer_name": r[2] or "-",
         "status": r[3], "total_amount": r[4], "created_at": str(r[5])}
        for r in rows
    ]


@app.get("/orders/{oid}")
def get_order(oid: str):
    r = db.order_get(oid)
    if not r:
        raise HTTPException(404, "Order not found")
    o = r["order"]
    items = r["items"]
    return {
        "id": o[0], "customer_id": o[1], "customer_name": o[2] or "-",
        "status": o[3], "total_amount": o[4], "created_at": str(o[5]),
        "items": [
            {"id": it[0], "product_id": it[1], "product_name": it[2] or "-",
             "qty": it[3], "price": it[4], "subtotal": it[5]}
            for it in items
        ],
    }


@app.patch("/orders/{oid}/status")
def set_status(oid: str, status: str = "completed"):
    if not db.order_get(oid):
        raise HTTPException(404, "Order not found")
    db.order_set_status(oid, status)
    return {"order_id": oid, "status": status}


# -------- Reports --------
@app.get("/report/sales")
def sales_report(days: int = 7):
    return db.sales_report(days)


@app.get("/report/low-stock")
def low_stock(threshold: int = 10):
    rows = db.low_stock(threshold)
    return {
        "threshold": threshold,
        "products": [
            {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]}
            for r in rows
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
