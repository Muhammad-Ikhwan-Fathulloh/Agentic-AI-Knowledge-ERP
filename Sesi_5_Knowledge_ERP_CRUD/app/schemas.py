from pydantic import BaseModel
from typing import List, Optional


class ProductIn(BaseModel):
    name: str
    price: float
    stock: int = 0


class ProductOut(ProductIn):
    id: str


class CustomerIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class CustomerOut(CustomerIn):
    id: str


class OrderItemIn(BaseModel):
    product_id: str
    qty: int


class OrderIn(BaseModel):
    customer_id: str
    items: List[OrderItemIn]
