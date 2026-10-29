import pytest

from app import transformer

@pytest.fixture(autouse=True)
def configured_sender_route(monkeypatch):
    monkeypatch.setattr(transformer, "SENDER_SHIPMENT_POINT", "TEST-SHIPMENT-PVZ")
    monkeypatch.setattr(transformer, "DEFAULT_TARIFF_CODE", "21")
