"""
WebSocket heartbeat mechanism for connection health monitoring.
"""
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class HeartbeatManager:
    """Manages WebSocket connection heartbeats."""
    
    def __init__(
        self,
        ping_interval: Optional[int] = None,
        ping_timeout: Optional[int] = None
    ):
        """Initialize heartbeat manager.
        
        Args:
            ping_interval: Seconds between ping messages
            ping_timeout: Seconds to wait for pong response
        """
        self.ping_interval = ping_interval or settings.ws_ping_interval
        self.ping_timeout = ping_timeout or settings.ws_ping_timeout
        
        # Track last pong time: {connection_id: datetime}
        self.last_pong: Dict[str, datetime] = {}
        
        # Track active heartbeat tasks: {connection_id: Task}
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(
            "heartbeat_manager_initialized",
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout
        )
    
    def start_heartbeat(
        self,
        connection_id: str,
        websocket,
        on_timeout_callback=None
    ) -> None:
        """Start heartbeat monitoring for a connection.
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket instance
            on_timeout_callback: Optional callback to call on timeout
        """
        # Cancel existing heartbeat if any
        self.stop_heartbeat(connection_id)
        
        # Initialize last pong time
        self.last_pong[connection_id] = datetime.now()
        
        # Create and store heartbeat task
        task = asyncio.create_task(
            self._heartbeat_loop(connection_id, websocket, on_timeout_callback)
        )
        self.heartbeat_tasks[connection_id] = task
        
        logger.debug("heartbeat_started", connection_id=connection_id)
    
    def stop_heartbeat(self, connection_id: str) -> None:
        """Stop heartbeat monitoring for a connection.
        
        Args:
            connection_id: Connection identifier
        """
        # Cancel task if exists
        if connection_id in self.heartbeat_tasks:
            task = self.heartbeat_tasks[connection_id]
            if not task.done():
                task.cancel()
            del self.heartbeat_tasks[connection_id]
        
        # Remove from tracking
        if connection_id in self.last_pong:
            del self.last_pong[connection_id]
        
        logger.debug("heartbeat_stopped", connection_id=connection_id)
    
    def record_pong(self, connection_id: str) -> None:
        """Record that a pong was received.
        
        Args:
            connection_id: Connection identifier
        """
        self.last_pong[connection_id] = datetime.now()
        logger.debug("pong_received", connection_id=connection_id)
    
    def is_alive(self, connection_id: str) -> bool:
        """Check if a connection is alive (recent pong received).
        
        Args:
            connection_id: Connection identifier
            
        Returns:
            True if connection is alive, False otherwise
        """
        if connection_id not in self.last_pong:
            return False
        
        last_time = self.last_pong[connection_id]
        elapsed = (datetime.now() - last_time).total_seconds()
        
        return elapsed < (self.ping_interval + self.ping_timeout)
    
    async def _heartbeat_loop(
        self,
        connection_id: str,
        websocket,
        on_timeout_callback=None
    ) -> None:
        """Internal heartbeat loop.
        
        Args:
            connection_id: Connection identifier
            websocket: WebSocket instance
            on_timeout_callback: Optional callback to call on timeout
        """
        try:
            while True:
                # Wait for ping interval
                await asyncio.sleep(self.ping_interval)
                
                # Check if last pong is too old
                if connection_id in self.last_pong:
                    elapsed = (datetime.now() - self.last_pong[connection_id]).total_seconds()
                    
                    if elapsed > (self.ping_interval + self.ping_timeout):
                        logger.warning(
                            "heartbeat_timeout",
                            connection_id=connection_id,
                            elapsed_seconds=elapsed
                        )
                        
                        # Call timeout callback if provided
                        if on_timeout_callback:
                            await on_timeout_callback(connection_id)
                        
                        break
                
                # Send ping
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.debug("ping_sent", connection_id=connection_id)
                
                except Exception as e:
                    logger.error(
                        "ping_send_failed",
                        connection_id=connection_id,
                        error=str(e)
                    )
                    break
        
        except asyncio.CancelledError:
            logger.debug("heartbeat_cancelled", connection_id=connection_id)
        
        except Exception as e:
            logger.error(
                "heartbeat_error",
                connection_id=connection_id,
                error=str(e)
            )
        
        finally:
            # Clean up
            if connection_id in self.heartbeat_tasks:
                del self.heartbeat_tasks[connection_id]
    
    def get_active_heartbeats(self) -> int:
        """Get number of active heartbeat monitors.
        
        Returns:
            Number of active heartbeats
        """
        return len(self.heartbeat_tasks)
    
    async def shutdown(self) -> None:
        """Shutdown all heartbeat monitors."""
        logger.info("shutting_down_heartbeats", count=len(self.heartbeat_tasks))
        
        # Cancel all tasks
        for connection_id in list(self.heartbeat_tasks.keys()):
            self.stop_heartbeat(connection_id)
        
        # Wait a bit for graceful shutdown
        await asyncio.sleep(0.1)
        
        logger.info("heartbeat_shutdown_complete")


# Global heartbeat manager instance
heartbeat_manager = HeartbeatManager()


def get_heartbeat_manager() -> HeartbeatManager:
    """Get the global heartbeat manager instance.
    
    Returns:
        HeartbeatManager instance
    """
    return heartbeat_manager
