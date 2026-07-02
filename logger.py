import logging
import os
from logging.handlers import RotatingFileHandler

# ==========================================
# ЛОГИРОВАНИЕ
# ==========================================
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'bot.log')

# Create logger
logger = logging.getLogger('heal_raid_bot')
logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter

# Avoid adding handlers multiple times
if not logger.handlers:
    # File handler with rotation (5 MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Export the logger
__all__ = ['logger']