import httpx
from app.config import settings


class ERPReportData:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.erp_api_base
        self.client = httpx.Client(timeout=30.0)

    def sales(self, days: int | None = None):
        days = days or settings.default_report_days
        try:
            return self.client.get(f"{self.base_url}/report/sales", params={"days": days}).json()
        except Exception as e:
            return {"error": str(e), "period_days": days, "total_revenue": 0, "by_product": []}

    def low_stock(self, threshold: int | None = None):
        threshold = threshold or settings.low_stock_threshold
        try:
            return self.client.get(f"{self.base_url}/report/low-stock", params={"threshold": threshold}).json()
        except Exception as e:
            return {"error": str(e), "threshold": threshold, "products": []}

    def latest_orders(self, limit=10):
        try:
            return self.client.get(f"{self.base_url}/orders", params={"limit": limit}).json()
        except Exception as e:
            return {"error": str(e)}
