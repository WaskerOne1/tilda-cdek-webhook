import json
import requests

payload = {
    "Name": "Кирилл Иванков",
    "Phone": "+7 (916) 077-47-40",
    "orderid": "2137044711",
    "formid": "form1692749091",
    "tildapayment": json.dumps({
        "currency": "RUB",
        "amount": 4591.55,
        "system": "yakassa",
        "prodamount": 4100,
        "timezoneoffset": -180,
        "products": [
            {
                "name": "Шпатель регулируемый \"Коршун\" для внутренних углов",
                "price": 4100,
                "img": "https://static.tildacdn.com/stor3730-6534-4466-a364-653830306239/d183173e29faf61842a779ee7cbc651e.jpg",
                "recid": "1692768281",
                "lid": "810307545992",
                "pack_label": "lwh",
                "pack_m": "200",
                "pack_x": "180",
                "pack_y": "160",
                "pack_z": "80",
                "part_uids": [""],
                "gen_uid": "810307545992",
                "url": "https://korshun.tools/catalog-korshun/tproduct/810307545992-shpatel-reguliruemii-korshun-dlya-vnutre",
                "uid": "810307545992",
                "unit": "PCE",
                "portion": "1",
                "single": "y",
                "quantity": 1,
                "amount": 4100,
                "ts": 1785940248,
            }
        ],
        "delivery": {
            "name": "СДЭК",
            "price": 491.55,
            "freedl": 5000,
            "city": "Москва",
            "pickup-name": "MSK481, Москва, ул. Поречная",
            "pickup-id": "MSK481",
            "service-id": "1827683932",
            "hash": "1452fc622b6a6b792a63294a0bb3c3e9",
            "postalcode": "109652",
            "country": "ru",
            "lang": "RU",
        },
    }),
}

response = requests.post('http://127.0.0.1:8001/create-order', json=payload, timeout=60)
print(response.status_code)
print(response.text)
