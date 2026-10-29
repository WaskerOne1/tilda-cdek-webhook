import json
import asyncio

import pytest
from fastapi import HTTPException

from app import transformer
from app import main as app_main
from app.cdek_client import CDEKClient
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


def test_create_order_uses_tariff_136_only_after_tarifflist_confirms_it(monkeypatch):
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
        return {"success": True, "status_code": 202, "data": {"entity": {"number": payload["number"]}}}

    monkeypatch.setattr(app_main.cdek, "calculate_tariff_list", fake_tariff_list)
    monkeypatch.setattr(app_main.cdek, "create_order", fake_create_order)

    response = asyncio.run(app_main.create_order(order_input))

    assert response["entity"]["number"] == "TST-TARIFF-136"
    assert captured["tariff_request"]["shipment_point"] == "TEST-SHIPMENT-PVZ"
    assert captured["tariff_request"]["delivery_point"] == "MSK481"
    assert captured["order_payload"]["tariff_code"] == 136


def test_create_order_does_not_call_order_api_if_tariff_136_is_unavailable(monkeypatch):
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

    with pytest.raises(HTTPException, match="Preferred tariff 136 is unavailable"):
        asyncio.run(app_main.create_order(order_input))

    assert create_order_called is False
