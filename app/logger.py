from loguru import logger
import sys

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | {message}",
)


def log_response(response_data):
    if isinstance(response_data, list):
        logger.info("CDEK response received: list with {} items", len(response_data))
        return

    if isinstance(response_data, dict):
        logger.info("CDEK response received: object with {} fields", len(response_data))
        return

    logger.info("CDEK response received: {}", type(response_data).__name__)