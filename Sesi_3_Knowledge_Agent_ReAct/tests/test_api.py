"""
Integration test untuk API ReAct Agent di http://127.0.0.1:8002
Jalankan server dulu: uvicorn app.main:app --port 8002
Lalu jalankan: pytest -v tests/test_api.py
"""
import pytest
import httpx


BASE_URL = "http://127.0.0.1:8002"
TIMEOUT = 60.0


# ============================================================================
# Health Check
# ============================================================================

class TestHealth:
    """Test endpoint /health."""

    def test_health_endpoint(self):
        """Test /health mengembalikan status ok."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["app"] == "ok"
        assert "llama_server_alive" in data
        assert "llama_server_ready" in data
        assert "documents_count" in data

    def test_health_has_documents_count(self):
        """Test health response memiliki jumlah dokumen."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/health")
        data = r.json()
        assert "documents_count" in data
        assert isinstance(data["documents_count"], int)


# ============================================================================
# ReAct Agent - Single Topic
# ============================================================================

class TestAgentSingleTopic:
    """Test /agent/chat dengan single topic query."""

    def test_chat_refund(self):
        """Test query tentang refund."""
        payload = {
            "query": "Apa kebijakan refund produk?",
            "max_steps": 4,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "final_answer" in data
        assert "steps" in data
        assert "total_steps" in data
        assert len(data["final_answer"]) > 5
        assert data["total_steps"] >= 1

    def test_chat_warranty(self):
        """Test query tentang garansi."""
        payload = {
            "query": "Bagaimana cara klaim garansi produk?",
            "max_steps": 4,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "final_answer" in data
        assert len(data["final_answer"]) > 0

    def test_chat_shipping(self):
        """Test query tentang pengiriman."""
        payload = {
            "query": "Berapa lama estimasi pengiriman standard?",
            "max_steps": 4,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "final_answer" in data

    def test_chat_payment(self):
        """Test query tentang pembayaran."""
        payload = {
            "query": "Metode pembayaran apa saja yang tersedia?",
            "max_steps": 4,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "final_answer" in data


# ============================================================================
# ReAct Agent - Multi Topic
# ============================================================================

class TestAgentMultiTopic:
    """Test /agent/chat dengan multi-topic query."""

    def test_multi_topic_two_topics(self):
        """Test query dengan 2 topik: garansi dan refund."""
        payload = {
            "query": "Jelaskan cara klaim garansi dan proses refund barang.",
            "max_steps": 8,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        # Multi-topik harus lebih dari 1 step
        assert data["total_steps"] >= 2, f"Multi-topik perlu minimal 2 steps, got {data['total_steps']}"
        assert len(data["final_answer"]) > 20

    def test_multi_topic_three_topics(self):
        """Test query dengan 3 topik berbeda."""
        payload = {
            "query": "Jelaskan tentang: kebijakan refund, cara klaim garansi, dan estimasi pengiriman.",
            "max_steps": 10,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert data["total_steps"] >= 2


# ============================================================================
# ReAct Agent - Edge Cases
# ============================================================================

class TestAgentEdgeCases:
    """Test edge cases untuk /agent/chat."""

    def test_empty_query(self):
        """Test query kosong."""
        payload = {
            "query": "",
            "max_steps": 2,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "final_answer" in data

    def test_special_characters(self):
        """Test query dengan karakter khusus."""
        payload = {
            "query": "Apakah bisa refund @#$%^&*() dan 1234567890?",
            "max_steps": 3,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200

    def test_unicode_emoji(self):
        """Test query dengan emoji."""
        payload = {
            "query": "Apa itu 🔄 refund? Apakah bisa klaim 📦?",
            "max_steps": 3,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200

    def test_temperature_zero(self):
        """Test dengan temperature 0 (deterministic)."""
        payload = {
            "query": "apa itu garansi?",
            "max_steps": 2,
            "temperature": 0.0,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200

    def test_max_steps_limit(self):
        """Test max_steps membatasi jumlah steps."""
        payload = {
            "query": "jelaskan refund garansi pengiriman pembayaran produk",
            "max_steps": 2,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()
        # Steps tidak boleh lebih dari max_steps
        assert data["total_steps"] <= 2


# ============================================================================
# Document CRUD Endpoints
# ============================================================================

class TestDocumentsCRUD:
    """Test /documents endpoints (kompatibel dengan Sesi 2)."""

    def test_list_documents(self):
        """Test GET /documents."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_list_documents_with_limit(self):
        """Test GET /documents dengan limit."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_create_document(self):
        """Test POST /documents."""
        payload = {
            "source": "test_api_pytest",
            "content": "Dokumen test dari API pytest integration test",
        }
        with httpx.Client(timeout=10) as client:
            r = client.post(f"{BASE_URL}/documents", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["source"] == payload["source"]
        assert data["content"] == payload["content"]
        return data["id"]

    def test_get_document(self):
        """Test GET /documents/{id}."""
        # Buat dokumen dulu
        payload = {
            "source": "test_get",
            "content": "Test get document by ID",
        }
        with httpx.Client(timeout=10) as client:
            create_r = client.post(f"{BASE_URL}/documents", json=payload)
        doc_id = create_r.json()["id"]

        # Get dokumen
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents/{doc_id}")

        assert r.status_code == 200
        data = r.json()
        assert data["id"] == doc_id
        assert data["content"] == payload["content"]

    def test_update_document(self):
        """Test PUT /documents/{id}."""
        # Buat dokumen dulu
        payload = {
            "source": "test_update",
            "content": "Content original",
        }
        with httpx.Client(timeout=10) as client:
            create_r = client.post(f"{BASE_URL}/documents", json=payload)
        doc_id = create_r.json()["id"]

        # Update dokumen
        update_payload = {
            "source": "test_update",
            "content": "Content sudah diupdate",
        }
        with httpx.Client(timeout=10) as client:
            r = client.put(f"{BASE_URL}/documents/{doc_id}", json=update_payload)

        assert r.status_code == 200
        data = r.json()
        assert data["content"] == update_payload["content"]

    def test_delete_document(self):
        """Test DELETE /documents/{id}."""
        # Buat dokumen dulu
        payload = {
            "source": "test_delete",
            "content": "Dokumen akan dihapus",
        }
        with httpx.Client(timeout=10) as client:
            create_r = client.post(f"{BASE_URL}/documents", json=payload)
        doc_id = create_r.json()["id"]

        # Delete dokumen
        with httpx.Client(timeout=10) as client:
            r = client.delete(f"{BASE_URL}/documents/{doc_id}")

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"

        # Verify deleted
        with httpx.Client(timeout=10) as client:
            get_r = client.get(f"{BASE_URL}/documents/{doc_id}")
        assert get_r.status_code == 404

    def test_get_nonexistent_document(self):
        """Test GET document yang tidak ada."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents/nonexistent-id-12345")

        assert r.status_code == 404


# ============================================================================
# Document Search
# ============================================================================

class TestDocumentSearch:
    """Test /documents/search endpoint."""

    def test_search_documents(self):
        """Test GET /documents/search."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents/search", params={"q": "refund", "k": 3})

        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_search_with_k_param(self):
        """Test search dengan parameter k (limit hasil)."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents/search", params={"q": "garansi", "k": 2})

        assert r.status_code == 200
        data = r.json()
        assert len(data) <= 2

    def test_search_empty_query(self):
        """Test search dengan query kosong."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents/search", params={"q": "", "k": 5})

        # Boleh return 200 dengan list kosong atau hasil
        assert r.status_code == 200


# ============================================================================
# Response Structure Validation
# ============================================================================

class TestResponseStructure:
    """Test struktur response sesuai schema."""

    def test_chat_response_schema(self):
        """Test /agent/chat response memiliki semua field."""
        payload = {
            "query": "apa itu refund?",
            "max_steps": 3,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)

        assert r.status_code == 200
        data = r.json()

        # Validasi field wajib
        assert "query" in data
        assert "final_answer" in data
        assert "steps" in data
        assert "total_steps" in data
        assert "domain" in data

        # Validasi steps array structure
        for step in data["steps"]:
            assert "step" in step
            assert "thought" in step
            assert "action" in step
            assert "action_input" in step
            assert "observation" in step

    def test_document_response_schema(self):
        """Test /documents response sesuai DocOut schema."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/documents", params={"limit": 1})

        if r.status_code == 200:
            data = r.json()
            if len(data) > 0:
                doc = data[0]
                assert "id" in doc
                assert "source" in doc
                assert "content" in doc


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performa API."""

    def test_response_time_single_query(self):
        """Test response time untuk query tunggal."""
        import time
        payload = {
            "query": "apa itu refund?",
            "max_steps": 2,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            start = time.time()
            r = client.post(f"{BASE_URL}/agent/chat", json=payload)
            elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 60, f"Response terlalu lama: {elapsed:.2f}s"

    def test_concurrent_requests(self):
        """Test request concurrent."""
        import concurrent.futures

        payload = {
            "query": "apa itu garansi?",
            "max_steps": 2,
            "temperature": 0.3,
        }

        def make_request():
            with httpx.Client(timeout=TIMEOUT) as client:
                return client.post(f"{BASE_URL}/agent/chat", json=payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(make_request) for _ in range(2)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Semua harus berhasil
        assert all(r.status_code == 200 for r in results)


# ============================================================================
# OpenAPI / Docs
# ============================================================================

class TestDocs:
    """Test API documentation endpoints."""

    def test_openapi_schema(self):
        """Test /openapi.json tersedia."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/openapi.json")

        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        assert "/agent/chat" in data["paths"]
        assert "/documents" in data["paths"]
        assert "/documents/search" in data["paths"]

    def test_docs_ui(self):
        """Test /docs (Swagger UI) tersedia."""
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{BASE_URL}/docs")

        assert r.status_code == 200
        assert "swagger" in r.text.lower() or "redoc" in r.text.lower()


if __name__ == "__main__":
    print("=" * 60)
    print("API Integration Tests untuk ReAct Agent")
    print("=" * 60)
    print(f"\n Pastikan server berjalan di: {BASE_URL}")
    print(" Jalankan: uvicorn app.main:app --port 8002")
    print(" lalu:    pytest -v tests/test_api.py")
    print("=" * 60)
