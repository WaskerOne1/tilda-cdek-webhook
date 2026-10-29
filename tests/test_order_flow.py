import json
import sqlite3
from pathlib import Path

import pytest

from app import main as app_main
from app import transformer
from app.cdek_client import CDEKClient
from app import cdek_client as cdek_client_module
from app.models.tariff import TariffRequest
from app.transformer import (
    parse_order_payload,
    select_preferred_tariff,
    transform_order,
    transform_order_tariff_list,
    transform_tariff,
    transform_tariff_list,
)


def _build_tilda_payload(products: list[dict], delivery: dict, order_id: str = "TST-001") -> dict:
    return {
        "Name": "Тест",
        "Phone": "+79990000000",
        "orderid": order_id,
        "tildapayment": json.dumps(
            {
                "products": products,
                "delivery": delivery,
            }
        ),
    }


def _single_product(quantity: int = 1, pack_m: str = "200", pack_x: str = "180", pack_y: str = "160", pack_z: str = "80", recid: str = "TEST-001", name: str = "Тестовый товар") -> dict:
    return {
        "name": name,
        "price": 0,
        "recid": recid,
        "pack_m": pack_m,
        "pack_x": pack_x,
        "pack_y": pack_y,
        "pack_z": pack_z,
        "quantity": quantity,
        "amount": 0,
    }


def _webhook_headers(token: str = "test-webhook-secret") -> dict[str, str]:
    return {"X-Tilda-Webhook-Token": token}


def _fail_on_cdek_calls(monkeypatch):
    calls = []

    def fail(method_name):
        def unexpected_call(*args, **kwargs):
            calls.append(method_name)
            raise AssertionError(f"Unexpected CDEK method call: {method_name}")

        return unexpected_call

    for method_name in ("get_city_code", "calculate_tariff_list", "create_order"):
        monkeypatch.setattr(app_main.cdek, method_name, fail(method_name))
    return calls


def test_a_single_product_package_units_converted_mm_to_cm():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=1)],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
    )

    result = transform_order(parse_order_payload(payload))
    assert len(result["packages"]) == 1

    pkg = result["packages"][0]
    assert result["tariff_code"] == 21
    assert pkg["number"] == "PKG-1"
    assert pkg["weight"] == 200
    assert pkg["length"] == 18
    assert pkg["width"] == 16
    assert pkg["height"] == 8
    assert pkg["items"][0]["amount"] == 1
    assert result["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert result["delivery_point"] == "MSK481"
    assert "from_location" not in result
    assert "to_location" not in result


def test_b_single_product_quantity_2_creates_two_packages():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=2)],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
        order_id="TST-002",
    )

    result = transform_order(parse_order_payload(payload))
    packages = result["packages"]
    assert [pkg["number"] for pkg in packages] == ["PKG-1", "PKG-2"]
    assert [pkg["weight"] for pkg in packages] == [200, 200]
    assert [(pkg["length"], pkg["width"], pkg["height"]) for pkg in packages] == [
        (18, 16, 8),
        (18, 16, 8),
    ]
    assert [len(pkg["items"]) for pkg in packages] == [1, 1]
    assert [pkg["items"][0]["ware_key"] for pkg in packages] == [
        "TEST-001",
        "TEST-001",
    ]
    assert [pkg["items"][0]["amount"] for pkg in packages] == [1, 1]
    assert all(pkg["weight"] != 400 for pkg in packages)


def test_c_two_different_products_create_two_packages():
    payload = _build_tilda_payload(
        products=[
            _single_product(quantity=1, recid="SKU-1", name="Товар 1"),
            _single_product(quantity=1, recid="SKU-2", name="Товар 2"),
        ],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
        order_id="TST-003",
    )

    result = transform_order(parse_order_payload(payload))
    packages = result["packages"]
    assert [pkg["number"] for pkg in packages] == ["PKG-1", "PKG-2"]
    assert [len(pkg["items"]) for pkg in packages] == [1, 1]
    ware_keys = [pkg["items"][0]["ware_key"] for pkg in packages]
    assert ware_keys == ["SKU-1", "SKU-2"]
    assert [pkg["items"][0]["amount"] for pkg in packages] == [1, 1]
    assert [pkg["weight"] for pkg in packages] == [200, 200]


def test_d_two_identical_quantity_2_create_two_packages():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=2, recid="SKU-SAME", name="Одинаковый")],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
        order_id="TST-004",
    )

    result = transform_order(parse_order_payload(payload))
    packages = result["packages"]
    assert [pkg["number"] for pkg in packages] == ["PKG-1", "PKG-2"]
    assert [pkg["weight"] for pkg in packages] == [200, 200]
    assert [(pkg["length"], pkg["width"], pkg["height"]) for pkg in packages] == [
        (18, 16, 8),
        (18, 16, 8),
    ]
    assert [len(pkg["items"]) for pkg in packages] == [1, 1]
    assert all(pkg["weight"] != 400 for pkg in packages)
    for pkg in packages:
        assert pkg["items"][0]["ware_key"] == "SKU-SAME"
        assert pkg["items"][0]["amount"] == 1


def test_e_fractional_dimensions_mm_to_cm_with_ceil_rounding():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=1, pack_x="25", pack_y="9", pack_z="9")],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
        order_id="TST-005",
    )

    result = transform_order(parse_order_payload(payload))
    pkg = result["packages"][0]
    assert pkg["length"] == 3
    assert pkg["width"] == 1
    assert pkg["height"] == 1


def test_f_delivery_point_payload_without_to_location():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=1)],
        delivery={
            "city": "Москва",
            "pickup-id": "MSK481",
            "pickup-name": "MSK481, Москва",
            "postalcode": "109652",
        },
        order_id="TST-006",
    )

    result = transform_order(parse_order_payload(payload))
    assert result["delivery_point"] == "MSK481"
    assert "to_location" not in result


def test_g_courier_payload_with_to_location_without_delivery_point():
    payload = _build_tilda_payload(
        products=[_single_product(quantity=1)],
        delivery={
            "city": "Москва",
            "pickup-name": "",
            "postalcode": "109652",
        },
        order_id="TST-007",
    )

    result = transform_order(parse_order_payload(payload))
    assert result["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert "from_location" not in result
    assert "delivery_point" not in result
    assert "to_location" in result
    assert result["to_location"]["city"] == "Москва"


def test_h_calculate_transform_uses_same_units_and_route_logic():
    data = TariffRequest(
        tariff_code=136,
        from_code=44,
        to_code=44,
        from_address="Москва, ул. Ленина, 1",
        shipment_point="TEST-SHIPMENT-PVZ",
        delivery_point="MSK481",
        weight=200,
        length=180,
        width=160,
        height=80,
    )

    result = transform_tariff(data)
    pkg = result["packages"][0]

    assert pkg["weight"] == 200
    assert pkg["length"] == 18
    assert pkg["width"] == 16
    assert pkg["height"] == 8
    assert result["from_location"]["code"] == 44
    assert result["from_location"]["address"] == "Москва, ул. Ленина, 1"
    assert result["to_location"]["code"] == 44
    assert result["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert result["delivery_point"] == "MSK481"


def test_h2_calculate_transform_fractional_dimensions_use_ceil():
    data = TariffRequest(
        tariff_code=136,
        from_code=44,
        to_code=44,
        from_address="Москва, ул. Ленина, 1",
        shipment_point="TEST-SHIPMENT-PVZ",
        delivery_point="MSK481",
        weight=200,
        length=25,
        width=9,
        height=9,
    )

    result = transform_tariff(data)
    pkg = result["packages"][0]

    assert pkg["weight"] == 200
    assert pkg["length"] == 3
    assert pkg["width"] == 1
    assert pkg["height"] == 1


def test_missing_sender_shipment_point_raises_configuration_error(monkeypatch):
    monkeypatch.setattr(transformer, "SENDER_SHIPMENT_POINT", None)
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
    )

    with pytest.raises(ValueError, match="SENDER_SHIPMENT_POINT"):
        transform_order(parse_order_payload(payload))


@pytest.mark.parametrize("tariff_code", [None, "", "not-a-code", "0", "21.5"])
def test_missing_or_invalid_tariff_config_raises_without_fallback(
    monkeypatch, tariff_code
):
    monkeypatch.setattr(transformer, "DEFAULT_TARIFF_CODE", tariff_code)
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
    )

    with pytest.raises(ValueError, match="DEFAULT_TARIFF_CODE"):
        transform_order(parse_order_payload(payload))


def test_tariff_list_payload_contains_city_and_pvz_route_without_tariff_code():
    data = TariffRequest(
        tariff_code=21,
        from_code=44,
        to_code=44,
        shipment_point="TEST-SHIPMENT-PVZ",
        delivery_point="MSK481",
        weight=200,
        length=180,
        width=160,
        height=80,
    )

    result = transform_tariff_list(data)

    assert "tariff_code" not in result
    assert result["from_location"] == {"code": 44}
    assert result["to_location"] == {"code": 44}
    assert result["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert result["delivery_point"] == "MSK481"
    assert result["packages"] == [
        {"weight": 200, "length": 18, "width": 16, "height": 8}
    ]


def test_cdek_client_uses_tariff_list_endpoint_without_network(monkeypatch):
    client = CDEKClient()
    captured = {}

    def fake_request(method, endpoint, **kwargs):
        captured.update(method=method, endpoint=endpoint, **kwargs)
        return {"success": True, "status_code": 200, "data": {"tariff_codes": []}}

    monkeypatch.setattr(client, "_request", fake_request)
    payload = {"type": 1, "from_location": {"code": 44}, "to_location": {"code": 44}}

    result = client.calculate_tariff_list(payload)

    assert result["success"] is True
    assert captured == {
        "method": "POST",
        "endpoint": "/v2/calculator/tarifflist",
        "json": payload,
    }

def test_cdek_client_does_not_log_request_or_response_pii(monkeypatch):
    logged_messages = []

    def capture_log(message, *args):
        logged_messages.append(str(message).format(*args))

    class FakeResponse:
        ok = True
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "recipient": {
                    "phone": "+70000000000",
                    "address": "Sensitive test address",
                }
            }

    client = CDEKClient()
    monkeypatch.setattr(cdek_client_module.logger, "info", capture_log)
    monkeypatch.setattr(client, "ensure_token", lambda: None)
    monkeypatch.setattr(client.session, "request", lambda **kwargs: FakeResponse())

    result = client._request(
        "POST",
        "/v2/orders",
        json={
            "recipient": {
                "phone": "+70000000000",
                "address": "Sensitive test address",
            }
        },
    )

    assert result["success"] is True
    all_logs = " ".join(logged_messages)
    assert "+70000000000" not in all_logs
    assert "Sensitive test address" not in all_logs


def test_preferred_tariff_136_is_selected_over_483():
    response = {
        "tariff_codes": [
            {"tariff_code": 483, "tariff_name": "Экспресс склад-склад"},
            {"tariff_code": 136, "tariff_name": "Посылка склад-склад"},
        ]
    }

    assert select_preferred_tariff(response) == 136


def test_missing_preferred_tariff_raises_without_falling_back_to_483():
    response = {
        "tariff_codes": [
            {"tariff_code": 483, "tariff_name": "Экспресс склад-склад"},
        ]
    }

    with pytest.raises(ValueError, match="Preferred tariff 136 is unavailable"):
        select_preferred_tariff(response)


def test_order_tariff_list_payload_uses_order_packages_and_both_pvz_codes():
    order = parse_order_payload(
        _build_tilda_payload(
            products=[_single_product(quantity=2)],
            delivery={"city": "Москва", "pickup-id": "MSK481"},
        )
    )

    request = transform_order_tariff_list(
        order,
        sender_city_code=44,
        recipient_city_code=44,
    )

    assert request["from_location"] == {"code": 44}
    assert request["to_location"] == {"code": 44}
    assert request["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert request["delivery_point"] == "MSK481"
    assert len(request["packages"]) == 2
    assert all(package["items"][0]["amount"] == 1 for package in request["packages"])


@pytest.mark.parametrize(
    "content_type", ["application/json", "application/x-www-form-urlencoded"]
)
def test_create_order_uses_tariff_136_only_after_tarifflist_confirms_it(
    webhook_call, monkeypatch, content_type
):
    order_input = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
        order_id="TST-TARIFF-136",
    )
    captured = {}

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)

    def fake_tariff_list(request):
        captured["tariff_request"] = request
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "tariff_codes": [
                    {"tariff_code": 483},
                    {"tariff_code": 136},
                ]
            },
        }

    def fake_create_order(payload):
        captured["order_payload"] = payload
        return {
            "success": True,
            "status_code": 202,
            "data": {"entity": {"number": payload["number"], "uuid": "uuid-test-136"}},
        }

    monkeypatch.setattr(app_main.cdek, "calculate_tariff_list", fake_tariff_list)
    monkeypatch.setattr(app_main.cdek, "create_order", fake_create_order)

    response = webhook_call(
        order_input,
        headers=_webhook_headers(),
        content_type=content_type,
    )

    assert response.status_code == 200
    assert response.json()["entity"]["number"] == "TST-TARIFF-136"
    assert captured["tariff_request"]["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert captured["tariff_request"]["delivery_point"] == "MSK481"
    assert captured["order_payload"]["tariff_code"] == 136


def test_create_order_does_not_call_order_api_if_tariff_136_is_unavailable(
    webhook_call, monkeypatch
):
    order_input = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
    )
    create_order_called = False

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)
    monkeypatch.setattr(
        app_main.cdek,
        "calculate_tariff_list",
        lambda request: {
            "success": True,
            "status_code": 200,
            "data": {"tariff_codes": [{"tariff_code": 483}]},
        },
    )

    def unexpected_create_order(payload):
        nonlocal create_order_called
        create_order_called = True
        raise AssertionError("create_order must not be called without tariff 136")

    monkeypatch.setattr(app_main.cdek, "create_order", unexpected_create_order)

    response = webhook_call(order_input, headers=_webhook_headers())

    assert response.status_code == 400
    assert "Preferred tariff 136 is unavailable" in response.json()["detail"]
    assert create_order_called is False


def test_orderid_can_retry_after_pre_create_tariff_failure(webhook_call, monkeypatch):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
        order_id="TST-RETRY-AFTER-TARIFF-FAILURE",
    )
    tariff_attempts = 0
    create_attempts = 0

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)

    def tariff_list(request):
        nonlocal tariff_attempts
        tariff_attempts += 1
        tariff_codes = [] if tariff_attempts == 1 else [{"tariff_code": 136}]
        return {"success": True, "status_code": 200, "data": {"tariff_codes": tariff_codes}}

    def create_order(order):
        nonlocal create_attempts
        create_attempts += 1
        return {
            "success": True,
            "status_code": 202,
            "data": {"entity": {"uuid": "uuid-after-retry", "number": order["number"]}},
        }

    monkeypatch.setattr(app_main.cdek, "calculate_tariff_list", tariff_list)
    monkeypatch.setattr(app_main.cdek, "create_order", create_order)

    first = webhook_call(payload, headers=_webhook_headers())
    second = webhook_call(payload, headers=_webhook_headers())

    assert first.status_code == 400
    assert "Preferred tariff 136 is unavailable" in first.json()["detail"]
    assert second.status_code == 200
    assert second.json()["entity"]["uuid"] == "uuid-after-retry"
    assert tariff_attempts == 2
    assert create_attempts == 1


def test_orderid_can_retry_after_payload_build_failure(webhook_call, monkeypatch):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
        order_id="TST-RETRY-AFTER-BUILD-FAILURE",
    )
    transform_attempts = 0
    create_attempts = 0
    original_transform_order = app_main.transform_order

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)
    monkeypatch.setattr(
        app_main.cdek,
        "calculate_tariff_list",
        lambda request: {
            "success": True,
            "status_code": 200,
            "data": {"tariff_codes": [{"tariff_code": 136}]},
        },
    )

    def fail_transform_once(order, tariff_code=None):
        nonlocal transform_attempts
        transform_attempts += 1
        if transform_attempts == 1:
            raise ValueError("simulated payload build failure")
        return original_transform_order(order, tariff_code=tariff_code)

    def create_order(order):
        nonlocal create_attempts
        create_attempts += 1
        return {
            "success": True,
            "status_code": 202,
            "data": {"entity": {"uuid": "uuid-after-build-retry", "number": order["number"]}},
        }

    monkeypatch.setattr(app_main, "transform_order", fail_transform_once)
    monkeypatch.setattr(app_main.cdek, "create_order", create_order)

    first = webhook_call(payload, headers=_webhook_headers())
    second = webhook_call(payload, headers=_webhook_headers())

    assert first.status_code == 400
    assert first.json()["detail"] == "simulated payload build failure"
    assert second.status_code == 200
    assert second.json()["entity"]["uuid"] == "uuid-after-build-retry"
    assert transform_attempts == 2
    assert create_attempts == 1


def test_webhook_without_configured_secret_is_closed(webhook_call, monkeypatch):
    monkeypatch.setattr(app_main, "TILDA_WEBHOOK_SECRET", None)
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call({"test": "test"})

    assert response.status_code == 503
    assert cdek_calls == []


def test_create_order_openapi_documents_json_and_form_bodies():
    operation = app_main.app.openapi()["paths"]["/create-order"]["post"]
    content = operation["requestBody"]["content"]

    assert "application/json" in content
    assert "application/x-www-form-urlencoded" in content


@pytest.mark.parametrize("headers", [{}, {"X-Tilda-Webhook-Token": "wrong-token"}])
def test_webhook_rejects_missing_or_invalid_header_without_cdek(
    webhook_call, monkeypatch, headers
):
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call(
        {"test": "test"},
        headers=headers,
        query_string="X-Tilda-Webhook-Token=test-webhook-secret",
    )

    assert response.status_code == 401
    assert cdek_calls == []


def test_authenticated_form_test_test_returns_ok_without_cdek(webhook_call, monkeypatch):
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call(
        {"test": "test", "orderid": "TEST-SERVICE-HOOK"},
        headers=_webhook_headers(),
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Tilda webhook test received"}
    assert cdek_calls == []
    assert not Path(app_main.ORDER_IDEMPOTENCY_DB_PATH).exists()


def test_authenticated_json_test_test_returns_ok_without_cdek(webhook_call, monkeypatch):
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call(
        {"test": "test", "orderid": "TEST-SERVICE-HOOK-JSON"},
        headers=_webhook_headers(),
    )

    assert response.status_code == 200
    assert cdek_calls == []
    assert not Path(app_main.ORDER_IDEMPOTENCY_DB_PATH).exists()


def test_test_test_without_valid_secret_is_rejected(webhook_call, monkeypatch):
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call(
        {"test": "test", "orderid": "TEST-UNAUTHENTICATED"},
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 401
    assert cdek_calls == []


def test_real_webhook_without_orderid_is_rejected_before_cdek(webhook_call, monkeypatch):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
    )
    payload.pop("orderid")
    cdek_calls = _fail_on_cdek_calls(monkeypatch)
    response = webhook_call(payload, headers=_webhook_headers())

    assert response.status_code == 400
    assert response.json()["detail"] == "Tilda orderid is required"
    assert cdek_calls == []


def test_orderid_inside_tildapayment_is_used_when_payment_is_empty(
    webhook_call, monkeypatch
):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
    )
    payload.pop("orderid")
    payment_data = json.loads(payload["tildapayment"])
    payment_data["orderid"] = "TST-NESTED-ORDERID"
    payload["tildapayment"] = json.dumps(payment_data)
    payload["payment"] = {}
    captured = {}

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)
    monkeypatch.setattr(
        app_main.cdek,
        "calculate_tariff_list",
        lambda request: {
            "success": True,
            "status_code": 200,
            "data": {"tariff_codes": [{"tariff_code": 136}]},
        },
    )

    def fake_create_order(order):
        captured.update(order)
        return {
            "success": True,
            "status_code": 202,
            "data": {"entity": {"uuid": "uuid-nested", "number": order["number"]}},
        }

    monkeypatch.setattr(app_main.cdek, "create_order", fake_create_order)
    response = webhook_call(payload, headers=_webhook_headers())

    assert response.status_code == 200
    assert captured["number"] == "TST-NESTED-ORDERID"


def test_successful_orderid_repeat_returns_saved_result_without_second_cdek_call(
    webhook_call, monkeypatch
):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
        order_id="TST-IDEMPOTENT-1",
    )
    calls = {"tarifflist": 0, "create_order": 0}

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)

    def fake_tariff_list(request):
        calls["tarifflist"] += 1
        return {
            "success": True,
            "status_code": 200,
            "data": {"tariff_codes": [{"tariff_code": 136}]},
        }

    def fake_create_order(order):
        calls["create_order"] += 1
        return {
            "success": True,
            "status_code": 202,
            "data": {"entity": {"uuid": "uuid-idempotent-1", "number": order["number"]}},
        }

    monkeypatch.setattr(app_main.cdek, "calculate_tariff_list", fake_tariff_list)
    monkeypatch.setattr(app_main.cdek, "create_order", fake_create_order)

    first = webhook_call(payload, headers=_webhook_headers())
    second = webhook_call(payload, headers=_webhook_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["entity"]["uuid"] == "uuid-idempotent-1"
    assert calls == {"tarifflist": 1, "create_order": 1}
    with sqlite3.connect(app_main.ORDER_IDEMPOTENCY_DB_PATH) as connection:
        row = connection.execute(
            "SELECT state, cdek_uuid, result_json FROM tilda_orders WHERE order_id = ?",
            ("TST-IDEMPOTENT-1",),
        ).fetchone()
    assert row[0] == "succeeded"
    assert row[1] == "uuid-idempotent-1"
    assert json.loads(row[2]) == first.json()


def test_ambiguous_cdek_result_blocks_retry_for_same_orderid(webhook_call, monkeypatch):
    payload = _build_tilda_payload(
        products=[_single_product()],
        delivery={"city": "Москва", "pickup-id": "MSK481"},
        order_id="TST-IDEMPOTENT-UNCERTAIN",
    )
    create_calls = 0

    monkeypatch.setattr(app_main.cdek, "get_city_code", lambda city: 44)
    monkeypatch.setattr(
        app_main.cdek,
        "calculate_tariff_list",
        lambda request: {
            "success": True,
            "status_code": 200,
            "data": {"tariff_codes": [{"tariff_code": 136}]},
        },
    )

    def ambiguous_create_order(order):
        nonlocal create_calls
        create_calls += 1
        raise TimeoutError("simulated CDEK timeout")

    monkeypatch.setattr(app_main.cdek, "create_order", ambiguous_create_order)

    first = webhook_call(payload, headers=_webhook_headers())
    second = webhook_call(payload, headers=_webhook_headers())

    assert first.status_code == 502
    assert second.status_code == 409
    assert "uncertain" in second.json()["detail"]
    assert create_calls == 1
