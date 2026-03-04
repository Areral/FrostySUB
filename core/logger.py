import sys
from loguru import logger

def setup_logger():
    logger.remove()
    
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    logger.add(
        "data/debug.log", 
        rotation="50 MB", 
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function}:{line} | {message}",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )

setup_logger()
