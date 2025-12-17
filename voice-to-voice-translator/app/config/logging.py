"""
Logging configuration for the application.
"""
import sys
import logging
from pathlib import Path
from typing import Optional
import structlog
from structlog.types import FilteringBoundLogger
from app.config.settings import get_settings


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None
) -> FilteringBoundLogger:
    """Setup structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        
    Returns:
        Configured logger instance
    """
    settings = get_settings()
    
    # Use provided values or fall back to settings
    level = log_level or settings.log_level
    file_path = log_file or settings.log_file
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if file_path:
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )
    
    # Setup file handler if log file specified
    if file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer() if settings.is_development 
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger()
    logger.info(
        "logging_configured",
        level=level,
        file=file_path,
        environment=settings.environment
    )
    
    return logger


def get_logger(name: Optional[str] = None) -> FilteringBoundLogger:
    """Get a logger instance.
    
    Args:
        name: Optional logger name
        
    Returns:
        Logger instance
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> FilteringBoundLogger:
        """Get logger instance with class context.
        
        Returns:
            Logger bound to the class name
        """
        return structlog.get_logger(self.__class__.__name__)


# Create default logger instance
logger = get_logger()
