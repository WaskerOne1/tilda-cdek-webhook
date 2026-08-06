import json
from app.transformer import parse_order_payload, transform_order
payload = {
    'Name': 'Кирилл',
    'Phone': '+7 (916) 077-47-40',
    'Checkbox': 'yes',
    'payment': {
        'orderid': '2137044711',
        'products': [
            {
                'name': 'KORSHUN Шпатель для внутренних углов ВУ с зубчатыми пластинами',
                'quantity': 1,
                'amount': 4390,
                'externalid': '50e24136-8198-11ef-acca-2cf05d712365',
                'price': '4390'
            }
        ],
        'amount': '4740',
        'subtotal': '4390',
        'delivery': 'Доставка по городу',
        'delivery_price': 350,
        'delivery_fio': 'Иванков Кирилл Витальевич',
        'delivery_city': 'Москва',
        'delivery_address': 'RU: 121351, Москва, ул Ярцевская, 1А, struct.1',
        'delivery_comment': '',
        'delivery_zip': '121351'
    },
    'formid': 'form2307383831',
    'formname': 'Cart'
}
order = parse_order_payload(payload)
print(order)
print(json.dumps(transform_order(order), ensure_ascii=False, indent=2))
