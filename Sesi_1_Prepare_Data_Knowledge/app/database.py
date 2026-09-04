import uuid
import duckdb
from sentence_transformers import SentenceTransformer

from app.config import settings

embed_model = SentenceTransformer(settings.embed_model)


def encode(text: str) -> list[float]:
    return embed_model.encode(text).tolist()


_state_con = {"con": None}


def get_con():
    if _state_con["con"] is None:
        _state_con["con"] = duckdb.connect(settings.duckdb_path)
    return _state_con["con"]


def init_db():
    con = get_con()
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS documents (
        id VARCHAR PRIMARY KEY,
        source VARCHAR,
        content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_emb ON documents USING HNSW (embedding);")
    except Exception:
        pass
    return con


def close_db():
    if _state_con["con"] is not None:
        _state_con["con"].close()
        _state_con["con"] = None


# ---------- Chunking ----------
def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    words = text.split()
    chunks: list[str] = []
    step = size - overlap
    if step <= 0:
        step = size
    for i in range(0, max(len(words), 1), step):
        chunk_words = words[i : i + size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
    return chunks


# ---------- CRUD dasar ----------
def insert_document(source: str, content: str) -> str:
    con = get_con()
    doc_id = str(uuid.uuid4())
    emb = encode(content)
    con.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
        [doc_id, source, content, emb],
    )
    return doc_id


def insert_chunks(source: str, chunks: list[str]) -> list[str]:
    ids = []
    for chunk in chunks:
        if chunk.strip():
            ids.append(insert_document(source, chunk))
    return ids


def search(query: str, k: int = 5) -> list:
    con = get_con()
    emb = encode(query)
    return con.execute(f"""
        SELECT id, source, content,
               array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
        FROM documents ORDER BY dist ASC LIMIT ?
    """, [emb, k]).fetchall()


def count() -> int:
    con = get_con()
    return con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def list_all(limit: int = 50) -> list:
    con = get_con()
    return con.execute(
        "SELECT id, source, content FROM documents ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()


def delete_all() -> int:
    con = get_con()
    n = count()
    con.execute("DELETE FROM documents")
    return n
