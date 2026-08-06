import csv
from pathlib import Path

from app.logger import logger
from app.models.order import Order


class Catalog:
    """
    Загружает каталог товаров один раз
    и умеет дополнять Order весом и габаритами.
    """

    def __init__(self, csv_path: str = "catalog.csv"):
        self.products = {}

        path = Path(csv_path)

        if not path.exists():
            logger.error(f"Каталог не найден: {path.resolve()}")
            return

        with open(path, "r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:

                external_id = row.get("externalid", "").strip()

                if not external_id:
                    continue

                self.products[external_id] = row

        logger.info(f"Каталог загружен. Товаров: {len(self.products)}")

    def fill_order(self, order: Order) -> Order:
        """
        Заполняет вес и габариты всех товаров заказа.
        """

        for item in order.items:

            product = self.products.get(item.external_id)

            if product is None:
                logger.error(
                    f"Товар не найден в каталоге. externalid={item.external_id}"
                )
                continue

            item.weight = self._to_float(product.get("weight"))

            item.length = self._to_int(product.get("pack_x"))

            item.width = self._to_int(product.get("pack_y"))

            item.height = self._to_int(product.get("pack_z"))

            logger.info(
                f"Каталог: {item.name} "
                f"(вес={item.weight} кг "
                f"{item.length}x{item.width}x{item.height})"
            )

        return order

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(float(str(value).replace(",", ".")))
        except (TypeError, ValueError):
            return 0