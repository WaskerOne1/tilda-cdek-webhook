from fastapi import FastAPI, HTTPException

from app.cdek_client import CDEKClient
from app.config import SENDER_CITY_CODE
from app.models.tariff import TariffRequest
from app.transformer import (
    parse_order_payload,
    select_preferred_tariff,
    transform_order,
    transform_order_tariff_list,
    transform_tariff,
)

app = FastAPI()

cdek = CDEKClient()


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "CDEK Webhook"
    }


# -------------------------------------------------
# Расчет стоимости
# -------------------------------------------------

@app.post("/calculate")
async def calculate(data: TariffRequest):
    """Generic tariff calculation endpoint. Не предназначен для этапов Tilda pickup-list/calculate."""
    payload = transform_tariff(data)
    result = cdek.calculate_tariff(payload)

    if not result["success"]:
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    return result["data"]


# -------------------------------------------------
# Создание заказа
# -------------------------------------------------

@app.post("/create-order")
async def create_order(order: dict):
    """Принимает финальный webhook Tilda или готовый order JSON и создает заказ в СДЭК."""
    try:
        parsed_order = parse_order_payload(order)

        if parsed_order.address.pickup_point_id:
            try:
                sender_city_code = int(SENDER_CITY_CODE)
            except (TypeError, ValueError):
                raise ValueError(
                    "Invalid configuration SENDER_CITY_CODE: expected a positive integer"
                ) from None

            if sender_city_code <= 0:
                raise ValueError(
                    "Invalid configuration SENDER_CITY_CODE: expected a positive integer"
                )

            recipient_city_code = cdek.get_city_code(parsed_order.address.city)
            if not recipient_city_code:
                raise ValueError(
                    f"Recipient city '{parsed_order.address.city}' was not found in CDEK"
                )

            tariff_request = transform_order_tariff_list(
                parsed_order,
                sender_city_code=sender_city_code,
                recipient_city_code=recipient_city_code,
            )
            tariff_result = cdek.calculate_tariff_list(tariff_request)
            if not tariff_result["success"]:
                raise HTTPException(
                    status_code=tariff_result["status_code"],
                    detail=tariff_result["data"],
                )

            selected_tariff_code = select_preferred_tariff(tariff_result["data"])
            payload = transform_order(parsed_order, tariff_code=selected_tariff_code)
        else:
            payload = transform_order(parsed_order)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    result = cdek.create_order(payload)

    if not result["success"]:
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    return result["data"]


# -------------------------------------------------
# Получение заказа
# -------------------------------------------------

@app.get("/order/{uuid}")
async def get_order(uuid: str):

    return cdek.get_order(uuid)


# -------------------------------------------------
# Города
# -------------------------------------------------

@app.get("/cities")
async def get_cities(city: str | None = None):

    result = cdek.get_cities(city)

    if not result["success"]:
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    cities = []

    for item in result["data"]:

        cities.append(
            {
                "code": item.get("code"),
                "city": item.get("city"),
                "region": item.get("region"),
                "country": item.get("country"),
            }
        )

    return cities


# -------------------------------------------------
# Пункты выдачи
# -------------------------------------------------

@app.get("/offices")
async def get_offices(city: str):

    result = cdek.get_offices(city)

    if not result["success"]:
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    offices = []

    for office in result["data"]:

        # Только действующие ПВЗ
        if not office.get("is_handout"):
            continue

        phones = office.get("phones") or []

        phone = ""

        if phones:
            phone = phones[0].get("number", "")

        location = office.get("location") or {}

        offices.append(
            {
                "code": office.get("code"),
                "name": office.get("name"),
                "address": location.get("address"),
                "work_time": office.get("work_time"),
                "phone": phone,
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),

                # Полезные признаки для сайта
                "cashless": office.get("have_cashless"),
                "fitting_room": office.get("is_dressing_room"),
                "allowed_cod": office.get("allowed_cod"),
            }
        )

    offices.sort(
        key=lambda x: (
            x["address"] or "",
            x["name"] or "",
        )
    )

    return {
        "count": len(offices),
        "items": offices,
    }


@app.get("/offices/raw")
async def get_offices_raw(city: str):
    result = cdek.get_offices(city)

    if not result["success"]:
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    return result["data"]