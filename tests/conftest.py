import asyncio
import json
from dataclasses import dataclass
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import transformer
from app import main as app_main


@dataclass
class LocalResponse:
    status_code: int
    body: bytes

    def json(self):
        return json.loads(self.body)


@pytest.fixture(autouse=True)
def configured_sender_route(monkeypatch):
    monkeypatch.setattr(transformer, "SENDER_SHIPMENT_POINT", "TEST-SHIPMENT-PVZ")
    monkeypatch.setattr(transformer, "DEFAULT_TARIFF_CODE", "21")


@pytest.fixture
def webhook_call(monkeypatch, tmp_path):
    monkeypatch.setattr(app_main, "TILDA_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(
        app_main,
        "ORDER_IDEMPOTENCY_DB_PATH",
        str(tmp_path / "idempotency.sqlite3"),
    )

    def call(payload, headers=None, content_type="application/json", query_string=""):
        if content_type == "application/x-www-form-urlencoded":
            body = urlencode(payload).encode("utf-8")
        else:
            body = json.dumps(payload).encode("utf-8")

        request_headers = [
            (name.lower().encode("ascii"), value.encode("latin-1"))
            for name, value in (headers or {}).items()
        ]
        request_headers.append((b"content-type", content_type.encode("ascii")))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/create-order",
            "raw_path": b"/create-order",
            "query_string": query_string.encode("ascii"),
            "headers": request_headers,
            "server": ("testserver", 80),
            "client": ("testclient", 12345),
        }
        body_sent = False

        async def receive():
            nonlocal body_sent
            if body_sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(scope, receive)
        try:
            response_data = asyncio.run(app_main.create_order(request))
            return LocalResponse(200, json.dumps(response_data).encode("utf-8"))
        except HTTPException as error:
            return LocalResponse(
                error.status_code,
                json.dumps({"detail": error.detail}).encode("utf-8"),
            )

    return call
