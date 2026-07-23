from app.models.order import Order
from app.models.tariff import TariffRequest


def transform_order(order: Order) -> dict:
    """
    Преобразует внутреннюю модель заказа
    в формат API СДЭК.
    """

    return {
        "type": 1,
        "number": order.order_number,
        "tariff_code": 136,
        "comment": order.comment,

        "shipment_point": "MSK1",
        "delivery_point": "SPB1",

        "recipient": {
            "name": order.customer_name,
            "email": order.customer_email,
            "phones": [
                {
                    "number": order.customer_phone
                }
            ]
        },

        "from_location": {
            "code": 44,
            "address": "Москва"
        },

        "to_location": {
            "city": order.city,
            "address": order.address
        },

        "packages": [
            {
                "number": "PKG-1",
                "weight": 1000,
                "length": 20,
                "width": 20,
                "height": 20,

                "items": [
                    {
                        "name": "Товар",
                        "ware_key": "SKU-001",
                        "cost": 1000,
                        "payment": {
                            "value": 1000
                        },
                        "weight": 1000,
                        "amount": 1
                    }
                ]
            }
        ]
    }


def transform_tariff(data: TariffRequest) -> dict:
    """
    Преобразует запрос расчета тарифа
    в формат API СДЭК.
    """

    return {
        "type": 1,
        "tariff_code": data.tariff_code,

        "from_location": {
            "code": data.from_code
        },

        "to_location": {
            "code": data.to_code
        },

        "packages": [
            {
                "weight": data.weight,
                "length": data.length,
                "width": data.width,
                "height": data.height
            }
        ]
    }