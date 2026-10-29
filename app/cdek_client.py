import requests
from datetime import datetime, timedelta

from app.auth import get_token
from app.config import CDEK_API
from app.logger import logger


class CDEKClient:

    def __init__(self):
        self.base_url = CDEK_API
        self.session = requests.Session()
        self.token = None
        self.token_expires = None

    # -------------------------------------------------
    # Авторизация
    # -------------------------------------------------

    def authorize(self):
        logger.info("Получаем OAuth токен...")

        try:
            token_data = get_token()
        except requests.RequestException as exc:
            logger.error("Ошибка OAuth CDEK")
            raise RuntimeError("CDEK authorization failed") from exc

        self.token = token_data["access_token"]
        self.token_expires = datetime.now() + timedelta(
            seconds=token_data["expires_in"]
        )

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        )

        logger.success("OAuth токен успешно получен")

    def is_token_expired(self):
        return (
            self.token is None
            or self.token_expires is None
            or datetime.now() >= self.token_expires
        )

    def ensure_token(self):
        if self.is_token_expired():
            logger.warning("OAuth токен истек. Получаем новый...")
            self.authorize()

    # -------------------------------------------------
    # Универсальный запрос
    # -------------------------------------------------

    def _request(self, method: str, endpoint: str, **kwargs):
        try:
            self.ensure_token()
        except Exception as exc:
            logger.error("CDEK request failed before sending: %s", exc)
            return {
                "success": False,
                "status_code": 502,
                "data": str(exc),
            }

        url = f"{self.base_url}{endpoint}"

        logger.info("=" * 60)
        logger.info(f"{method} {url}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                **kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            response_data = None
            status_code = 502

            if hasattr(exc, "response") and exc.response is not None:
                try:
                    response_data = exc.response.json()
                except ValueError:
                    response_data = exc.response.text
                status_code = exc.response.status_code
            else:
                response_data = str(exc)

            logger.error("CDEK request failed (HTTP %s)", status_code)
            return {
                "success": False,
                "status_code": status_code,
                "data": response_data,
            }

        logger.info(f"HTTP {response.status_code}")

        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text

        return {
            "success": response.ok,
            "status_code": response.status_code,
            "data": response_data,
        }

    # -------------------------------------------------
    # Города
    # -------------------------------------------------

    def get_cities(
        self,
        city: str | None = None,
        country_code: str = "RU",
        size: int = 20,
        page: int = 0,
    ):

        params = {
            "country_codes": country_code,
            "size": size,
            "page": page,
        }

        if city:
            params["city"] = city

        return self._request(
            "GET",
            "/v2/location/cities",
            params=params,
        )

    def find_city(self, city: str):

        result = self.get_cities(city)

        if not result["success"]:
            return None

        cities = result["data"]

        if not cities:
            return None

        for item in cities:

            if item["city"].lower() == city.lower():
                return item

        return cities[0]

    def get_city_code(self, city: str):

        city_data = self.find_city(city)

        if city_data is None:
            return None

        return city_data["code"]

    # -------------------------------------------------
    # Пункты выдачи
    # -------------------------------------------------

    def get_offices(
        self,
        city: str | None = None,
        city_code: int | None = None,
        country_code: str = "RU",
    ):

        if city and city_code is None:

            city_code = self.get_city_code(city)

            if city_code is None:

                return {
                    "success": False,
                    "status_code": 404,
                    "data": f"Город '{city}' не найден",
                }

        params = {
            "country_code": country_code,
            "city_code": city_code,
            "type": "PVZ",
        }

        return self._request(
            "GET",
            "/v2/deliverypoints",
            params=params,
        )

    # -------------------------------------------------
    # Калькулятор
    # -------------------------------------------------

    def calculate_tariff(self, data: dict):

        return self._request(
            "POST",
            "/v2/calculator/tariff",
            json=data,
        )

    def calculate_tariff_list(self, data: dict):
        return self._request(
            "POST",
            "/v2/calculator/tarifflist",
            json=data,
        )

    # -------------------------------------------------
    # Заказы
    # -------------------------------------------------

    def create_order(self, order: dict):

        return self._request(
            "POST",
            "/v2/orders",
            json=order,
        )

    def get_order(self, uuid: str):

        return self._request(
            "GET",
            f"/v2/orders/{uuid}",
        )