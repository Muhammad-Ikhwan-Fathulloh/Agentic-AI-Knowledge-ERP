import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.router import _rule_fallback


def test_rule_fallback_knowledge():
    assert _rule_fallback("Apa itu SOP pengembalian?") == "knowledge"
    assert _rule_fallback("Halo selamat pagi") == "knowledge"


def test_rule_fallback_erp():
    assert _rule_fallback("Stok NocBook berapa?") == "erp"
    assert _rule_fallback("laporan penjualan mingguan") == "erp"
