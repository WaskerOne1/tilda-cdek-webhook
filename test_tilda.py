import json
from app.transformer import parse_order_payload, transform_order
from app.logger import logger

payload = {
    'Name': 'Иван Иванов',
    'Phone': '+79990000000',
    'Checkbox': 'yes',
    'payment': {
        'orderid': 'TEST_ORDER_001',
        'products': [
            {
                'name': 'Шпатель для внутренних углов ВУ с зубчатыми пластинами',
                'quantity': 1,
                'amount': 4390,
                'externalid': 'SKU-TEST-001',
                'price': '4390'
            }
        ],
        'amount': '4740',
        'subtotal': '4390',
        'delivery': 'Доставка по городу',
        'delivery_price': 350,
        'delivery_fio': 'Иван Иванов',
        'delivery_city': 'Test City',
        'delivery_address': 'Test address',
        'delivery_comment': '',
        'delivery_zip': '000000'
    },
    'formid': 'FORM_TEST_001',
    'formname': 'Cart'
}
order = parse_order_payload(payload)
logger.info("%s", order)
logger.info(json.dumps(transform_order(order), ensure_ascii=False, indent=2))
