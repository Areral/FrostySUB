import sys
import os
from loguru import logger

os.makedirs("data", exist_ok=True)

logger.remove()

# =======================
# КОНСОЛЬ GITHUB ACTIONS
# =======================
logger.add(
    sys.stderr,
    format="<magenta>✦ {time:HH:mm:ss}</magenta> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level="INFO",
    colorize=True,
    enqueue=True
)

# ===========================
# ЛОКАЛЬНЫЙ ДАМП ДЛЯ ОТЛАДКИ
# ===========================
logger.add(
    "data/debug.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="3 days",
    enqueue=True
)
