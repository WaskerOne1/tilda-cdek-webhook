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
SENDER_LOCATION_CODE = os.getenv("SENDER_LOCATION_CODE")
SENDER_LOCATION_ADDRESS = os.getenv("SENDER_LOCATION_ADDRESS", "")

# Default СДЭК location and tariff values.
DEFAULT_FROM_LOCATION_CODE = os.getenv("DEFAULT_FROM_LOCATION_CODE")
DEFAULT_FROM_LOCATION_ADDRESS = os.getenv("DEFAULT_FROM_LOCATION_ADDRESS", "")
DEFAULT_TARIFF_CODE = os.getenv("DEFAULT_TARIFF_CODE", "21")

REQUIRED_CONFIG = {
    "CDEK_API": CDEK_API,
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "SENDER_LOCATION_CODE": SENDER_LOCATION_CODE,
    "SENDER_LOCATION_ADDRESS": SENDER_LOCATION_ADDRESS,
    "SENDER_PHONE": SENDER_PHONE,
}

missing_config = [name for name, value in REQUIRED_CONFIG.items() if not value]
if missing_config:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_config)
    )
