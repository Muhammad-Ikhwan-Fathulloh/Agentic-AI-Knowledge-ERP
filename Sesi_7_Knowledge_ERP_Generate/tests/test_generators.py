import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.generators import _summarize_sales, _summarize_lowstock


def test_summarize_sales_nonempty():
    data = {
        "period_days": 7,
        "total_revenue": 25_000_000,
        "by_product": [
            {"product": "Laptop", "qty": 2, "revenue": 25_000_000},
        ],
    }
    s = _summarize_sales(data)
    assert "Total Revenue" in s
    assert "Laptop" in s


def test_summarize_lowstock_empty():
    s = _summarize_lowstock({"threshold": 10, "products": []})
    assert "stok aman" in s
