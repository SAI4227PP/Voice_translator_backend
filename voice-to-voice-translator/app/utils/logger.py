"""
Custom logger utilities.
"""
import structlog
from typing import Any, Dict, Optional


def log_function_call(logger, func_name: str, **kwargs: Any) -> None:
    """Log a function call with parameters.
    
    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function parameters to log
    """
    logger.debug(
        "function_called",
        function=func_name,
        **kwargs
    )


def log_error_with_context(
    logger,
    error: Exception,
    context: Dict[str, Any],
    message: Optional[str] = None
) -> None:
    """Log an error with additional context.
    
    Args:
        logger: Logger instance
        error: Exception instance
        context: Additional context dictionary
        message: Optional custom message
    """
    logger.error(
        message or "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        **context,
        exc_info=True
    )


def create_component_logger(component_name: str):
    """Create a logger for a specific component.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Logger instance bound to component name
    """
    return structlog.get_logger(component_name)
