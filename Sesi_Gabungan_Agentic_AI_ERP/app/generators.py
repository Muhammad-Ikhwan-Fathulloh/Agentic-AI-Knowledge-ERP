import json
from app.llm import llm_complete
from app.database import (
    report_sales, report_low_stock,
    p_list, c_list, o_get, erpdoc_search, sop_search,
)
from app.config import settings

# ======================================================================
# PROMPTS
# ======================================================================
ROUTER_PROMPT = """Kamu adalah ROUTER AGENT di sistem Agentic AI ERP NocStore.

TUGAS UTAMA:
1. Baca SOP (Standar Operasional Prosedur) yang relevan dengan pertanyaan user DI BAWAH INI.
2. Berdasarkan SOP tersebut, TENTUKAN ACTION ERP apa saja yang HARUS dijalankan agar bisa memberikan jawaban lengkap ke user.
3. Setiap action punya parameter (jika perlu).
4. MAKSIMAL 3 actions. Prioritaskan action yang PALING relevan menurut SOP.

=== DAFTAR ACTION ERP YANG TERSEDIA ===
- lookup_product      : Cari data produk (nama, harga, stok) dari tabel products ERP.
                       PARAM (param): kata kunci nama produk (misal: "NocBook", "NocMouse").
                       Digunakan jika SOP menyebutkan perlu cek produk / stok / harga.
- check_low_stock     : Daftar produk dengan stok <= threshold.
                       PARAM (param): angka threshold (default 10).
                       Digunakan jika SOP menyebut stok menipis / reorder.
- check_sales_report  : Laporan penjualan (total revenue, by product) N hari terakhir.
                       PARAM (param): jumlah hari (default 7).
                       Digunakan jika SOP menyebut analisa penjualan / produk terlaris.
- lookup_customer     : Cari data customer berdasarkan nama / email.
                       PARAM (param): kata kunci nama / email customer.
                       Digunakan jika SOP menyebut butuh data customer.
- lookup_order        : Detail order (status, items, total) berdasarkan order_id.
                       PARAM (param): order_id (jika user menyebutkan).
- lookup_erp_knowledge: Cari pengetahuan pendukung di KB ERP (spesifikasi produk, supplier, lead time).
                       PARAM (param): kata kunci pencarian (misal: "NocBook spesifikasi", "supplier").
                       Digunakan jika pertanyaan tentang spesifikasi detail / info master data.
- no_erp_needed       : Jika jawaban CUKUP dari SOP saja, TIDAK perlu ambil data ERP.
                       PARAM (param): null / kosongkan.

=== PERTANYAAN USER ===
{question}

=== SOP TERKAIT YANG DITEMUKAN ===
{sop_context}

=== FORMAT OUTPUT WAJIB ===
HANYA OUTPUT JSON VALID, TIDAK ADA TEKS LAINNYA, TIDAK ADA TAMBOHAN KALIMAT APAPUN.
Struktur JSON:
{{
  "actions": [
    {{"action": "nama_action", "param": "parameter string ATAU null", "reason": "kalimat singkat mengapa action ini dipilih (dari SOP)"}}
  ],
  "sop_summary": "Ringkasan SOP yang relevan dengan jawaban user, 2-3 kalimat."
}}

Contoh jawaban jika user tanya stok NocBook:
{{
  "actions": [
    {{"action": "lookup_product", "param": "NocBook", "reason": "SOP Klaim Garansi menyebutkan perlu lookup produk untuk cek kategori stok."}},
    {{"action": "lookup_erp_knowledge", "param": "NocBook spesifikasi", "reason": "User tanya tentang produk NocBook, perlu dukungan spesifikasi."}}
  ],
  "sop_summary": "Untuk klaim garansi, customer harus menghubungi CS WA dengan serial number dan foto keluhan. DOA (7 hari) diganti unit baru gratis, sisanya kirim ke service center."
}}

SEKARANG, KELUARKAN HANYA JSON:
"""

FINAL_ANSWER_PROMPT = """Kamu adalah Customer Service Agent PROFESIONAL di NocStore (toko online perangkat keras komputer).

Berikut adalah data yang kamu punya untuk menjawab user:
A) SOP YANG RELEVAN (ringkasan):
{sop_summary}

B) RINCIAN SOP ASLI (untuk pastikan kamu tidak salah):
{sop_detail}

C) DATA ERP YANG TELAH DIAMBIL BERDASARKAN PETUNJUK SOP:
{erp_results}

D) PERTANYAAN USER:
{question}

=== INSTRUKSI MENJAWAB ===
1. Jawab dalam BAHASA INDONESIA yang ramah dan jelas.
2. AWAL jawaban: sebutkan poin SOP yang relevan (misal: "Sesuai SOP klaim garansi NocStore: ...").
3. TENGAH jawaban: sisipkan DATA ERP yang relevan (harga, stok, nama produk, dll) JIKA ADA.
4. AKHIR jawaban: berikan ACTION ITEM / NEXT STEP yang jelas untuk user.
5. JANGAN mengarang data. Jika data ERP tidak lengkap, katakan "Informasi terkait [X] saat ini belum tersedia di sistem, silakan hubungi CS WA +62-811-0000-123".
6. JANGAN menyebut "menurut router" atau istilah teknis internal. Jawab seolah kamu CS sungguhan.

Jawaban (maksimal 8 kalimat, padat & jelas):
"""

SALES_PROMPT = """Kamu adalah ANALIS BISNIS senior di toko online retail.
Berikut adalah DATA PENJUALAN {days} hari TERAKHIR dalam format teks:
{data_summary}

TULIS LAPORAN EKSEKUTIF dalam BAHASA INDONESIA FORMAL, TEPAT 4 PARAGRAF:
Paragraf 1: Ringkasan total pendapatan dan performa umum.
Paragraf 2: Analisis 3 produk terlaris (jika ada < 3, sebutkan semua) - sertakan unit terjual & kontribusi revenue.
Paragraf 3: Tren yang terlihat (misal: produk teknologi tinggi laku, aksesoris stabil, dsb) - JANGAN mengarang data, simpulkan hanya dari angka yang ada.
Paragraf 4: SATU rekomendasi BISNIS YANG ACTIONABLE (spesifik, bukan umum) + alasan singkat mengapa masuk akal.

JANGAN menuliskan judul, JANGAN ulang angka mentah, langsung ke narasi analisis.
Laporan:"""

LOW_STOCK_PROMPT = """Kamu adalah manajer logistik. Berikut daftar PRODUK DENGAN STOK <= {threshold}:
{data_summary}

Buat NOTULENSI SINGKAT BAHASA INDONESIA maksimal 6 kalimat:
1. Jumlah total SKU yang perlu perhatian.
2. Sebutkan 3 produk dengan stok terendah beserta sisa unitnya.
3. Dampak jika tidak segera restock.
4. Usulan kuantitas restock (kira-kira: stok target 2x dari rata-rata penjualan, atau jika tidak ada data, usulkan angka masuk akal berdasarkan harga).
5. Prioritas: sebutkan produk mana yang harus diproses HARI INI.
6. Penutup: next step yang jelas.

Notulensi:"""

KNOWLEDGE_QA_PROMPT = """Kamu adalah Customer Service Agent yang ramah dan ahli di toko online NocStore.
Berikut adalah KONTEK (potensi jawaban) dari knowledge base yang relevan dengan pertanyaan pengguna:

{context}

PERTANYAAN PENGGUNA: {question}

INSTRUKSI:
1. Jawab dalam BAHASA INDONESIA yang ramah dan jelas.
2. HANYA gunakan informasi dari KONTEK di atas. Jika jawaban tidak ada di KONTEK, katakan dengan jujur:
   "Maaf, saya belum menemukan informasi yang tepat untuk pertanyaan Anda. Silakan hubungi CS kami untuk bantuan lebih lanjut."
3. JANGAN mengarang data atau asumsi di luar konteks.
4. Jika pertanyaan berkaitan dengan SOP / prosedur, jabarkan langkah-langkahnya secara runtut.

Jawaban:"""


# ======================================================================
# HELPER SUMMARIZERS
# ======================================================================
def _summarize_sales(data):
    lines = [f"Total Revenue: Rp{data.get('total_revenue', 0):,.0f}"]
    lines.append(f"Periode: {data.get('period_days', 0)} hari terakhir")
    lines.append("Detail per Produk:")
    for p in data.get("by_product", []):
        lines.append(
            f"  - {p['product']}: {p['qty']} unit, Rp{p['revenue']:,.0f} "
            f"(share: {(p['revenue'] / max(data.get('total_revenue', 1), 1)) * 100:.1f}%)"
        )
    if not data.get("by_product"):
        lines.append("  (belum ada transaksi dalam periode ini)")
    return "\n".join(lines)


def _summarize_lowstock(data):
    lines = [f"Threshold stok: <= {data.get('threshold', 0)} unit"]
    lines.append(f"Jumlah SKU: {len(data.get('products', []))}")
    for p in data.get("products", []):
        lines.append(f"  - {p['name']} (ID {p['id'][:8]}): stok={p['stock']}, harga=Rp{p['price']:,.0f}")
    if not data.get("products"):
        lines.append("  (semua produk stok aman - tidak ada yang di bawah threshold)")
    return "\n".join(lines)


# ======================================================================
# EXECUTOR : Menjalankan action ERP yang diputuskan router
# ======================================================================
def _execute_action(action: str, param: str | None):
    """Execute one ERP action, return dict result."""
    try:
        if action == "lookup_product":
            keyword = param or ""
            rows = p_list(keyword) if keyword else p_list()
            products = [
                {"id": r[0], "name": r[1], "price_idr": f"Rp{r[2]:,.0f}", "stock": r[3]}
                for r in rows[:8]
            ]
            return {"status": "ok", "count": len(products), "products": products}

        if action == "check_low_stock":
            try:
                thr = int(param) if param else settings.low_stock_threshold
            except ValueError:
                thr = settings.low_stock_threshold
            data = report_low_stock(thr)
            return {"status": "ok", "threshold": thr, "products": data["products"]}

        if action == "check_sales_report":
            try:
                days = int(param) if param else settings.default_report_days
            except ValueError:
                days = settings.default_report_days
            data = report_sales(days)
            return {"status": "ok", "period_days": days,
                    "total_revenue_idr": f"Rp{data['total_revenue']:,.0f}",
                    "by_product": data["by_product"]}

        if action == "lookup_customer":
            keyword = param or ""
            rows = c_list(keyword) if keyword else c_list()
            custs = [
                {"id": r[0], "name": r[1], "email": r[2], "phone": r[3]}
                for r in rows[:10]
            ]
            return {"status": "ok", "count": len(custs), "customers": custs}

        if action == "lookup_order":
            oid = param or ""
            if not oid:
                return {"status": "error", "message": "lookup_order butuh order_id sebagai param"}
            r = o_get(oid)
            if not r:
                return {"status": "not_found", "order_id": oid}
            o = r["order"]
            return {
                "status": "ok",
                "order_id": o[0], "customer": o[2], "status_order": o[3],
                "total_idr": f"Rp{o[4]:,.0f}",
                "created_at": str(o[5]),
                "items": [
                    {"product": it[2], "qty": it[3], "price_idr": f"Rp{it[4]:,.0f}",
                     "subtotal_idr": f"Rp{it[5]:,.0f}"}
                    for it in r["items"]
                ],
            }

        if action == "lookup_erp_knowledge":
            keyword = param or ""
            rows = erpdoc_search(keyword, k=4) if keyword else []
            docs = [
                {"source": r[1], "content_snippet": r[2][:500], "score": float(r[3])}
                for r in rows
            ]
            return {"status": "ok", "count": len(docs), "erp_docs": docs}

        if action == "no_erp_needed":
            return {"status": "ok", "note": "Tidak perlu ambil data ERP - jawaban cukup dari SOP"}

        return {"status": "unknown_action", "action": action}
    except Exception as e:
        return {"status": "error", "action": action, "message": str(e)}


# ======================================================================
# ROUTER : SOP -> decide actions
# ======================================================================
def _fallback_router_plan(question: str, sop_rows: list):
    """
    RULE-BASED FALLBACK jika LLM router tidak siap / output JSON invalid.
    Heuristik sederhana berdasarkan kata kunci di pertanyaan + SOP.
    """
    q_lower = question.lower()
    actions = []

    if any(k in q_lower for k in ["garansi", "rusak", "doa", "klaim", "service"]):
        actions.append({"action": "lookup_product", "param": "NocBook",
                        "reason": "Heuristik: Klaim garansi butuh data produk"})

    if any(k in q_lower for k in ["stok", "persediaan", "habis", "menipis", "reorder", "stok minimum"]):
        thr = 10
        for w in q_lower.split():
            if w.isdigit():
                thr = int(w); break
        actions.append({"action": "check_low_stock", "param": str(thr),
                        "reason": "Heuristik: Cek stok kritis sesuai SOP"})

    if any(k in q_lower for k in ["penjualan", "laporan", "revenue", "omzet", "terlaris", "pendapatan"]):
        days = 7
        for w in q_lower.split():
            if w.isdigit() and 1 <= int(w) <= 90:
                days = int(w); break
        actions.append({"action": "check_sales_report", "param": str(days),
                        "reason": "Heuristik: Perlu laporan penjualan"})

    if any(k in q_lower for k in ["harga", "beli", "pesan", "order", "produk", "katalog", "spesifikasi", "spesifikasi", "spec"]):
        keyword = ""
        for cand in ["NocBook", "NocMouse", "NocBoard", "Monitor", "RAM", "SSD", "Headset", "Webcam"]:
            if cand.lower() in q_lower:
                keyword = cand; break
        actions.append({"action": "lookup_product", "param": keyword or None,
                        "reason": "Heuristik: User tanya tentang produk"})
        if keyword or any(k in q_lower for k in ["spesif", "spec", "detail"]):
            actions.append({"action": "lookup_erp_knowledge", "param": keyword or "spesifikasi produk",
                            "reason": "Heuristik: Perlu detail spesifikasi"})

    if any(k in q_lower for k in ["retur", "refund", "kembalikan barang", "pengembalian", "batal pesan"]):
        actions.append({"action": "lookup_order", "param": None,
                        "reason": "Heuristik: Return perlu data order (jika ada ID)"})

    if not actions:
        actions.append({"action": "no_erp_needed", "param": None,
                        "reason": "Heuristik: Jawaban cukup dari SOP saja"})

    sop_summary_parts = []
    for r in sop_rows[:2]:
        sop_summary_parts.append(f"{r[1]}: {r[2][:200]}")
    sop_summary = " | ".join(sop_summary_parts) if sop_summary_parts else "Tidak ada SOP spesifik ditemukan."

    return {"actions": actions[:3], "sop_summary": sop_summary}


async def _plan_actions(question: str, sop_rows: list, llm_ready: bool):
    """Pilih action via LLM jika siap, fallback ke rule-based."""
    if not llm_ready:
        return _fallback_router_plan(question, sop_rows)

    context_lines = []
    for i, r in enumerate(sop_rows[:4], 1):
        context_lines.append(f"[SOP {i} - {r[1]}] {r[2]}")
    sop_context = "\n\n".join(context_lines) if context_lines else "(tidak ada SOP yang match)"

    prompt = ROUTER_PROMPT.format(question=question, sop_context=sop_context)
    raw = await llm_complete(prompt, max_tokens=1000, temperature=0.2,
                             stop=["\n```", "```"])

    try:
        json_str = raw.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()
        parsed = json.loads(json_str)
        if "actions" not in parsed:
            raise ValueError("tidak ada field actions")
        return parsed
    except Exception as e:
        print(f"[Router] LLM parse gagal ({e}), fallback ke rule-based. Raw: {raw[:200]}")
        return _fallback_router_plan(question, sop_rows)


# ======================================================================
# AGENTIC MAIN PIPELINE
# ======================================================================
async def agentic_sop_erp_qa(question: str, llm_ready: bool, k_sop: int = 4):
    """
    Alur Agentic:
      STEP 1. Cari SOP TERLEBIH DAHULU (pahami prosedur).
      STEP 2. SOP -> router (LLM / rule) -> rencana action ERP.
      STEP 3. Eksekusi semua action ERP, kumpulkan hasil.
      STEP 4. Gabung SOP + hasil ERP -> LLM jawaban final.
    """
    # --- STEP 1 ---
    sop_rows = sop_search(question, k=k_sop)
    sop_context_dict = [
        {"id": r[0], "source": r[1], "content": r[2], "score": float(r[3])}
        for r in sop_rows
    ]

    # --- STEP 2 ---
    plan = await _plan_actions(question, sop_rows, llm_ready)

    # --- STEP 3 ---
    steps = []
    for act in plan.get("actions", []):
        result = _execute_action(act.get("action", "no_erp_needed"), act.get("param"))
        steps.append({
            "action": act.get("action"),
            "param": act.get("param"),
            "reason": act.get("reason"),
            "result": result,
        })

    # --- STEP 4 ---
    sop_summary = plan.get("sop_summary", "")
    sop_detail_lines = []
    for r in sop_rows[:3]:
        sop_detail_lines.append(f"- {r[1]}: {r[2][:400]}")
    sop_detail = "\n".join(sop_detail_lines) or "(tidak ada)"

    erp_lines = []
    for s in steps:
        erp_lines.append(f"[Action: {s['action']} (param={s['param']!r})]")
        erp_lines.append(f"   Reason: {s.get('reason','-')}")
        erp_lines.append(f"   Result: {json.dumps(s['result'], ensure_ascii=False)[:800]}")
    erp_results = "\n".join(erp_lines) if erp_lines else "(tidak ada action ERP)"

    if llm_ready:
        prompt = FINAL_ANSWER_PROMPT.format(
            sop_summary=sop_summary,
            sop_detail=sop_detail,
            erp_results=erp_results,
            question=question,
        )
        final_answer = await llm_complete(prompt, max_tokens=800, temperature=0.35)
    else:
        parts = [f"📋 **SOP Terkait**: {sop_summary or sop_detail[:300]}"]
        for s in steps:
            act, res = s["action"], s["result"]
            if res.get("status") == "ok":
                if act == "lookup_product" and res.get("products"):
                    ps = res["products"][:3]
                    parts.append("\n🛒 **Data Produk** (dari ERP):")
                    for p in ps:
                        parts.append(f"  • {p['name']} — {p['price_idr']} (stok: {p['stock']})")
                elif act == "check_low_stock":
                    parts.append(f"\n⚠️ **Stok Kritis** (<= {res.get('threshold')}):")
                    for p in res.get("products", [])[:3]:
                        parts.append(f"  • {p['name']} — sisa {p['stock']} unit @Rp{p['price']:,.0f}")
                elif act == "check_sales_report":
                    parts.append(f"\n📊 **Penjualan {res.get('period_days')} hari** (total {res.get('total_revenue_idr')}):")
                    for bp in res.get("by_product", [])[:3]:
                        parts.append(f"  • {bp['product']}: {bp['qty']} unit (Rp{bp['revenue']:,.0f})")
                elif act == "lookup_erp_knowledge" and res.get("erp_docs"):
                    parts.append(f"\n📘 **Pengetahuan ERP**:")
                    for d in res["erp_docs"][:2]:
                        parts.append(f"  • [{d['source']}] {d['content_snippet'][:200]}")
                elif act == "lookup_order":
                    if res.get("status_order"):
                        parts.append(f"\n🧾 **Order {res['order_id']}**: {res['status_order']} — {res['total_idr']}")
                elif act == "no_erp_needed":
                    parts.append("")
        parts.append("\n💡 **Langkah Selanjutnya**: Hubungi CS WA +62-811-0000-123 untuk bantuan lebih lanjut.")
        final_answer = "\n".join(parts)

    return {
        "question": question,
        "sop_context": sop_context_dict,
        "plan": plan,
        "steps": steps,
        "final_answer": final_answer,
        "llm_used": llm_ready,
    }


# ======================================================================
# LEGACY GENERATORS (backward compat)
# ======================================================================
async def generate_sales_report(days: int | None = None):
    days = days or settings.default_report_days
    raw = report_sales(days)
    summary = _summarize_sales(raw)
    narrative = await llm_complete(
        SALES_PROMPT.format(
            days=raw.get("period_days", days),
            data_summary=summary,
        ),
        max_tokens=900, temperature=0.5,
    )
    return {
        "type": "sales_report",
        "period_days": raw.get("period_days"),
        "raw_data": raw,
        "summary_text": summary,
        "narrative": narrative,
    }


async def generate_low_stock_report(threshold: int | None = None):
    threshold = threshold or settings.low_stock_threshold
    raw = report_low_stock(threshold)
    summary = _summarize_lowstock(raw)
    narrative = await llm_complete(
        LOW_STOCK_PROMPT.format(
            threshold=raw.get("threshold", threshold),
            data_summary=summary,
        ),
        max_tokens=700, temperature=0.3,
    )
    return {
        "type": "low_stock_report",
        "threshold": raw.get("threshold"),
        "raw_data": raw,
        "summary_text": summary,
        "narrative": narrative,
    }


async def answer_with_knowledge(question: str, search_results: list):
    context_lines = []
    for i, r in enumerate(search_results, 1):
        context_lines.append(f"[Sumber: {r[1]}] {r[2]}")
    context = "\n\n".join(context_lines) if context_lines else "(tidak ada konteks ditemukan)"
    answer = await llm_complete(
        KNOWLEDGE_QA_PROMPT.format(context=context, question=question),
        max_tokens=600, temperature=0.3,
    )
    return {
        "question": question,
        "context": context_lines,
        "answer": answer,
    }
