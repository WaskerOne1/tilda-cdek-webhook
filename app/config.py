import os

from dotenv import load_dotenv

load_dotenv()

CDEK_API = os.getenv("CDEK_API")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Default sender settings for СДЭК order creation.
SENDER_NAME = os.getenv("SENDER_NAME", "Отправитель")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PHONE = os.getenv("SENDER_PHONE", "")
SENDER_SHIPMENT_POINT = os.getenv("SENDER_SHIPMENT_POINT")
SENDER_CITY_CODE = os.getenv("SENDER_CITY_CODE")
DEFAULT_TARIFF_CODE = os.getenv("DEFAULT_TARIFF_CODE")
TILDA_WEBHOOK_SECRET = os.getenv("TILDA_WEBHOOK_SECRET")
ORDER_IDEMPOTENCY_DB_PATH = os.getenv(
    "ORDER_IDEMPOTENCY_DB_PATH"
) or "data/order_idempotency.sqlite3"

REQUIRED_CONFIG = {
    "CDEK_API": CDEK_API,
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "SENDER_PHONE": SENDER_PHONE,
    "SENDER_SHIPMENT_POINT": SENDER_SHIPMENT_POINT,
    "SENDER_CITY_CODE": SENDER_CITY_CODE,
    "DEFAULT_TARIFF_CODE": DEFAULT_TARIFF_CODE,
}

missing_config = [name for name, value in REQUIRED_CONFIG.items() if not value]
if missing_config:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_config)
    )
