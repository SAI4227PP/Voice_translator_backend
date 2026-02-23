"""
Timing utilities for performance tracking.
"""
import time
from typing import Optional, Dict, List
from contextlib import contextmanager
from collections import defaultdict
import statistics
from app.config import get_logger

logger = get_logger(__name__)


class Timer:
    """Simple timer for measuring execution time."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize timer.
        
        Args:
            name: Optional timer name for logging
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time.
        
        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            raise RuntimeError("Timer not started")
        
        self.end_time = time.perf_counter()
        return self.elapsed
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds.
        
        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            return 0.0
        
        end = self.end_time if self.end_time is not None else time.perf_counter()
        return end - self.start_time
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds.
        
        Returns:
            Elapsed time in milliseconds
        """
        return self.elapsed * 1000
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, *args):
        """Context manager exit."""
        elapsed = self.stop()
        if self.name:
            logger.debug(f"{self.name}_duration_ms", duration=self.elapsed_ms)


@contextmanager
def time_block(name: str, log_result: bool = True):
    """Context manager for timing a code block.
    
    Args:
        name: Block name for logging
        log_result: Whether to log the result
        
    Yields:
        Timer instance
    """
    timer = Timer(name)
    timer.start()
    
    try:
        yield timer
    finally:
        elapsed = timer.stop()
        if log_result:
            logger.debug(
                "time_block_completed",
                name=name,
                duration_ms=timer.elapsed_ms
            )


class PerformanceTracker:
    """Track performance metrics over time."""
    
    def __init__(self):
        """Initialize performance tracker."""
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.max_samples = 1000
    
    def record(self, metric_name: str, value: float) -> None:
        """Record a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
        """
        self.metrics[metric_name].append(value)
        
        # Keep only recent samples
        if len(self.metrics[metric_name]) > self.max_samples:
            self.metrics[metric_name] = self.metrics[metric_name][-self.max_samples:]
    
    @contextmanager
    def measure(self, metric_name: str):
        """Context manager for measuring and recording execution time.
        
        Args:
            metric_name: Name of the metric
            
        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.record(metric_name, elapsed_ms)
    
    def get_stats(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get statistics for a metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Dictionary of statistics or None if no data
        """
        values = self.metrics.get(metric_name)
        if not values:
            return None
        
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value.
        
        Args:
            values: List of values
            percentile: Percentile (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics.
        
        Returns:
            Dictionary of all metric statistics
        """
        return {
            name: self.get_stats(name)
            for name in self.metrics.keys()
            if self.get_stats(name) is not None
        }
    
    def clear(self, metric_name: Optional[str] = None) -> None:
        """Clear metrics.
        
        Args:
            metric_name: Optional specific metric to clear, or None for all
        """
        if metric_name:
            if metric_name in self.metrics:
                del self.metrics[metric_name]
        else:
            self.metrics.clear()


# Global performance tracker instance
performance_tracker = PerformanceTracker()


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance.
    
    Returns:
        PerformanceTracker instance
    """
    return performance_tracker
