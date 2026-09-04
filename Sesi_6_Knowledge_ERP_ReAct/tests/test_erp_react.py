import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.react_erp import _parse_step


def test_parse_step():
    out = (
        "Thought: Stok NocBook harus dicek dulu.\n"
        "Action: check_stock\n"
        "Action Input: {\"product_name\":\"NocBook\"}\n"
    )
    th, act, ai = _parse_step(out)
    assert act == "check_stock"
    assert "NocBook" in ai
