import json
from app.config import settings
from app.database import db


class ERPTools:
    """
    Tool registry yang memanggil ERP Database Layer secara internal.
    Semua method return STRING agar bisa jadi Observation di ReAct.
    """
    def __init__(self, base_url: str | None = None):
        self._pending_order = None

    # ----- check_stock -----
    def check_stock(self, product_name: str) -> str:
        rows = db.product_list(name=product_name)
        if isinstance(rows, list) and rows:
            lines = [f"Hasil pencarian stok untuk '{product_name}':"]
            for r in rows:
                lines.append(
                    f"- ID: {r[0]} | {r[1]} | Harga: Rp{r[2]:,.0f} | Stok: {r[3]} unit"
                )
            return "\n".join(lines)
        return f"(tidak ada produk yang cocok dengan '{product_name}')"

    # ----- list_products -----
    def list_products(self) -> str:
        rows = db.product_list()
        if isinstance(rows, list):
            lines = [f"Daftar {len(rows)} produk:"]
            for r in rows:
                lines.append(
                    f"- [{r[0][:8]}] {r[1]} - Rp{r[2]:,.0f} (stok {r[3]})"
                )
            return "\n".join(lines)
        return f"ERROR: {rows}"

    # ----- get_order_status -----
    def get_order_status(self, order_id: str) -> str:
        try:
            r = db.order_get(order_id)
            if r:
                o = r["order"]
                items = r["items"]
                it = "\n".join(
                    f"  * {x[2]} x{x[3]} @ Rp{x[4]:,.0f} = Rp{x[5]:,.0f}"
                    for x in items
                )
                return (
                    f"Order {o[0]}\n"
                    f"Pelanggan: {o[2]}\n"
                    f"Status: {o[3]}\n"
                    f"Total: Rp{o[4]:,.0f}\n"
                    f"Tanggal: {o[5]}\n"
                    f"Item:\n{it}"
                )
            return "Order tidak ditemukan."
        except Exception as e:
            return f"Error: {e}"

    # ----- create_order (human-in-the-loop) -----
    def stage_create_order(self, customer_id, product_id, qty) -> str:
        try:
            r = db.order_create(customer_id, [{"product_id": product_id, "qty": int(qty)}])
            self._pending_order = r
            return (
                f"[PERLU KONFIRMASI] Order sudah disimulasikan:\n"
                f"  order_id: {r.get('order_id')}\n"
                f"  total: Rp{r.get('total_amount', 0):,.0f}\n"
                f"Kirim Action confirm_create_order jika user setuju."
            )
        except ValueError as e:
            return f"GAGAL membuat order: {str(e)}"
        except Exception as e:
            return f"Error API: {e}"

    def confirm_create_order(self, answer: str = "ya") -> str:
        if "ya" in answer.lower() or "ok" in answer.lower() or "setuju" in answer.lower():
            return f"Order berhasil disimpan: {json.dumps(self._pending_order)}"
        return "Order DIBATALKAN oleh user."

    # ----- list_customers -----
    def list_customers(self) -> str:
        rows = db.customer_list()
        if isinstance(rows, list):
            lines = [f"Daftar {len(rows)} pelanggan:"]
            for r in rows:
                lines.append(
                    f"- ID: {r[0]} | {r[1]} | {r[2] or '-'} | {r[3] or '-'}"
                )
            return "\n".join(lines)
        return f"ERROR: {rows}"

    def call(self, action: str, params_str: str, human_confirm_answer: str | None = None) -> str:
        action = action.strip().lower()
        params_str = (params_str or "").strip()

        try:
            params = json.loads(params_str) if params_str.startswith("{") else {"value": params_str}
        except Exception:
            params = {"value": params_str}

        if action == "check_stock":
            return self.check_stock(params.get("product_name") or params.get("value") or params_str)
        if action == "list_products":
            return self.list_products()
        if action == "list_customers":
            return self.list_customers()
        if action == "get_order_status":
            return self.get_order_status(params.get("order_id") or params.get("value") or params_str)
        if action == "create_order":
            return self.stage_create_order(
                params.get("customer_id"), params.get("product_id"), params.get("qty", 1)
            )
        if action == "confirm_create_order":
            return self.confirm_create_order(human_confirm_answer or params_str)
        return (
            f"Tool '{action}' tidak dikenal.\n"
            f"Tool tersedia: check_stock, list_products, list_customers, get_order_status, create_order, confirm_create_order."
        )
