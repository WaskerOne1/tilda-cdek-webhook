from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Customer:
    """Информация о покупателе."""

    name: str
    phone: str
    email: str = ""


@dataclass
class Address:
    """Адрес доставки."""

    city: str
    address: str
    postal_code: str = ""
    pickup_point_id: Optional[str] = None


@dataclass
class Item:
    """Товар."""

    external_id: str
    name: str
    quantity: int
    price: float

    # Заполняются CatalogResolver
    weight: float = 0.0

    length: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class Delivery:
    """Доставка."""

    type: str
    price: float


@dataclass
class Order:
    """Внутренняя модель заказа."""

    order_id: str

    customer: Customer

    address: Address

    delivery: Delivery

    items: List[Item] = field(default_factory=list)

    subtotal: float = 0.0
    total: float = 0.0