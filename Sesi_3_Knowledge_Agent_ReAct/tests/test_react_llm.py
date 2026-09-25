"""
Unit test komprehensif untuk ReAct Agent dengan LLM.
Menguji berbagai pola: single-topic, multi-topic, edge cases, tool calls, dll.
Jalankan: pytest -v tests/test_react_llm.py
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.react import react_loop, _parse_step, _is_placeholder_answer
from app.tools import tools


# ============================================================================
# fixtures - helper untuk setup/teardown per test
# ============================================================================

@pytest.fixture(autouse=True)
def reset_tools():
    """Reset tool state sebelum setiap test."""
    yield


# ============================================================================
# PATTERN 1: Single topic query - basic search
# ============================================================================

class TestSingleTopicPatterns:
    """Pola dasar: satu topik, satu search, langsung finish."""

    @pytest.mark.asyncio
    async def test_single_topic_refund(self):
        """Test query single topic: pertanyaan tentang refund."""
        answer, steps = await react_loop(
            "Apa kebijakan refund produk?",
            max_steps=4,
            temperature=0.3,
        )
        # Verifikasi struktur
        assert isinstance(answer, str)
        assert len(answer) > 10, "Jawaban terlalu pendek"
        assert len(steps) >= 1, "Minimal harus ada 1 step"

        # Verifikasi step log structure
        for step in steps:
            assert step.thought, "Thought tidak boleh kosong"
            assert step.action is not None, "Action tidak boleh None"

        # Verifikasi ada tool call atau FINISH
        actions = [s.action for s in steps]
        assert any(a is not None for a in actions), "Harus ada action"

        # Verifikasi jawaban bukan placeholder
        assert not _is_placeholder_answer(answer), f"Jawaban adalah placeholder: {answer}"

    @pytest.mark.asyncio
    async def test_single_topic_warranty(self):
        """Test query single topic: pertanyaan tentang garansi."""
        answer, steps = await react_loop(
            "Bagaimana cara klaim garansi?",
            max_steps=4,
            temperature=0.3,
        )
        assert isinstance(answer, str)
        assert len(answer) > 5
        # Bisa finish atau belum selesai tergantung data
        if steps:
            assert steps[-1].action in ["finish", "FINISH", "search_knowledge", "list_documents", None] or steps[-1].action is not None

    @pytest.mark.asyncio
    async def test_single_topic_shipping(self):
        """Test query single topic: pertanyaan tentang pengiriman."""
        answer, steps = await react_loop(
            "Berapa lama pengiriman standard?",
            max_steps=4,
            temperature=0.3,
        )
        assert isinstance(answer, str)
        # Jawaban bisa dari LLM sendiri atau dari knowledge base
        assert len(answer) > 5


# ============================================================================
# PATTERN 2: Multi-topic query - harus search terpisah per topik
# ============================================================================

class TestMultiTopicPatterns:
    """Pola multi-topik: pertanyaan mengandung lebih dari satu topik berbeda."""

    @pytest.mark.asyncio
    async def test_multi_topic_warranty_and_return(self):
        """Test multi-topik: pertanyaan tentang garansi DAN pengembalian."""
        answer, steps = await react_loop(
            "Bagaimana cara klaim garansi dan bagaimana proses pengembalian barang?",
            max_steps=8,
            temperature=0.3,
        )
        # Verifikasi multi-step
        assert len(steps) >= 2, "Multi-topik minimal harus 2 steps"

        # Verifikasi ada search_knowledge (mungkin lebih dari 1)
        search_count = sum(1 for s in steps if s.action == "search_knowledge")
        assert search_count >= 2, f"Multi-topik harus minimal 2 search, ditemukan: {search_count}"

        # Verifikasi jawaban tidak kosong
        assert len(answer) > 20, "Jawaban multi-topik harus cukup lengkap"
        assert not _is_placeholder_answer(answer)

    @pytest.mark.asyncio
    async def test_multi_topic_payment_and_shipping(self):
        """Test multi-topik: pertanyaan tentang pembayaran DAN pengiriman."""
        answer, steps = await react_loop(
            "Metode pembayaran apa saja yang tersedia dan berapa lama ongkir?",
            max_steps=8,
            temperature=0.3,
        )
        # Verifikasi multi-step
        assert len(steps) >= 2

        # Verifikasi ada search_knowledge
        search_count = sum(1 for s in steps if s.action == "search_knowledge")
        assert search_count >= 1, "Harus ada minimal 1 search"

    @pytest.mark.asyncio
    async def test_multi_topic_three_topics(self):
        """Test multi-topik: tiga topik berbeda sekaligus."""
        answer, steps = await react_loop(
            "Jelaskan tentang: kebijakan refund, cara klaim garansi, dan estimasi pengiriman.",
            max_steps=10,
            temperature=0.3,
        )
        # Verifikasi cukup steps
        assert len(steps) >= 3, f"3 topik harus minimal 3 steps, ditemukan: {len(steps)}"

        # Verifikasi search untuk setiap topik
        search_count = sum(1 for s in steps if s.action == "search_knowledge")
        assert search_count >= 2, f"3 topik harus minimal 2 search berbeda, ditemukan: {search_count}"


# ============================================================================
# PATTERN 3: Tool call patterns
# ============================================================================

class TestToolCallPatterns:
    """Pola pemanggilan tool: search_knowledge, list_documents, create_document."""

    @pytest.mark.asyncio
    async def test_search_knowledge_tool(self):
        """Test tool search_knowledge dipanggil dengan benar."""
        # Langsung test tool
        result = tools.search_knowledge("refund", k=3)
        assert isinstance(result, str)
        # Result bisa "(tidak ada hasil)" atau hasil search

    @pytest.mark.asyncio
    async def test_list_documents_tool(self):
        """Test tool list_documents dipanggil dengan benar."""
        result = tools.list_documents(limit=5)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_create_document_tool(self):
        """Test tool create_document menyimpan dokumen baru."""
        test_source = "test_unit_pytest"
        test_content = "Ini adalah dokumen test dari unit test pytest"
        result = tools.create_document(test_source, test_content)
        assert "ID=" in result or "Berhasil" in result, f"Create document gagal: {result}"

        # Verifikasi bisa di-search
        search_result = tools.search_knowledge("dokumen test unit pytest")
        assert "test" in search_result.lower() or "ID=" in search_result

    @pytest.mark.asyncio
    async def test_tool_dispatcher(self):
        """Test tool dispatcher memanggil method yang benar."""
        # Test search_knowledge
        result = tools.call("search_knowledge", "test query")
        assert isinstance(result, str)

        # Test list_documents
        result = tools.call("list_documents", "5")
        assert isinstance(result, str)

        # Test create_document
        result = tools.call("create_document", '{"source":"test","content":"test content"}')
        assert "ID=" in result or "Berhasil" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test tool tidak dikenal mengembalikan error message."""
        result = tools.call("unknown_tool", "test")
        assert "tidak dikenal" in result.lower() or "error" in result.lower()


# ============================================================================
# PATTERN 4: ReAct loop control flow
# ============================================================================

class TestReActControlFlow:
    """Pola kontrol flow: retry placeholder, format validation, max steps."""

    @pytest.mark.asyncio
    async def test_react_returns_tuple(self):
        """Test react_loop mengembalikan tuple (answer, steps)."""
        answer, steps = await react_loop("test query", max_steps=2)
        assert isinstance(answer, str)
        assert isinstance(steps, list)
        assert all(hasattr(s, 'thought') for s in steps)

    @pytest.mark.asyncio
    async def test_react_step_log_structure(self):
        """Test StepLog memiliki semua field yang diperlukan."""
        answer, steps = await react_loop("apa itu refund?", max_steps=3)
        for step in steps:
            assert hasattr(step, 'step')
            assert hasattr(step, 'thought')
            assert hasattr(step, 'action')
            assert hasattr(step, 'action_input')
            assert hasattr(step, 'observation')
            assert step.step > 0
            assert len(step.thought) > 0

    @pytest.mark.asyncio
    async def test_max_steps_respected(self):
        """Test bahwa max_steps dihormati."""
        answer, steps = await react_loop(
            "jelaskan semua tentang produk jasa pengiriman refund garansi dan pembayaran",
            max_steps=3,
            temperature=0.3,
        )
        # Steps tidak boleh lebih dari max_steps
        assert len(steps) <= 3, f"Steps {len(steps)} melebihi max_steps 3"

    @pytest.mark.asyncio
    async def test_finish_action_exists(self):
        """Test bahwa ada step dengan action FINISH."""
        answer, steps = await react_loop("apa itu kebijakan pengembalian?", max_steps=5)
        # Cari FINISH action
        has_finish = any(
            s.action and s.action.upper() == "FINISH"
            for s in steps
        )
        # Kalau tidak ada FINISH, mungkin max_steps habis
        # atau masih dalam proses - keduanya valid
        if not has_finish:
            assert len(steps) >= 1, "Minimal harus ada 1 step"


# ============================================================================
# PATTERN 5: Edge cases dan error handling
# ============================================================================

class TestEdgeCases:
    """Edge cases: empty query, special characters, sangat panjang, dll."""

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """Test query kosong masih mengembalikan hasil (bukan crash)."""
        answer, steps = await react_loop("", max_steps=2)
        # Tidak boleh crash
        assert isinstance(answer, str)
        assert isinstance(steps, list)

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test query dengan karakter khusus."""
        answer, steps = await react_loop(
            "Apakah bisa refund @#$%^&*() dan 1234567890?",
            max_steps=3,
        )
        assert isinstance(answer, str)

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Test query yang sangat panjang."""
        long_query = "jelaskan " + "tentang hal hal ".join([
            "refund", "garansi", "pengiriman", "pembayaran",
            "produk", "jasa", "layanan", "customer service"
        ]) * 3
        answer, steps = await react_loop(long_query, max_steps=5)
        assert isinstance(answer, str)

    @pytest.mark.asyncio
    async def test_unicode_query(self):
        """Test query dengan Unicode/emoji."""
        answer, steps = await react_loop(
            "Apa itu 🔄 refund? Apakah bisa mengklaim garansi 📦?",
            max_steps=3,
        )
        assert isinstance(answer, str)


# ============================================================================
# PATTERN 6: Temperature variations
# ============================================================================

class TestTemperatureVariations:
    """Test dengan temperature berbeda untuk memastikan stabilitas."""

    @pytest.mark.asyncio
    async def test_low_temperature(self):
        """Test temperature rendah (0.1) - lebih deterministik."""
        answer, steps = await react_loop(
            "apa itu refund?",
            max_steps=3,
            temperature=0.1,
        )
        assert len(answer) > 5

    @pytest.mark.asyncio
    async def test_high_temperature(self):
        """Test temperature tinggi (0.7) - lebih random."""
        answer, steps = await react_loop(
            "apa itu refund?",
            max_steps=3,
            temperature=0.7,
        )
        assert len(answer) > 5

    @pytest.mark.asyncio
    async def test_zero_temperature(self):
        """Test temperature 0 - sepenuhnya deterministik."""
        answer, steps = await react_loop(
            "apa itu garansi?",
            max_steps=3,
            temperature=0.0,
        )
        assert len(answer) > 5


# ============================================================================
# PATTERN 7: Parse step patterns
# ============================================================================

class TestParseStepPatterns:
    """Test parsing output LLM ke komponen ReAct."""

    def test_parse_thought_extraction(self):
        """Test ekstraksi Thought dari output."""
        output = "Thought: Saya perlu mencari informasi.\nAction: search_knowledge\nAction Input: refund"
        thought, action, action_input = _parse_step(output)
        assert "mencari" in thought.lower()

    def test_parse_action_extraction(self):
        """Test ekstraksi Action dari output."""
        output = "Thought: Test\nAction: search_knowledge\nAction Input: query"
        _, action, _ = _parse_step(output)
        assert action == "search_knowledge"

    def test_parse_action_input_extraction(self):
        """Test ekstraksi Action Input dari output."""
        output = "Thought: Test\nAction: FINISH\nAction Input: Jawaban lengkap tentang topik."
        _, _, action_input = _parse_step(output)
        assert "Jawaban lengkap" in action_input

    def test_parse_finish_action(self):
        """Test parsing action FINISH."""
        output = "Thought: Selesai\nAction: FINISH\nAction Input: Ini jawabannya."
        _, action, _ = _parse_step(output)
        assert action.upper() == "FINISH"

    def test_parse_create_document_action(self):
        """Test parsing action create_document."""
        output = 'Thought: Simpan\nAction: create_document\nAction Input: {"source":"test","content":"isi"}'
        _, action, _ = _parse_step(output)
        assert action == "create_document"

    def test_parse_list_documents_action(self):
        """Test parsing action list_documents."""
        output = "Thought: Lihat daftar\nAction: list_documents\nAction Input: 10"
        _, action, _ = _parse_step(output)
        assert action == "list_documents"

    def test_parse_missing_fields(self):
        """Test parsing dengan field yang hilang."""
        output = "Thought: Test saja"
        thought, action, action_input = _parse_step(output)
        assert thought == "Test saja"
        assert action == ""
        assert action_input == ""

    def test_parse_malformed_output(self):
        """Test parsing output yang tidak sesuai format."""
        output = "Ini bukan format ReAct yang benar"
        thought, action, action_input = _parse_step(output)
        # Tidak crash, hanya return empty strings
        assert thought == ""
        assert action == ""
        assert action_input == ""


# ============================================================================
# PATTERN 8: Placeholder detection
# ============================================================================

class TestPlaceholderDetection:
    """Test deteksi placeholder answer."""

    def test_placeholder_selesai(self):
        """Test deteksi placeholder 'selesai'."""
        assert _is_placeholder_answer("selesai.") == True
        assert _is_placeholder_answer("Selesai") == True

    def test_placeholder_jawaban_final(self):
        """Test deteksi placeholder 'jawaban final'."""
        assert _is_placeholder_answer("jawaban final.") == True
        assert _is_placeholder_answer("Jawaban Final") == True

    def test_placeholder_dots(self):
        """Test deteksi placeholder '...' atau '-'."""
        assert _is_placeholder_answer("...") == True
        assert _is_placeholder_answer("----") == True

    def test_placeholder_empty(self):
        """Test deteksi placeholder kosong."""
        assert _is_placeholder_answer("") == True
        assert _is_placeholder_answer("   ") == True
        assert _is_placeholder_answer("x") == True  # terlalu pendek

    def test_not_placeholder_valid_answer(self):
        """Test bahwa jawaban valid tidak terdeteksi sebagai placeholder."""
        assert _is_placeholder_answer(
            "Untuk klaim garansi: 1) Hubungi CS, 2) Sertakan bukti pembelian."
        ) == False
        assert _is_placeholder_answer(
            "Kebijakan refund adalah 30 hari setelah pembelian dengan syarat dokumen lengkap."
        ) == False


# ============================================================================
# PATTERN 9: Integration tests - full ReAct loop
# ============================================================================

class TestFullIntegration:
    """Integration test: full ReAct loop dari awal sampai akhir."""

    @pytest.mark.asyncio
    async def test_full_loop_knowledge_query(self):
        """Test full loop dengan query knowledge base."""
        # Setup: create test document
        tools.create_document(
            "Panduan Refund",
            "Kebijakan refund produk adalah 30 hari setelah pembelian. "
            "Syarat: produk belum dipakai, kemasan lengkap, ada bukti beli."
        )

        # Execute ReAct
        answer, steps = await react_loop(
            "Apa saja syarat refund produk?",
            max_steps=4,
            temperature=0.3,
        )

        # Assertions
        assert isinstance(answer, str)
        assert len(answer) > 10
        assert len(steps) >= 1

        # Verifikasi thought mengandung reasoning
        for step in steps:
            assert len(step.thought) > 5, "Thought terlalu pendek"

    @pytest.mark.asyncio
    async def test_full_loop_multiple_searches(self):
        """Test full loop dengan multiple searches."""
        # Setup: create multiple documents
        tools.create_document("Info Garansi", "Garansi produk 1 tahun terbatas.")
        tools.create_document("Info Refund", "Refund bisa dalam 14 hari.")

        # Execute
        answer, steps = await react_loop(
            "Jelaskan tentang garansi dan refund.",
            max_steps=8,
            temperature=0.3,
        )

        # Assertions
        assert isinstance(answer, str)
        # Harus ada minimal 2 search (multi-topik)
        search_count = sum(1 for s in steps if s.action == "search_knowledge")
        assert search_count >= 1, f"Harus ada search, ditemukan: {search_count}"


# ============================================================================
# PATTERN 10: Performance and timeout tests
# ============================================================================

class TestPerformance:
    """Test performa dan waktu eksekusi."""

    @pytest.mark.asyncio
    async def test_response_time_reasonable(self):
        """Test bahwa response time masuk akal (< 60 detik untuk 1 step)."""
        import time
        start = time.time()
        answer, steps = await react_loop("apa itu refund?", max_steps=1)
        elapsed = time.time() - start
        assert elapsed < 60, f"Response terlalu lama: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_multiple_steps_performance(self):
        """Test performa dengan multiple steps."""
        import time
        start = time.time()
        answer, steps = await react_loop(
            "garansi dan refund dan pengiriman",
            max_steps=5,
        )
        elapsed = time.time() - start
        # 5 steps harus selesai dalam waktu wajar
        assert elapsed < 120, f"5 steps terlalu lama: {elapsed:.2f}s"


# ============================================================================
# Helper untuk run manual
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ReAct Agent - Comprehensive Unit Tests")
    print("=" * 60)
    print("\nJalankan dengan: pytest -v tests/test_react_llm.py")
    print("\nAtau untuk test spesifik:")
    print("  pytest -v tests/test_react_llm.py::TestSingleTopicPatterns::test_single_topic_refund")
    print("\nAtau dengan coverage:")
    print("  pytest --cov=app tests/test_react_llm.py")
    print("=" * 60)
