import os

# Prevent tests from reading the developer's local .env during module imports.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.update(
    {
        "CDEK_API": "https://cdek.test.invalid",
        "CLIENT_ID": "test-client-id",
        "CLIENT_SECRET": "test-client-secret",
        "SENDER_PHONE": "+70000000000",
        "SENDER_SHIPMENT_POINT": "TEST-SHIPMENT-PVZ",
        "SENDER_CITY_CODE": "44",
        "DEFAULT_TARIFF_CODE": "21",
        "TILDA_WEBHOOK_SECRET": "test-webhook-secret",
        "ORDER_IDEMPOTENCY_DB_PATH": "unused-test-default.sqlite3",
    }
)
