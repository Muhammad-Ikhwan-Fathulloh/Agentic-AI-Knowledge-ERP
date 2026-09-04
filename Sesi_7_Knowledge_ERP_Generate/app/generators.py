from app.llm import llm_complete
from app.report_data import ERPReportData
from app.config import settings

data_client = ERPReportData()

SALES_PROMPT = """Kamu adalah ANALIS BISNIS senior di toko online retail.
Berikut adalah DATA PENJUALAN {days} hari TERAKHIR dalam format teks:
{data_summary}

TULIS LAPORAN EKSEKUTIF dalam BAHASA INDONESIA FORMAL, TEPAT 4 PARAGRAF:
Paragraf 1: Ringkasan total pendapatan dan performa umum.
Paragraf 2: Analisis 3 produk terlaris (jika ada < 3, sebutkan semua) — sertakan unit terjual & kontribusi revenue.
Paragraf 3: Tren yang terlihat (misal: produk teknologi tinggi laku, aksesoris stabil, dsb) — JANGAN mengarang data, simpulkan hanya dari angka yang ada.
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
        lines.append("  (semua produk stok aman — tidak ada yang di bawah threshold)")
    return "\n".join(lines)


async def generate_sales_report(days: int | None = None):
    raw = data_client.sales(days)
    summary = _summarize_sales(raw)
    narrative = await llm_complete(
        SALES_PROMPT.format(
            days=raw.get("period_days", settings.default_report_days),
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
    raw = data_client.low_stock(threshold)
    summary = _summarize_lowstock(raw)
    narrative = await llm_complete(
        LOW_STOCK_PROMPT.format(
            threshold=raw.get("threshold", settings.low_stock_threshold),
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
