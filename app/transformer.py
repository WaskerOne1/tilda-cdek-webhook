import json
from typing import Any, Dict, List, Optional

from app.config import (
    DEFAULT_FROM_LOCATION_ADDRESS,
    DEFAULT_FROM_LOCATION_CODE,
    DEFAULT_TARIFF_CODE,
    SENDER_COMPANY,
    SENDER_EMAIL,
    SENDER_LOCATION_ADDRESS,
    SENDER_LOCATION_CODE,
    SENDER_NAME,
    SENDER_PHONE,
)
from app.models.order import Address, Customer, Delivery, Item, Order
from app.models.tariff import TariffRequest


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _normalize_phone(value: Any) -> str:
    if value is None:
        return ""

    raw = str(value)
    return "".join(ch for ch in raw if ch.isdigit() or ch == "+")


def _build_packages(items: List[Item]) -> List[Dict[str, Any]]:
    packages: List[Dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        quantity = item.quantity if item.quantity > 0 else 1
        package_weight = int(item.weight * quantity) if item.weight else 1000
        package_length = item.length or 20
        package_width = item.width or 20
        package_height = item.height or 20

        packages.append(
            {
                "number": f"PKG-{index}",
                "weight": package_weight,
                "length": package_length,
                "width": package_width,
                "height": package_height,
                "items": [
                    {
                        "name": item.name,
                        "ware_key": item.external_id,
                        "cost": item.price,
                        "payment": {"value": item.price},
                        "weight": package_weight,
                        "amount": quantity,
                    }
                ],
            }
        )

    return packages


def _get_first_available_code(*values: Optional[str]) -> int:
    for value in values:
        if value is not None and value != "":
            code = _to_int(value)
            if code:
                return code
    return 0


def _load_tildapayment(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_payment = payload.get("tildapayment")

    if isinstance(raw_payment, dict):
        return raw_payment

    if isinstance(raw_payment, str):
        try:
            return json.loads(raw_payment)
        except json.JSONDecodeError:
            return None

    return None


def from_tilda_order(payload: Dict[str, Any]) -> Order:
    tildapayment = _load_tildapayment(payload)
    payment = tildapayment or payload.get("payment", {})

    order_id = (
        payment.get("orderid")
        or payment.get("orderId")
        or payload.get("orderid")
        or payload.get("orderId")
        or payload.get("guid")
        or payload.get("formid")
        or "tilda-order"
    )

    customer_name = payload.get("Name") or payment.get("delivery_fio") or ""
    customer_phone = payload.get("Phone") or ""

    raw_delivery = payment.get("delivery", {})
    # payment["delivery"] may be either a dict (detailed delivery data) or
    # a string (delivery type/name). Normalize to a dict for downstream
    # field access.
    if isinstance(raw_delivery, dict):
        delivery_data = raw_delivery
    else:
        delivery_data = {}
    address_city = (
        delivery_data.get("city")
        or payment.get("delivery_city")
        or payload.get("city")
        or ""
    )
    address_text = (
        delivery_data.get("pickup-name")
        or payment.get("delivery_address")
        or ""
    )
    address_postal = (
        delivery_data.get("postalcode")
        or payment.get("delivery_zip")
        or ""
    )
    pickup_point = (
        delivery_data.get("pickup-id")
        or payment.get("pickupPointId")
        or payload.get("pickupPointId")
    )

    products = payment.get("products", [])

    items: List[Item] = []
    for product in products:
        external_id = (
            product.get("externalid")
            or product.get("gen_uid")
            or product.get("uid")
            or product.get("recid")
            or product.get("name")
            or ""
        )

        items.append(
            Item(
                external_id=str(external_id),
                name=str(product.get("name") or "Товар"),
                quantity=_to_int(product.get("quantity") or 1, 1),
                price=_to_float(product.get("price") or product.get("amount") or 0),
                weight=_to_float(product.get("pack_m") or 0),
                length=_to_int(product.get("pack_x") or 0),
                width=_to_int(product.get("pack_y") or 0),
                height=_to_int(product.get("pack_z") or 0),
            )
        )

    # Determine delivery type as a string. If payment['delivery'] is a dict,
    # try to extract a 'type' field; if it's a string, use it directly.
    raw_delivery_type = payment.get("delivery")
    if isinstance(raw_delivery_type, dict):
        delivery_type = raw_delivery_type.get("type") or "Доставка"
    elif isinstance(raw_delivery_type, str):
        delivery_type = raw_delivery_type
    else:
        delivery_type = "Доставка"
    delivery_price = _to_float(payment.get("delivery_price") or 0)

    subtotal = _to_float(payment.get("subtotal") or payment.get("amount") or 0)
    total = _to_float(payment.get("amount") or subtotal)

    return Order(
        order_id=str(order_id),
        customer=Customer(
            name=str(customer_name),
            phone=_normalize_phone(customer_phone),
            email=str(payload.get("Email") or payment.get("email") or ""),
        ),
        address=Address(
            city=str(address_city),
            address=str(address_text),
            postal_code=str(address_postal),
            pickup_point_id=str(pickup_point) if pickup_point else None,
        ),
        delivery=Delivery(
            type=str(delivery_type),
            price=delivery_price,
        ),
        items=items,
        subtotal=subtotal,
        total=total,
    )


def parse_order_payload(payload: Dict[str, Any]) -> Order:
    """Преобразует финальный webhook Tilda или готовый order JSON в внутреннюю модель Order."""

    if "payment" in payload or "Name" in payload or "delivery_city" in payload:
        return from_tilda_order(payload)

    if "sender" in payload and "recipient" in payload and "packages" in payload:
        raise ValueError("Payload is already in СДЭК format")

    return Order(
        order_id=str(payload.get("order_id") or payload.get("id") or "order"),
        customer=Customer(**payload["customer"]),
        address=Address(**payload["address"]),
        delivery=Delivery(**payload["delivery"]),
        items=[Item(**item) for item in payload.get("items", [])],
        subtotal=_to_float(payload.get("subtotal") or payload.get("total") or 0),
        total=_to_float(payload.get("total") or payload.get("amount") or 0),
    )


def transform_order(order: Order) -> dict:
    """Преобразует внутреннюю модель заказа в формат API СДЭК."""

    if not order.customer.phone:
        raise ValueError("Телефон получателя обязателен")

    payload: Dict[str, Any] = {
        "type": 1,
        "number": str(order.order_id),
        "tariff_code": _to_int(getattr(order, "tariff_code", DEFAULT_TARIFF_CODE)),
        "comment": getattr(order, "comment", ""),
        "sender": {
            "name": SENDER_NAME,
            "company": SENDER_COMPANY,
            "email": SENDER_EMAIL,
            "phones": [{"number": _normalize_phone(SENDER_PHONE)}] if SENDER_PHONE else [],
        },
        "recipient": {
            "name": order.customer.name,
            "email": order.customer.email,
            "phones": [{"number": _normalize_phone(order.customer.phone)}],
        },
        "from_location": {
            "code": _get_first_available_code(SENDER_LOCATION_CODE, DEFAULT_FROM_LOCATION_CODE),
            "address": SENDER_LOCATION_ADDRESS or DEFAULT_FROM_LOCATION_ADDRESS,
        },
        "packages": _build_packages(order.items),
    }

    if order.address.pickup_point_id:
        payload["delivery_point"] = order.address.pickup_point_id
    else:
        payload["to_location"] = {
            "city": order.address.city,
            "postal_code": order.address.postal_code,
            "address": order.address.address,
        }

    return payload


def transform_tariff(data: TariffRequest) -> dict:
    """Преобразует запрос расчета тарифа в формат API СДЭК."""

    return {
        "type": 1,
        "tariff_code": data.tariff_code,
        "from_location": {"code": data.from_code},
        "to_location": {"code": data.to_code},
        "packages": [
            {
                "weight": data.weight,
                "length": data.length,
                "width": data.width,
                "height": data.height,
            }
        ],
    }
