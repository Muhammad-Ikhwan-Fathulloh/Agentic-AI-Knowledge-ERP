import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db


def test_seed_products():
    rows = db.product_list()
    assert len(rows) >= 8, "Seed minimal 8 produk harus ada"


def test_customer_create_and_get():
    cid = db.customer_insert("Test User A", "test@a.com", "000")
    got = db.customer_get(cid)
    assert got is not None
    assert got[1] == "Test User A"


def test_order_rejects_stock_shortage():
    products = db.product_list()
    pid = products[0][0]
    current_stock = products[0][3]
    customers = db.customer_list()
    cid = customers[0][0]
    try:
        db.order_create(cid, [{"product_id": pid, "qty": current_stock + 99999}])
        assert False, "Seharusnya ValueError stok kurang"
    except ValueError:
        pass
