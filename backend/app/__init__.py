from app.config import settings
from app.logging_config import setup_logging

setup_logging(settings.LOG_LEVEL)
