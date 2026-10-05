"""
Server logging configuration for writing activity to logs/server.log.
"""

import logging
from shared.config import LOGS_DIR

LOG_FILE = LOGS_DIR / "server.log"

logger = logging.getLogger("HybridServer")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_formatter = logging.Formatter("[%(asctime)s] [%(threadName)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
file_handler.setFormatter(file_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)


def log_event(message: str, level: str = "info") -> None:
    if level.lower() == "info":
        logger.info(message)
    elif level.lower() == "warning":
        logger.warning(message)
    elif level.lower() == "error":
        logger.error(message)
