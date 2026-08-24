import json

from app.models.tariff import TariffRequest
from app.transformer import parse_order_payload, transform_order, transform_tariff


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
    assert pkg["weight"] == 200
    assert pkg["length"] == 18
    assert pkg["width"] == 16
    assert pkg["height"] == 8
    assert pkg["items"][0]["amount"] == 1


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
    assert len(result["packages"]) == 2

    for pkg in result["packages"]:
        assert pkg["weight"] == 200
        assert pkg["length"] == 18
        assert pkg["width"] == 16
        assert pkg["height"] == 8
        assert pkg["items"][0]["amount"] == 1


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
    assert len(result["packages"]) == 2
    ware_keys = [pkg["items"][0]["ware_key"] for pkg in result["packages"]]
    assert ware_keys == ["SKU-1", "SKU-2"]


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
    assert len(result["packages"]) == 2
    for pkg in result["packages"]:
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
    assert "delivery_point" not in result
    assert "to_location" in result
    assert result["to_location"]["city"] == "Москва"


def test_h_calculate_transform_uses_same_units_and_route_logic():
    data = TariffRequest(
        tariff_code=136,
        from_code=44,
        to_code=44,
        from_address="Москва, ул. Ленина, 1",
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
    assert result["from_location"]["address"] == "Москва, ул. Ленина, 1"
    assert result["to_location"]["code"] == 44
    assert result["delivery_point"] == "MSK481"


def test_h2_calculate_transform_fractional_dimensions_use_ceil():
    data = TariffRequest(
        tariff_code=136,
        from_code=44,
        to_code=44,
        from_address="Москва, ул. Ленина, 1",
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
