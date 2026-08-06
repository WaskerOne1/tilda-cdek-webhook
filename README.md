# Tilda → CDEK Webhook

## Описание
Сервис принимает вебхуки из Tilda, преобразует данные заказа и создаёт заказы в API СДЭК. Подходит для интеграции интернет‑магазина на Tilda и автоматической передачи заказов в СДЭК.

## Возможности
- Приём webhook от Tilda
- Парсинг заказа в внутреннюю модель
- Трансформация в формат API СДЭК
- Создание заказа в СДЭК и получение статуса
- Поиск городов и пунктов выдачи (ПВЗ)
- Простые unit‑тесты для основных сценариев

## Структура проекта

app/
- main.py — FastAPI приложение и маршруты
- auth.py — получение токена у СДЭК
- cdek_client.py — клиент для вызовов API СДЭК
- transformer.py — преобразование Tilda → внутренняя модель → СДЭК
- catalog.py — (опционально) загрузка каталога товаров
- models/ — dataclass-модели заказа, адреса, товара и пр.

docs/
- minimal-order.json — пример минимального запроса в СДЭК

tests/
- test_order_flow.py — базовые тесты преобразования

README.md — этот файл

## Требования
- Python 3.12+
- Рекомендуется работать в виртуальном окружении

## Установка

```bash
git clone <repo_url>
cd sdek-api
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка
Скопируйте `.env.example` в `.env` и заполните значения:

```
CDEK_API=https://api.edu.cdek.ru
CLIENT_ID=
CLIENT_SECRET=
SENDER_LOCATION_CODE=
SENDER_LOCATION_ADDRESS=
SENDER_PHONE=
```

Не коммитьте файл `.env` в репозиторий.

## Запуск

```bash
# локально
uvicorn app.main:app --reload
# приложение будет доступно по http://127.0.0.1:8000
```

## Swagger
Документация OpenAPI: http://127.0.0.1:8000/docs

## Тесты

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

## Переключение TEST / PROD
- По умолчанию примеры и тесты используют `api.edu.cdek.ru` (sandbox).
- Для работы с production укажите в `.env` `CDEK_API=https://api.cdek.ru` и используйте production `CLIENT_ID/SECRET`.

## Политика безопасности / приватность
- Не храните реальные ключи и персональные данные в репозитории.
- Для публикации создавайте `.env.example` и используйте инструменты CI для секретов.

## Лицензия
MIT
