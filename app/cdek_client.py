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

        self.authorize()

    def authorize(self):
        """
        Получает OAuth токен и сохраняет его в Session.
        """

        logger.info("Получаем OAuth токен...")

        token_data = get_token()

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
        """
        Проверяет срок действия токена.
        """

        return datetime.now() >= self.token_expires

    def ensure_token(self):
        """
       Если токен истек — получает новый.
        """

        if self.is_token_expired():

            logger.warning("OAuth токен истек. Получаем новый...")

            self.authorize()

    def _request(self, method: str, endpoint: str, **kwargs):
        """
        Универсальный метод выполнения HTTP-запросов.
        """

        self.ensure_token()

        url = f"{self.base_url}{endpoint}"

        logger.info(f"{method} {url}")

        response = self.session.request(
            method=method,
            url=url,
            **kwargs,
        )

        logger.info(f"Статус ответа: {response.status_code}")

        if not response.ok:

            logger.error(response.text)

            response.raise_for_status()

        if response.content:
            return response.json()

        return None

    def calculate_tariff(self, data: dict):
        """
        Расчет стоимости доставки.
        """

        return self._request(
            "POST",
            "/v2/calculator/tariff",
            json=data,
        )

    def create_order(self, order: dict):
        """
        Создание заказа.
        """

        return self._request(
            "POST",
            "/v2/orders",
            json=order,
        )

    def get_order(self, uuid: str):
        """
        Получение заказа по UUID.
        """

        return self._request(
            "GET",
            f"/v2/orders/{uuid}",
        )