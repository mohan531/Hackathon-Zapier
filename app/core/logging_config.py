import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging():
    """Configures the application-wide logging with console and rotating file handlers."""

    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate logs
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # 1. Console Handler (always enabled)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (conditional based on environment variables)
    # This block will only execute if APP_ENV is 'production' OR LOG_TO_FILE is 'true'
    if os.getenv("APP_ENV") == "production" or os.getenv("LOG_TO_FILE", "False").lower() == "true":
        log_dir = "logs"
        log_file_name = "confluence_summarizer.log"
        log_file_path = os.path.join(log_dir, log_file_name)

        # Ensure the logs directory exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        try:
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=7,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)

            logger = logging.getLogger(__name__) # Get a logger for this module
            logger.info(f"Logging to rotating file enabled: {log_file_path}")

        except Exception as e:
            root_logger.error(f"Failed to set up rotating file logging: {e}")
            # Note: This error will still go to console because console_handler is already set up.

    # Suppress verbose logging from specific libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.INFO)