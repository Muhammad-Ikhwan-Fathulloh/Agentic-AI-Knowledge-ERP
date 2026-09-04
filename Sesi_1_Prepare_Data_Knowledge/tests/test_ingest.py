import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import chunk_text, encode


def test_chunking_basic():
    text = "a " * 1000
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) >= 10
    for c in chunks:
        assert len(c.split()) <= 100


def test_embed_dimension():
    v = encode("hello world")
    assert isinstance(v, list)
    assert len(v) == 384
