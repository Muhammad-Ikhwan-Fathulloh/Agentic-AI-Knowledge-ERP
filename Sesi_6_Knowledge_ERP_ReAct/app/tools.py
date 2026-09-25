import json
import httpx
from app.config import settings


class ERPTools:
    """
    Tool registry yang memanggil ERP REST API (Sesi 5, port 8005).
    Semua method return STRING agar bisa jadi Observation di ReAct.
    """
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.erp_api_base
        self.client = httpx.Client(timeout=30.0)
        self._pending_order = None

    def _get(self, path, params=None):
        try:
            return self.client.get(f"{self.base_url}{path}", params=params or {}).json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path, json_body=None):
        try:
            return self.client.post(f"{self.base_url}{path}", json=json_body or {}).json()
        except Exception as e:
            return {"error": str(e)}

    # ----- check_stock -----
    def check_stock(self, product_name: str) -> str:
        rows = self._get("/products", {"name": product_name})
        if isinstance(rows, list) and rows:
            lines = [f"Hasil pencarian stok untuk '{product_name}':"]
            for r in rows:
                lines.append(
                    f"- ID: {r['id']} | {r['name']} | Harga: Rp{r['price']:,.0f} | Stok: {r['stock']} unit"
                )
            return "\n".join(lines)
        return f"(tidak ada produk yang cocok dengan '{product_name}')"

    # ----- list_products -----
    def list_products(self) -> str:
        rows = self._get("/products")
        if isinstance(rows, list):
            lines = [f"Daftar {len(rows)} produk:"]
            for r in rows:
                lines.append(
                    f"- [{r['id'][:8]}] {r['name']} - Rp{r['price']:,.0f} (stok {r['stock']})"
                )
            return "\n".join(lines)
        return f"ERROR: {rows}"

    # ----- get_order_status -----
    def get_order_status(self, order_id: str) -> str:
        r = self._get(f"/orders/{order_id}")
        if isinstance(r, dict) and "id" in r:
            it = "\n".join(
                f"  * {x['product_name']} x{x['qty']} @ Rp{x['price']:,.0f} = Rp{x['subtotal']:,.0f}"
                for x in r.get("items", [])
            )
            return (
                f"Order {r['id']}\n"
                f"Pelanggan: {r['customer_name']}\n"
                f"Status: {r['status']}\n"
                f"Total: Rp{r['total_amount']:,.0f}\n"
                f"Tanggal: {r['created_at']}\n"
                f"Item:\n{it}"
            )
        return f"Order tidak ditemukan / error: {r}"

    # ----- create_order (human-in-the-loop) -----
    def stage_create_order(self, customer_id, product_id, qty) -> str:
        payload = {
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "qty": int(qty)}],
        }
        r = self._post("/orders", payload)
        if "error" in r or "detail" in r:
            return f"GAGAL membuat order: {r.get('detail') or r.get('error') or r}"
        self._pending_order = r
        return (
            f"[PERLU KONFIRMASI] Order sudah disimulasikan:\n"
            f"  order_id: {r.get('order_id')}\n"
            f"  total: Rp{r.get('total_amount', 0):,.0f}\n"
            f"Kirim Action confirm_create_order jika user setuju."
        )

    def confirm_create_order(self, answer: str = "ya") -> str:
        if "ya" in answer.lower() or "ok" in answer.lower() or "setuju" in answer.lower():
            return f"Order berhasil disimpan: {json.dumps(self._pending_order)}"
        return "Order DIBATALKAN oleh user."

    # ----- list_customers -----
    def list_customers(self) -> str:
        rows = self._get("/customers")
        if isinstance(rows, list):
            lines = [f"Daftar {len(rows)} pelanggan:"]
            for r in rows:
                lines.append(
                    f"- ID: {r['id']} | {r['name']} | {r.get('email') or '-'} | {r.get('phone') or '-'}"
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
