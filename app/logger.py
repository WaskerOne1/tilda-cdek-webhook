from loguru import logger
import sys
import json

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | {message}",
)


def log_response(response_data):
    """
    Красивое логирование ответов СДЭК.
    """

    if isinstance(response_data, list):

        logger.info(f"Получено объектов: {len(response_data)}")

        if response_data:

            logger.info(
                "Первый объект:\n{}",
                json.dumps(
                    response_data[0],
                    ensure_ascii=False,
                    indent=4,
                ),
            )

        return

    if isinstance(response_data, dict):

        logger.info(
            "Ответ:\n{}",
            json.dumps(
                response_data,
                ensure_ascii=False,
                indent=4,
            ),
        )

        return

    logger.info(response_data)