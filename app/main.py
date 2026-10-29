import hmac
import json
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from app.cdek_client import CDEKClient
from app.config import (
    ORDER_IDEMPOTENCY_DB_PATH,
    SENDER_CITY_CODE,
    TILDA_WEBHOOK_SECRET,
)
from app.idempotency import IdempotencyStore
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


def _parse_webhook_body(body: bytes, content_type: str) -> dict:
    media_type = content_type.split(";", 1)[0].strip().lower()
    try:
        if media_type == "application/json" or body.lstrip().startswith(b"{"):
            payload = json.loads(body)
        else:
            fields = parse_qsl(body.decode("utf-8"), keep_blank_values=True)
            payload = {key: value for key, value in fields}
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook body") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be an object")
    return payload


def _payment_candidates(payload: dict) -> list[dict]:
    candidates = []
    for key in ("tildapayment", "payment"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                candidates.append(parsed)
    return candidates


def _extract_order_id(payload: dict) -> str:
    values = [payload.get("orderid"), payload.get("orderId")]
    for payment in _payment_candidates(payload):
        values.extend((payment.get("orderid"), payment.get("orderId")))

    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _authenticate_tilda(request: Request) -> None:
    if not TILDA_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Tilda webhook authentication is not configured",
        )

    supplied_token = request.headers.get("X-Tilda-Webhook-Token")
    if not supplied_token or not hmac.compare_digest(
        supplied_token.encode("utf-8"), TILDA_WEBHOOK_SECRET.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid Tilda webhook token")


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

@app.post(
    "/create-order",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    }
                },
            },
        }
    },
)
async def create_order(request: Request):
    """Authenticate Tilda webhook, then process a test or idempotent order."""
    _authenticate_tilda(request)
    order = _parse_webhook_body(
        await request.body(),
        request.headers.get("content-type", ""),
    )

    if order.get("test") == "test":
        return {"status": "ok", "message": "Tilda webhook test received"}

    order_id = _extract_order_id(order)
    if not order_id:
        raise HTTPException(status_code=400, detail="Tilda orderid is required")

    store = IdempotencyStore(ORDER_IDEMPOTENCY_DB_PATH)
    state, saved_result = store.reserve(order_id)
    if state == "succeeded":
        return saved_result
    if state == "processing":
        raise HTTPException(
            status_code=409,
            detail="This orderid is already being processed",
        )
    if state == "uncertain":
        raise HTTPException(
            status_code=409,
            detail="Previous CDEK submission outcome is uncertain; verify before retrying",
        )

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
    except HTTPException:
        store.release(order_id)
        raise
    except Exception as error:
        store.release(order_id)
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error)) from None
        raise

    try:
        result = cdek.create_order(payload)
    except Exception:
        store.mark_uncertain(order_id)
        raise HTTPException(
            status_code=502,
            detail="CDEK order submission outcome is uncertain; verify before retrying",
        ) from None

    if not result["success"]:
        if result["status_code"] >= 500:
            store.mark_uncertain(order_id)
        else:
            store.release(order_id)
        raise HTTPException(
            status_code=result["status_code"],
            detail=result["data"],
        )

    response_data = result["data"]
    entity = response_data.get("entity") if isinstance(response_data, dict) else None
    cdek_uuid = entity.get("uuid") if isinstance(entity, dict) else None
    if not cdek_uuid:
        store.mark_uncertain(order_id)
        raise HTTPException(
            status_code=502,
            detail="CDEK response did not contain an order UUID; verify before retrying",
        )

    store.complete(order_id, response_data)
    return response_data


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