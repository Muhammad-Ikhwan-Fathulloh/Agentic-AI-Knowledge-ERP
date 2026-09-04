import httpx
from app.config import settings


class KnowledgeTools:
    """
    Tool registry yang memanggil Knowledge Agent REST API (Sesi 2, port 8001).
    Semua tool mengembalikan STRING (tekstual) agar bisa dimasukkan ke prompt
    sebagai Observation di ReAct loop.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.knowledge_api_base
        self.client = httpx.Client(timeout=30.0)

    def _get(self, path: str, params: dict | None = None):
        try:
            r = self.client.get(f"{self.base_url}{path}", params=params or {})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path: str, json_body: dict | None = None):
        try:
            r = self.client.post(f"{self.base_url}{path}", json=json_body or {})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Tool: search_knowledge
    # ------------------------------------------------------------------
    def search_knowledge(self, query: str, k: int = 3) -> str:
        """Mencari dokumen relevan di knowledge base. Param: query (str), k (int, default 3)."""
        result = self._get("/documents/search", {"q": query, "k": k})
        if isinstance(result, list):
            lines = []
            for i, doc in enumerate(result, 1):
                score = doc.get("score", 0)
                lines.append(
                    f"[{i}] (score={score:.4f}) Sumber: {doc.get('source')}\n"
                    f"    {doc.get('content', '')[:500]}"
                )
            return "\n\n".join(lines) if lines else "(tidak ada hasil)"
        return f"ERROR search: {result}"

    # ------------------------------------------------------------------
    # Tool: create_document
    # ------------------------------------------------------------------
    def create_document(self, source: str, content: str) -> str:
        """Menyimpan dokumen baru ke knowledge base. Param: source (str), content (str)."""
        result = self._post("/documents", {"source": source, "content": content})
        if isinstance(result, dict) and "id" in result:
            return f"Berhasil tersimpan dengan ID={result['id']}"
        return f"ERROR create_document: {result}"

    # ------------------------------------------------------------------
    # Tool: list_documents
    # ------------------------------------------------------------------
    def list_documents(self, limit: int = 10) -> str:
        """Melihat daftar dokumen terbaru. Param: limit (int, default 10)."""
        result = self._get("/documents", {"limit": limit})
        if isinstance(result, list):
            lines = [f"Dokumen terbaru (total {len(result)}):"]
            for d in result:
                lines.append(f"- [{d['id'][:8]}...] {d['source']}: {d['content'][:80]}...")
            return "\n".join(lines)
        return f"ERROR list: {result}"

    def call(self, action: str, action_input: str) -> str:
        """
        Memetakan string action + action_input (tekstual) ke method yang tepat.
        Regex parser dari main.py akan memanggil fungsi ini.
        """
        action = action.strip().lower()
        if action == "search_knowledge":
            return self.search_knowledge(action_input.strip('"').strip("'"))
        if action == "list_documents":
            try:
                n = int(action_input) if action_input.strip().isdigit() else 10
                return self.list_documents(n)
            except Exception:
                return self.list_documents()
        if action == "create_document":
            try:
                import json as _json
                obj = _json.loads(action_input)
                return self.create_document(
                    obj.get("source", "user-upload"),
                    obj.get("content", ""),
                )
            except Exception:
                if "|" in action_input:
                    src, cnt = action_input.split("|", 1)
                    return self.create_document(src.strip(), cnt.strip())
                return "Format create_document salah. Gunakan JSON: {\"source\":\"...\", \"content\":\"...\"}"
        return f"Tool tidak dikenal: {action}. Tool yang tersedia: search_knowledge, list_documents, create_document"


tools = KnowledgeTools()
