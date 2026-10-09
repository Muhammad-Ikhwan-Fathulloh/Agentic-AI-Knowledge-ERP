"""
Test Agentic AI ERP v2 - DUAL KB (SOP + ERP Docs) + Agentic SOP→ERP Router
"""
import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

client = TestClient(app)


# ============================================================
# 1. SYSTEM
# ============================================================
class TestSystem:
    def test_root_v2_info(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == "2.0.0"
        assert "Dual Knowledge Base" in data["feature"]

    def test_health_dua_kb(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "kb_sop_chunks" in data["counts"]
        assert "kb_erp_docs_chunks" in data["counts"]
        assert data["counts"]["kb_sop_chunks"] >= 5
        assert data["counts"]["kb_erp_docs_chunks"] >= 3

    def test_stats_dua_kb(self):
        r = client.get("/stats")
        assert r.status_code == 200
        data = r.json()
        assert "kb_sop" in data["knowledge_bases"]
        assert "kb_erp_docs" in data["knowledge_bases"]
        assert "lookup_product" in str(data["agentic_router"]["supported_actions"])


# ============================================================
# 2. KB #1 — SOP
# ============================================================
class TestKBSOP:
    def test_sop_seed_ada(self):
        r = client.get("/sop/documents")
        assert r.status_code == 200
        sources = {d["source"] for d in r.json()}
        wajib = {"SOP_Klaim_Garansi", "SOP_Pengembalian_Barang_Return",
                 "SOP_Pemesanan_Pembayaran", "SOP_Pengiriman_Shipping",
                 "SOP_Stok_Kritis_Reorder", "SOP_Analisa_Penjualan"}
        assert wajib.issubset(sources), f"SOP wajib hilang: {wajib - sources}"

    def test_sop_search_garansi(self):
        r = client.post("/sop/search", json={"q": "klaim garansi NocBook", "k": 3})
        assert r.status_code == 200
        results = r.json()
        assert len(results) >= 1
        assert any("garansi" in r["content"].lower() for r in results)

    def test_sop_ingest_text(self):
        r = client.post("/sop/ingest/text", json={
            "source": "SOP_TEST_Discount_Lebaran",
            "content": (
                "SOP Discount Lebaran 2026:\n"
                "1. Periode: 1-30 April 2026.\n"
                "2. Discount 10% min belanja Rp500.000.\n"
                "3. Discount 15% min belanja Rp2.000.000.\n"
                "4. Cashback 5% via e-wallet GoPay/ShopeePay."
            ),
        })
        assert r.status_code == 200
        d = r.json()
        assert d["source"] == "SOP_TEST_Discount_Lebaran"
        assert d["total_chunks"] >= 1


# ============================================================
# 3. KB #2 — ERP DOCS
# ============================================================
class TestKBERPDocs:
    def test_erp_docs_seed_ada(self):
        r = client.get("/erp-docs/documents")
        assert r.status_code == 200
        sources = {d["source"] for d in r.json()}
        assert any("NocBook" in s for s in sources)
        assert any("Kategori" in s or "Supplier" in s for s in sources)

    def test_erp_docs_search_spesifikasi(self):
        r = client.post("/erp-docs/search", json={"q": "spesifikasi NocBook Pro 14", "k": 3})
        assert r.status_code == 200
        results = r.json()
        assert any("nocbook" in r["content"].lower() and "oled" in r["content"].lower()
                   for r in results)

    def test_erp_docs_ingest_text(self):
        r = client.post("/erp-docs/ingest/text", json={
            "source": "ERP_Info_Promo_Q4",
            "content": (
                "Promo Q4 2026 bundling NocBook + NocMouse + NocBoard = Rp13.500.000 "
                "(harga normal Rp13.648.000). Stok terbatas 500 unit nationwide."
            ),
        })
        assert r.status_code == 200
        assert r.json()["total_words"] >= 10


# ============================================================
# 4. ERP SYSTEM (CRUD + Reports)
# ============================================================
class TestERP:
    def test_products_semantic_search(self):
        r = client.get("/products", params={"name": "laptop"})
        assert r.status_code == 200
        names = [p["name"].lower() for p in r.json()]
        assert any("nocbook" in n for n in names)

    def test_full_order_flow_and_reports(self):
        custs = client.get("/customers").json()
        cid = custs[0]["id"]
        prods = client.get("/products", params={"name": "NocMouse"}).json()
        assert prods
        pid = prods[0]["id"]

        o = client.post("/orders", json={
            "customer_id": cid, "items": [{"product_id": pid, "qty": 1}]
        }).json()
        assert "order_id" in o

        client.patch(f"/orders/{o['order_id']}/status?status=completed")

        sales = client.get("/report/sales", params={"days": 30}).json()
        assert sales["period_days"] == 30
        assert isinstance(sales["total_revenue"], float)

        low = client.get("/report/low-stock", params={"threshold": 1000}).json()
        assert "products" in low


# ============================================================
# 5. AGENTIC ROUTER — SOP -> ERP (INTI FITUR BARU)
# ============================================================
class TestAgenticSOPEPR:
    def test_agentic_garansi_trigger_lookup_product(self):
        """
        Kasus: User tanya klaim garansi NocBook.
        Expected: Agent membaca SOP Klaim Garansi →
                  Router memutuskan action lookup_product (NocBook)
                  + lookup_erp_knowledge (spesifikasi)
                  → Step executed → final answer menggabung SOP + data ERP.
        """
        r = client.post("/ai/agentic/qa", json={
            "q": "Laptop NocBook Pro 14 saya layarnya pecah, bagaimana proses klaim garansinya?",
            "k": 4,
        })
        assert r.status_code == 200
        data = r.json()

        assert "question" in data
        assert "sop_context" in data
        assert len(data["sop_context"]) >= 1
        assert any("garansi" in s["source"].lower() or "klaim" in s["source"].lower()
                   for s in data["sop_context"])

        assert "plan" in data
        assert "actions" in data["plan"]
        actions = [a.get("action") for a in data["plan"]["actions"]]
        assert len(actions) >= 1, f"Actions harus >= 1, tapi: {actions}"
        assert "lookup_product" in actions or "lookup_erp_knowledge" in actions, (
            f"SOP menyebutkan perlu cek produk, seharusnya ada lookup_product / "
            f"lookup_erp_knowledge di actions. Dapat: {actions}"
        )

        assert "steps" in data
        executed = [s["action"] for s in data["steps"]]
        assert len(executed) >= 1
        for step in data["steps"]:
            assert "result" in step
            res = step["result"]
            assert res.get("status") in ("ok", "not_found", "unknown_action"), (
                f"Step {step['action']} result status tidak wajar: {res}"
            )

        assert "final_answer" in data
        assert len(data["final_answer"]) >= 30

    def test_agentic_stok_trigger_low_stock(self):
        """
        Kasus: Staf gudang tanya stok menipis.
        Expected: Agent baca SOP Stok_Kritis_Reorder → router pilih check_low_stock.
        """
        r = client.post("/ai/agentic/qa", json={
            "q": "Ada barang apa saja stoknya di bawah 25 unit? Saya perlu reorder besok.",
            "k": 4,
        })
        assert r.status_code == 200
        data = r.json()
        actions_plan = [a.get("action") for a in data["plan"]["actions"]]
        assert "check_low_stock" in actions_plan, (
            f"SOP stok seharusnya trigger check_low_stock. Dapat actions: {actions_plan}"
        )
        executed = {s["action"]: s["result"] for s in data["steps"]}
        assert "check_low_stock" in executed
        assert executed["check_low_stock"]["status"] == "ok"
        assert "threshold" in executed["check_low_stock"]
        assert executed["check_low_stock"]["threshold"] in (25, 10)

    def test_agentic_penjualan_trigger_sales_report(self):
        r = client.post("/ai/agentic/qa", json={
            "q": "Bagaimana laporan penjualan 30 hari terakhir? Sebutkan produk terlaris.",
            "k": 4,
        })
        assert r.status_code == 200
        data = r.json()
        actions = [a.get("action") for a in data["plan"]["actions"]]
        assert "check_sales_report" in actions, (
            f"SOP Analisa Penjualan seharusnya trigger check_sales_report. Dapat: {actions}"
        )
        executed = {s["action"]: s["result"] for s in data["steps"]}
        assert "check_sales_report" in executed
        assert executed["check_sales_report"]["status"] == "ok"

    def test_agentic_return_tanpa_erp_data(self):
        """
        Kasus: User hanya tanya prosedur return secara umum (tidak ada ID order).
        Expected: SOP Return → no_erp_needed + (mungkin lookup_order dengan param null).
        Jawaban CUKUP dari SOP.
        """
        r = client.post("/ai/agentic/qa", json={
            "q": "Bagaimana cara mengajukan pengembalian barang (return)?",
            "k": 4,
        })
        assert r.status_code == 200
        data = r.json()
        sources = [s["source"] for s in data["sop_context"]]
        assert any("Return" in s or "Pengembalian" in s for s in sources)
        assert data["final_answer"]

    def test_agentic_produk_untuk_beli(self):
        r = client.post("/ai/agentic/qa", json={
            "q": "Saya mau beli NocMouse X1, harganya berapa dan stoknya ready tidak?",
            "k": 4,
        })
        assert r.status_code == 200
        data = r.json()
        actions = [a.get("action") for a in data["plan"]["actions"]]
        assert "lookup_product" in actions or "lookup_erp_knowledge" in actions, (
            f"Pertanyaan produk harus lookup product / erp knowledge. Actions: {actions}"
        )
        executed = {s["action"]: s["result"] for s in data["steps"]}
        if "lookup_product" in executed:
            res = executed["lookup_product"]
            assert res["status"] == "ok"
            prods = res.get("products", [])
            assert any("NocMouse" in p.get("name", "") for p in prods)
        assert "NocMouse" in data["final_answer"] or "final_answer" in data


# ============================================================
# 6. AI GENERATOR REPORTS (backward compat)
# ============================================================
class TestAIGenerator:
    def test_sales_report_structure(self):
        r = client.post("/ai/report/sales", json={"days": 7})
        assert r.status_code == 200
        d = r.json()
        assert d["type"] == "sales_report"
        assert "narrative" in d
        assert "summary_text" in d

    def test_low_stock_report_structure(self):
        r = client.post("/ai/report/low-stock", json={"threshold": 50})
        assert r.status_code == 200
        d = r.json()
        assert d["type"] == "low_stock_report"

    def test_combined_report(self):
        r = client.get("/ai/report/combined")
        assert r.status_code == 200
        d = r.json()
        assert "sales" in d and "low_stock" in d
