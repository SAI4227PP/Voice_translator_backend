"""
Rate limiting and throttling.
"""
import time
from typing import Dict, Optional
from collections import defaultdict, deque
from app.config import get_logger, get_settings
from app.utils.exceptions import RateLimitError

logger = get_logger(__name__)
settings = get_settings()


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(
        self,
        max_requests: int = 100,
        time_window_seconds: int = 60
    ):
        """Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per time window
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        
        # Store request timestamps per identifier
        self._requests: Dict[str, deque] = defaultdict(lambda: deque())
        
        logger.info(
            "rate_limiter_initialized",
            max_requests=max_requests,
            window_seconds=time_window_seconds
        )
    
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (user ID, IP, etc.)
            
        Returns:
            True if within limit
            
        Raises:
            RateLimitError: If rate limit exceeded
        """
        current_time = time.time()
        requests = self._requests[identifier]
        
        # Remove old requests outside time window
        cutoff_time = current_time - self.time_window
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        # Check if limit exceeded
        if len(requests) >= self.max_requests:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                requests=len(requests)
            )
            raise RateLimitError(
                f"Rate limit exceeded: {len(requests)}/{self.max_requests} requests"
            )
        
        # Add current request
        requests.append(current_time)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Number of remaining requests
        """
        current_time = time.time()
        requests = self._requests[identifier]
        
        # Remove old requests
        cutoff_time = current_time - self.time_window
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        return max(0, self.max_requests - len(requests))
    
    def reset_limit(self, identifier: str) -> None:
        """Reset rate limit for identifier.
        
        Args:
            identifier: Unique identifier
        """
        if identifier in self._requests:
            del self._requests[identifier]
            logger.info("rate_limit_reset", identifier=identifier)


class ConnectionRateLimiter:
    """Rate limiter for WebSocket connections."""
    
    def __init__(
        self,
        max_connections_per_ip: int = 10,
        max_messages_per_second: int = 10
    ):
        """Initialize connection rate limiter.
        
        Args:
            max_connections_per_ip: Max concurrent connections per IP
            max_messages_per_second: Max messages per second per connection
        """
        self.max_connections_per_ip = max_connections_per_ip
        self.max_messages_per_second = max_messages_per_second
        
        # Track connections per IP
        self._connections_per_ip: Dict[str, int] = defaultdict(int)
        
        # Message rate limiters per connection
        self._message_limiters: Dict[str, RateLimiter] = {}
        
        logger.info(
            "connection_rate_limiter_initialized",
            max_conn_per_ip=max_connections_per_ip,
            max_msg_per_sec=max_messages_per_second
        )
    
    def check_connection_limit(self, ip_address: str) -> bool:
        """Check if new connection is allowed.
        
        Args:
            ip_address: Client IP address
            
        Returns:
            True if allowed
            
        Raises:
            RateLimitError: If limit exceeded
        """
        current_connections = self._connections_per_ip[ip_address]
        
        if current_connections >= self.max_connections_per_ip:
            logger.warning(
                "connection_limit_exceeded",
                ip=ip_address,
                connections=current_connections
            )
            raise RateLimitError(
                f"Connection limit exceeded: {current_connections}/{self.max_connections_per_ip}"
            )
        
        return True
    
    def register_connection(self, connection_id: str, ip_address: str) -> None:
        """Register new connection.
        
        Args:
            connection_id: Connection ID
            ip_address: Client IP
        """
        self._connections_per_ip[ip_address] += 1
        
        # Create message rate limiter for this connection
        self._message_limiters[connection_id] = RateLimiter(
            max_requests=self.max_messages_per_second,
            time_window_seconds=1
        )
        
        logger.info(
            "connection_registered",
            connection_id=connection_id,
            ip=ip_address,
            total_from_ip=self._connections_per_ip[ip_address]
        )
    
    def unregister_connection(self, connection_id: str, ip_address: str) -> None:
        """Unregister connection.
        
        Args:
            connection_id: Connection ID
            ip_address: Client IP
        """
        self._connections_per_ip[ip_address] = max(
            0,
            self._connections_per_ip[ip_address] - 1
        )
        
        # Remove message rate limiter
        if connection_id in self._message_limiters:
            del self._message_limiters[connection_id]
        
        logger.info(
            "connection_unregistered",
            connection_id=connection_id,
            ip=ip_address
        )
    
    def check_message_rate(self, connection_id: str) -> bool:
        """Check message rate for connection.
        
        Args:
            connection_id: Connection ID
            
        Returns:
            True if within limit
            
        Raises:
            RateLimitError: If rate exceeded
        """
        if connection_id not in self._message_limiters:
            logger.warning("message_rate_check_unknown_connection", id=connection_id)
            return True
        
        limiter = self._message_limiters[connection_id]
        return limiter.check_rate_limit(connection_id)


# Global rate limiter instances
_rate_limiter: Optional[RateLimiter] = None
_connection_limiter: Optional[ConnectionRateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter.
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            max_requests=settings.max_requests_per_minute,
            time_window_seconds=60
        )
    return _rate_limiter


def get_connection_limiter() -> ConnectionRateLimiter:
    """Get global connection limiter.
    
    Returns:
        ConnectionRateLimiter instance
    """
    global _connection_limiter
    if _connection_limiter is None:
        _connection_limiter = ConnectionRateLimiter(
            max_connections_per_ip=settings.max_connections_per_ip,
            max_messages_per_second=settings.max_messages_per_second
        )
    return _connection_limiter
