import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.planner import extract_json


def test_extract_json_valid():
    text = "Berikut hasilnya:\n{\"need_tool\": true, \"tool\": \"search_knowledge\", \"query\": \"harga laptop\"}\nTerima kasih."
    j = extract_json(text)
    assert j is not None
    assert j["need_tool"] is True
    assert j["tool"] == "search_knowledge"


def test_extract_json_invalid():
    assert extract_json("ini bukan json sama sekali") is None
