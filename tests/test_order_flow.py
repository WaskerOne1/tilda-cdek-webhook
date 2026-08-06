import json
from app.transformer import parse_order_payload, transform_order


def test_transform_with_delivery_point():
    payload = {
        'Name': 'Тест',
        'Phone': '+79990000000',
        'orderid': 'TST-001',
        'tildapayment': json.dumps({
            'products': [],
            'delivery': {
                'city': 'Москва',
                'pickup-name': 'MSK65, Москва, ул. Динамовская',
                'pickup-id': 'MSK65',
                'postalcode': '109044',
            }
        })
    }

    order = parse_order_payload(payload)
    result = transform_order(order)

    assert 'delivery_point' in result
    assert result['delivery_point'] == 'MSK65'
    # when delivery_point is present, to_location must not be included
    assert 'to_location' not in result


def test_transform_without_delivery_point():
    payload = {
        'Name': 'Тест',
        'Phone': '+79990000000',
        'orderid': 'TST-002',
        'tildapayment': json.dumps({
            'products': [],
            'delivery': {
                'city': 'Москва',
                'pickup-name': '',
                'postalcode': '109044',
            }
        })
    }

    order = parse_order_payload(payload)
    result = transform_order(order)

    assert 'delivery_point' not in result
    assert 'to_location' in result
    assert result['to_location'].get('city') == 'Москва'
    assert 'address' in result['to_location'] or 'postal_code' in result['to_location']
