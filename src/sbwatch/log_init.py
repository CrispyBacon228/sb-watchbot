from loguru import logger
import sys

def setup_logging():
    # Reset handlers and log to stdout at INFO level
    logger.remove()
    logger.add(sys.stdout, level="INFO", enqueue=True, backtrace=False, diagnose=False)
