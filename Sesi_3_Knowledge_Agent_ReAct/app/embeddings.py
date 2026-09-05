"""
app/embeddings.py — disalin dari Sesi 2, dipakai langsung oleh database.py lokal Sesi 3.
"""
from sentence_transformers import SentenceTransformer
from app.config import settings

embed_model = SentenceTransformer(settings.embed_model)


def encode(text: str) -> list[float]:
    return embed_model.encode(text).tolist()
