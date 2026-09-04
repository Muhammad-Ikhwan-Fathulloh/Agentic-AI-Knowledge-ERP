import json
import re

from app.config import settings
from app.llm import llm_complete


def extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


ROUTER_PROMPT = """Kamu adalah ROUTER agent. Tugasmu: klasifikasikan query user ke SALAH SATU domain:
- knowledge  →  pertanyaan tentang informasi, dokumen, FAQ, SOP, pengetahuan umum berbasis teks, atau sapaan halo.
- erp        →  pertanyaan tentang data transaksional: stok, harga produk, daftar produk, order/status pesanan, laporan penjualan, pelanggan, atau permintaan buat order.

Keluarkan HANYA JSON (tidak ada teks lain):
{{"domain": "knowledge"}}   ATAU   {{"domain": "erp"}}

Query user: {query}
JSON:"""


def _rule_fallback(query: str) -> str:
    q = query.lower()
    erp_kws = [
        "stok", "harga", "order", "beli", "pesan", "jual", "laporan", "penjualan",
        "produk", "barang", "pelanggan", "customer", "stoknya", "diskon", "keranjang",
        "checkout", "resi", "pengiriman",
    ]
    if any(k in q for k in erp_kws):
        return "erp"
    return "knowledge"


async def route_query(query: str) -> tuple[str, str]:
    """Return (domain, confidence). confidence: llm | fallback."""
    raw = None
    for _ in range(settings.router_max_retry + 1):
        raw = await llm_complete(
            ROUTER_PROMPT.format(query=query),
            max_tokens=120, temperature=0.05, stop=["\n\n"],
        )
        parsed = extract_json(raw)
        if parsed and parsed.get("domain") in ("knowledge", "erp"):
            return parsed["domain"], "llm"
    return _rule_fallback(query), "fallback"
