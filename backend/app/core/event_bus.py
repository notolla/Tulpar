"""
EventBus - Async event distribution system
Routes state changes to WebSocket broadcaster
"""

import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Async event bus for state change distribution
    - Decouples ingestor from WebSocket layer
    - Supports multiple subscribers
    - Queue-based for backpressure handling
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start event processing loop"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("EventBus started")
    
    async def stop(self):
        """Stop event processing"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")
    
    async def _process_loop(self):
        """Main processing loop"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")
    
    async def _dispatch(self, event: Dict[str, Any]):
        """Dispatch event to all subscribers"""
        for subscriber in self._subscribers:
            try:
                # Handle both sync and async subscribers
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
    
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to events"""
        self._subscribers.append(callback)
        logger.info(f"New subscriber added (total: {len(self._subscribers)})")
    
    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Unsubscribe from events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.info(f"Subscriber removed (total: {len(self._subscribers)})")
    
    async def publish(self, event_type: str, payload: Dict[str, Any]):
        """
        Publish event to bus
        Non-blocking with backpressure handling
        """
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload
        }
        
        try:
            # Non-blocking put with timeout
            await asyncio.wait_for(
                self._queue.put(event),
                timeout=0.1
            )
        except asyncio.TimeoutError:
            # Queue full, drop event (backpressure)
            logger.warning(f"EventBus queue full, dropping {event_type} event")
    
    async def publish_state_diff(self, diff: Dict[str, Any]):
        """Publish state diff event"""
        await self.publish("state_diff", diff)
    
    async def publish_full_state(self, state: Dict[str, Any]):
        """Publish full state reset event"""
        await self.publish("full_state", state)
    
    async def publish_heartbeat(self):
        """Publish heartbeat event"""
        await self.publish("heartbeat", {"status": "live"})
    
    @property
    def queue_size(self) -> int:
        """Current queue size"""
        return self._queue.qsize()
    
    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers"""
        return len(self._subscribers)


# Global singleton
event_bus = EventBus()
