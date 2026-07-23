from fastapi import FastAPI

from app.cdek_client import CDEKClient
from app.models.order import Order
from app.models.tariff import TariffRequest
from app.transformer import transform_order, transform_tariff

app = FastAPI()

cdek = CDEKClient()


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "CDEK Webhook"
    }


@app.post("/calculate")
async def calculate(data: TariffRequest):

    payload = transform_tariff(data)

    result = cdek.calculate_tariff(payload)

    return result


@app.post("/create-order")
async def create_order(order: Order):

    payload = transform_order(order)

    result = cdek.create_order(payload)

    return result