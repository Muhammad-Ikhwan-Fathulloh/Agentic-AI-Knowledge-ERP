from sentence_transformers import SentenceTransformer

from app.config import settings

_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(settings.embed_model)
    return _embed_model


def encode(text: str) -> list[float]:
    return get_embed_model().encode(text).tolist()
