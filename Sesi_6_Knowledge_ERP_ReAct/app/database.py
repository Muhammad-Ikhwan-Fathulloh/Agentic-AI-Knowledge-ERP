import os
import uuid
from datetime import datetime, timedelta

import duckdb

from app.config import settings
from app.embeddings import encode


def init_db():
    con = duckdb.connect(settings.duckdb_path)
    con.execute("INSTALL vss; LOAD vss;")
    con.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL,
        price DOUBLE NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL,
        email VARCHAR, phone VARCHAR,
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
    return con


def _seed(con: duckdb.DuckDBPyConnection):
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed = [
            ("Laptop NocBook Pro 14", 12500000, 25),
            ("Mouse Wireless NocMouse X1", 249000, 120),
            ("Keyboard Mechanical NocBoard K7", 899000, 45),
            ("Monitor 27\" NocView 4K", 5750000, 18),
            ("Headset NocSound H500", 599000, 60),
            ("Webcam NocCam Pro 1080p", 325000, 80),
            ("SSD NVMe 1TB NocStorage", 1250000, 90),
            ("RAM DDR4 16GB NocMem", 650000, 75),
        ]
        for name, price, stock in seed:
            emb = encode(name)
            con.execute(
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, current_timestamp)",
                [str(uuid.uuid4()), name, price, stock, emb],
            )
    if con.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        seed = [
            ("Budi Santoso", "budi@example.com", "081234567890"),
            ("Siti Rahayu", "siti@example.com", "081298765432"),
            ("PT. Teknologi Nusantara", "admin@nusantara.tech", "0211234567"),
        ]
        for name, email, phone in seed:
            con.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?, current_timestamp)",
                [str(uuid.uuid4()), name, email, phone],
            )


class ERPDatabase:
    def __init__(self):
        self.con = init_db()
        _seed(self.con)

    # --- Products ---
    def product_insert(self, name, price, stock):
        pid = str(uuid.uuid4())
        emb = encode(name)
        self.con.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, current_timestamp)",
            [pid, name, price, stock, emb],
        )
        return pid

    def product_list(self, name=None):
        if name:
            q_emb = encode(name)
            return self.con.execute(
                f"SELECT id, name, price, stock, array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist FROM products ORDER BY dist ASC LIMIT 10",
                [q_emb],
            ).fetchall()
        return self.con.execute("SELECT id, name, price, stock FROM products ORDER BY name").fetchall()

    def product_get(self, pid):
        return self.con.execute(
            "SELECT id, name, price, stock FROM products WHERE id=?", [pid]
        ).fetchone()

    def product_update(self, pid, name, price, stock):
        emb = encode(name)
        self.con.execute(
            "UPDATE products SET name=?, price=?, stock=?, embedding=? WHERE id=?",
            [name, price, stock, emb, pid],
        )

    def product_delete(self, pid):
        self.con.execute("DELETE FROM products WHERE id=?", [pid])

    # --- Customers ---
    def customer_insert(self, name, email=None, phone=None):
        cid = str(uuid.uuid4())
        self.con.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, current_timestamp)",
            [cid, name, email, phone],
        )
        return cid

    def customer_list(self, name=None):
        if name:
            return self.con.execute(
                "SELECT id, name, email, phone FROM customers WHERE LOWER(name) LIKE ? ORDER BY name",
                [f"%{name.lower()}%"],
            ).fetchall()
        return self.con.execute(
            "SELECT id, name, email, phone FROM customers ORDER BY name"
        ).fetchall()

    def customer_get(self, cid):
        return self.con.execute(
            "SELECT id, name, email, phone FROM customers WHERE id=?", [cid]
        ).fetchone()

    # --- Orders ---
    def order_create(self, customer_id, items):
        """items: list of dict {product_id, qty}."""
        cust = self.con.execute("SELECT id FROM customers WHERE id=?", [customer_id]).fetchone()
        if not cust:
            raise ValueError("Customer tidak ditemukan")
        total = 0.0
        prepared = []
        for it in items:
            p = self.con.execute(
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
        self.con.execute(
            "INSERT INTO orders VALUES (?, ?, 'pending', ?, current_timestamp)",
            [oid, customer_id, total],
        )
        for it in prepared:
            self.con.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)",
                [str(uuid.uuid4()), oid, it["product_id"], it["qty"], it["price"], it["subtotal"]],
            )
            self.con.execute(
                "UPDATE products SET stock = stock - ? WHERE id=?",
                [it["qty"], it["product_id"]],
            )
        return {"order_id": oid, "total_amount": total, "status": "pending"}

    def order_get(self, oid):
        order = self.con.execute("""
            SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
            FROM orders o LEFT JOIN customers c ON c.id = o.customer_id WHERE o.id=?
        """, [oid]).fetchone()
        if not order:
            return None
        items = self.con.execute("""
            SELECT oi.id, oi.product_id, p.name, oi.qty, oi.price, oi.subtotal
            FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id=?
        """, [oid]).fetchall()
        return {"order": order, "items": items}

    def order_list(self, limit=20, status=None):
        if status:
            return self.con.execute("""
                SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
                FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
                WHERE o.status = ? ORDER BY o.created_at DESC LIMIT ?
            """, [status, limit]).fetchall()
        return self.con.execute("""
            SELECT o.id, o.customer_id, c.name, o.status, o.total_amount, o.created_at
            FROM orders o LEFT JOIN customers c ON c.id = o.customer_id
            ORDER BY o.created_at DESC LIMIT ?
        """, [limit]).fetchall()

    def order_set_status(self, oid, status):
        self.con.execute("UPDATE orders SET status=? WHERE id=?", [status, oid])

    # --- Reports ---
    def sales_report(self, days=7):
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.con.execute("""
            SELECT p.name, COALESCE(SUM(oi.qty),0) qty, COALESCE(SUM(oi.subtotal),0) rev
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            JOIN orders o ON o.id = oi.order_id
            WHERE o.created_at >= ? AND o.status != 'cancelled'
            GROUP BY p.name ORDER BY rev DESC
        """, [since]).fetchall()
        total = self.con.execute("""
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

    def low_stock(self, threshold=10):
        return self.con.execute("""
            SELECT id, name, price, stock FROM products WHERE stock <= ? ORDER BY stock ASC
        """, [threshold]).fetchall()


db = ERPDatabase()
