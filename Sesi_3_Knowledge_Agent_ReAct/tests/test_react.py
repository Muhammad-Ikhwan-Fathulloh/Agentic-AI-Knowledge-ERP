"""
Unit test sederhana untuk parser ReAct dan tool registry (TIDAK butuh LLM nyala).
Jalankan: pytest -v tests/test_react.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.react import _parse_step


def test_parse_step_normal():
    output = (
        "Thought: Saya perlu mencari informasi tentang refund.\n"
        "Action: search_knowledge\n"
        "Action Input: kebijakan refund produk\n"
    )
    th, act, ai = _parse_step(output)
    assert "refund" in th.lower()
    assert act == "search_knowledge"
    assert "refund" in ai.lower()


def test_parse_step_finish():
    output = (
        "Thought: Saya sudah punya jawaban final.\n"
        "Action: FINISH\n"
        "Action Input: Kebijakan refund adalah 30 hari setelah pembelian.\n"
    )
    th, act, ai = _parse_step(output)
    assert act.upper() == "FINISH"
    assert "30 hari" in ai
