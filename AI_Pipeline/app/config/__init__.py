"""Config module initialization."""
import logging

from app.config.settings import settings, get_settings, reload_settings


def setup_logging(log_level=None, log_file=None):
    level_name = (log_level or settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger().addHandler(fh)
    return logging.getLogger("app")


def get_logger(name=None):
    return logging.getLogger(name or "app")


class LoggerMixin:
    @property
    def logger(self):
        return get_logger(self.__class__.__name__)


logger = get_logger("app")

__all__ = [
    "settings",
    "get_settings",
    "reload_settings",
    "setup_logging",
    "get_logger",
    "logger",
    "LoggerMixin",
]
