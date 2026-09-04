import os
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
    CREATE TABLE IF NOT EXISTS semantic_cache (
        id VARCHAR PRIMARY KEY,
        prompt TEXT,
        response TEXT,
        domain VARCHAR,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS interactions (
        interaction_id VARCHAR PRIMARY KEY,
        query TEXT,
        answer TEXT,
        domain VARCHAR,
        router_confidence VARCHAR,
        feedback BOOLEAN,
        cached BOOLEAN DEFAULT false,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_cache_emb ON semantic_cache USING HNSW (embedding);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_inter_emb ON interactions USING HNSW (embedding);")
    except Exception:
        pass


# ---- Semantic Cache ----
def cache_lookup(query: str, threshold: float | None = None):
    threshold = threshold or settings.semantic_cache_threshold
    con = get_con()
    emb = encode(query)
    row = con.execute(f"""
        SELECT response, domain, array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
        FROM semantic_cache ORDER BY dist ASC LIMIT 1
    """, [emb]).fetchone()
    if row and row[2] <= threshold:
        return {"response": row[0], "domain": row[1], "distance": row[2]}
    return None


def cache_store(query: str, response: str, domain: str):
    con = get_con()
    emb = encode(query)
    cid = str(uuid.uuid4())
    con.execute(f"""
        INSERT INTO semantic_cache VALUES (?, ?, ?, ?, ?, current_timestamp)
    """, [cid, query, response, domain, emb])
    return cid


# ---- Interactions / Feedback ----
def interaction_store(query, answer, domain, router_confidence="unknown", cached=False):
    con = get_con()
    emb = encode(query)
    iid = str(uuid.uuid4())
    con.execute(f"""
        INSERT INTO interactions (interaction_id, query, answer, domain,
                                   router_confidence, feedback, cached, embedding, created_at)
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, current_timestamp)
    """, [iid, query, answer, domain, router_confidence, cached, emb])
    return iid


def interaction_set_feedback(interaction_id: str, is_like: bool):
    con = get_con()
    con.execute(
        "UPDATE interactions SET feedback = ? WHERE interaction_id = ?",
        [is_like, interaction_id],
    )
    row = con.execute(
        "SELECT interaction_id, query, domain, feedback FROM interactions WHERE interaction_id = ?",
        [interaction_id],
    ).fetchone()
    return row


def interaction_stats():
    con = get_con()
    total = con.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    likes = con.execute("SELECT COUNT(*) FROM interactions WHERE feedback = true").fetchone()[0]
    dislikes = con.execute("SELECT COUNT(*) FROM interactions WHERE feedback = false").fetchone()[0]
    cached = con.execute("SELECT COUNT(*) FROM semantic_cache").fetchone()[0]
    return {
        "total_interactions": total,
        "likes": likes,
        "dislikes": dislikes,
        "cache_entries": cached,
    }
