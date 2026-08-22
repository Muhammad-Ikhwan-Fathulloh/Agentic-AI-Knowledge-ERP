# app/database.py (bagian DuckDB)
import duckdb, uuid
from app.config import settings
from app.embeddings import encode

def init_duckdb():
    con = duckdb.connect(settings.duckdb_path)
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS documents (
        id VARCHAR PRIMARY KEY, source VARCHAR, content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    return con

class DocStore:
    def __init__(self):
        self.backend = "duckdb"
        self.con = init_duckdb()

    def insert(self, source: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        emb = encode(content)
        self.con.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
                [doc_id, source, content, emb],
            )

        return doc_id

    def get(self, doc_id: str):
        row = self.con.execute(
                "SELECT id, source, content FROM documents WHERE id=?", [doc_id]
            ).fetchone()
        return row

    def list(self, limit: int = 20, offset: int = 0):
        return self.con.execute(
                "SELECT id, source, content FROM documents LIMIT ? OFFSET ?",
                [limit, offset],
            ).fetchall()

    def update(self, doc_id: str, source: str, content: str):
        emb = encode(content)
        self.con.execute(
                "UPDATE documents SET content=?, source=?, embedding=? WHERE id=?",
                [content, source, emb, doc_id],
            )

    def delete(self, doc_id: str):
        self.con.execute("DELETE FROM documents WHERE id=?", [doc_id])

    def search(self, query: str, k: int = 5):
        q_emb = encode(query)
        return self.con.execute(f"""
                SELECT id, source, content, array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
                FROM documents ORDER BY dist ASC LIMIT ?
            """, [q_emb, k]).fetchall()

store = DocStore()