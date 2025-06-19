from .defaults import INSTALLATION_DIR
from loguru import logger
from pathlib import Path
import sys

# Ensure logs directory exists
logs_dir = Path(INSTALLATION_DIR) / "logs"
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