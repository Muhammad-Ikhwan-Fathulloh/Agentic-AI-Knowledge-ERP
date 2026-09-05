# app/embeddings.py
from sentence_transformers import SentenceTransformer
from app.config import settings

embed_model = SentenceTransformer(settings.embed_model)

def encode(text: str) -> list[float]:
    return embed_model.encode(text).tolist()