from .defaults import DEFAULT_STORAGE_PATH
from loguru import logger
import sys

# Ensure logs directory exists
logs_dir = DEFAULT_STORAGE_PATH / "logs"
logs_dir.mkdir(exist_ok=True, parents=True)

# Configure logger
logger.remove()

# Console output (INFO and above)
logger.add(sys.stderr, level="INFO")

# File output (DEBUG and above, rotated daily, kept for 5 days)
logger.add(
    logs_dir / "codetide_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="00:00",
    retention="5 days",
    enqueue=True,
    backtrace=True,
    diagnose=True,
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
)