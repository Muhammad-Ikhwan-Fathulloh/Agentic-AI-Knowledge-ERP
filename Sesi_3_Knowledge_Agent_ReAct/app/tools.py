"""
app/tools.py — Tool registry untuk ReAct agent.

Dual-mode:
  • USE_LOCAL_DB=true (default)  → baca/tulis langsung ke DuckDB lokal Sesi 3.
    Tidak butuh service Sesi 2 (port 8001) jalan sama sekali.
  • USE_LOCAL_DB=false           → panggil REST API Sesi 2 via HTTP (perilaku lama).

Semua tool mengembalikan STRING agar bisa dimasukkan ke prompt sebagai
Observation di ReAct loop.
"""
import json
import httpx
from app.config import settings


class KnowledgeTools:
    def __init__(self):
        self._use_local = settings.use_local_db
        if not self._use_local:
            self._client = httpx.Client(timeout=30.0)
            self._base = settings.knowledge_api_base

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _local_store(self):
        """Lazy import agar tidak circular saat testing."""
        from app.database import store
        return store

    def _http_get(self, path: str, params: dict | None = None):
        try:
            r = self._client.get(f"{self._base}{path}", params=params or {})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def _http_post(self, path: str, body: dict | None = None):
        try:
            r = self._client.post(f"{self._base}{path}", json=body or {})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Tool: search_knowledge
    # ------------------------------------------------------------------
    def search_knowledge(self, query: str, k: int = 3) -> str:
        """Mencari dokumen relevan di knowledge base. Param: query (str), k (int, default 3)."""
        if self._use_local:
            rows = self._local_store().search(query, k)
            if not rows:
                return "(tidak ada hasil)"
            lines = []
            for i, (doc_id, source, content, score) in enumerate(rows, 1):
                lines.append(
                    f"[{i}] (score={score:.4f}) Sumber: {source}\n"
                    f"    {content[:500]}"
                )
            return "\n\n".join(lines)

        # --- mode HTTP ---
        result = self._http_get("/documents/search", {"q": query, "k": k})
        if isinstance(result, list):
            lines = []
            for i, doc in enumerate(result, 1):
                lines.append(
                    f"[{i}] (score={doc.get('score', 0):.4f}) Sumber: {doc.get('source')}\n"
                    f"    {doc.get('content', '')[:500]}"
                )
            return "\n\n".join(lines) if lines else "(tidak ada hasil)"
        return f"ERROR search: {result}"

    # ------------------------------------------------------------------
    # Tool: create_document
    # ------------------------------------------------------------------
    def create_document(self, source: str, content: str) -> str:
        """Menyimpan dokumen baru ke knowledge base. Param: source (str), content (str)."""
        if self._use_local:
            doc_id = self._local_store().insert(source, content)
            return f"Berhasil tersimpan dengan ID={doc_id}"

        result = self._http_post("/documents", {"source": source, "content": content})
        if isinstance(result, dict) and "id" in result:
            return f"Berhasil tersimpan dengan ID={result['id']}"
        return f"ERROR create_document: {result}"

    # ------------------------------------------------------------------
    # Tool: list_documents
    # ------------------------------------------------------------------
    def list_documents(self, limit: int = 10) -> str:
        """Melihat daftar dokumen terbaru. Param: limit (int, default 10)."""
        if self._use_local:
            rows = self._local_store().list(limit=limit)
            if not rows:
                return "Knowledge base masih kosong."
            lines = [f"Dokumen terbaru (total ditampilkan {len(rows)}):"]
            for doc_id, source, content in rows:
                lines.append(f"- [{doc_id[:8]}...] {source}: {content[:80]}...")
            return "\n".join(lines)

        result = self._http_get("/documents", {"limit": limit})
        if isinstance(result, list):
            lines = [f"Dokumen terbaru (total {len(result)}):"]
            for d in result:
                lines.append(f"- [{d['id'][:8]}...] {d['source']}: {d['content'][:80]}...")
            return "\n".join(lines)
        return f"ERROR list: {result}"

    # ------------------------------------------------------------------
    # Dispatcher — dipanggil oleh react_loop
    # ------------------------------------------------------------------
    def call(self, action: str, action_input: str) -> str:
        """Memetakan string action + action_input ke method yang tepat."""
        action = action.strip().lower()

        if action == "search_knowledge":
            return self.search_knowledge(action_input.strip('"').strip("'"))

        if action == "list_documents":
            try:
                n = int(action_input) if action_input.strip().isdigit() else 10
            except Exception:
                n = 10
            return self.list_documents(n)

        if action == "create_document":
            try:
                obj = json.loads(action_input)
                return self.create_document(
                    obj.get("source", "user-upload"),
                    obj.get("content", ""),
                )
            except Exception:
                if "|" in action_input:
                    src, cnt = action_input.split("|", 1)
                    return self.create_document(src.strip(), cnt.strip())
                return (
                    'Format create_document salah. '
                    'Gunakan JSON: {"source":"...", "content":"..."}'
                )

        return (
            f"Tool tidak dikenal: {action}. "
            "Tool yang tersedia: search_knowledge, list_documents, create_document"
        )


tools = KnowledgeTools()
