"""
WebSocket SITREP (Situation Report) Handler
Production-grade real-time aircraft position streaming
"""

import asyncio
from typing import Dict, Set, Optional
from datetime import datetime
import logging

from fastapi import WebSocket, WebSocketDisconnect

from ..core.state_store import state_store
from ..core.diff_engine import diff_engine, StateDiff
from ..core.event_bus import event_bus

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts state updates
    - Connection registry per client
    - Async safe broadcasting
    - Automatic cleanup on disconnect
    - Support for full state and diff updates
    """
    
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._stats = {
            "total_connections": 0,
            "current_connections": 0,
            "messages_sent": 0,
            "start_time": datetime.now()
        }
    
    async def connect(self, websocket: WebSocket):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            self._connections.add(websocket)
            self._stats["total_connections"] += 1
            self._stats["current_connections"] = len(self._connections)
        
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info(f"🔌 WebSocket connected: {client_info} (total: {len(self._connections)})")
        
        # Send initial full state
        await self._send_full_state(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
                self._stats["current_connections"] = len(self._connections)
        
        logger.info(f"🔌 WebSocket disconnected (total: {len(self._connections)})")
    
    async def _send_full_state(self, websocket: WebSocket):
        """Send complete state to single client (for reconnect/init)"""
        try:
            state = await state_store.get_snapshot()
            message = diff_engine.get_full_state(state)
            
            await websocket.send_json(message)
            self._stats["messages_sent"] += 1
            
        except Exception as e:
            logger.error(f"Failed to send full state: {e}")
    
    async def broadcast_diff(self, diff: StateDiff):
        """Broadcast state diff to all connected clients"""
        if diff.is_empty():
            return
        
        message = diff.to_dict()
        await self._broadcast(message)
    
    async def broadcast_heartbeat(self):
        """Broadcast heartbeat to all clients"""
        message = diff_engine.get_heartbeat()
        await self._broadcast(message)
    
    async def _broadcast(self, message: Dict):
        """Internal broadcast with error handling"""
        if not self._connections:
            return
        
        # Create list of send tasks
        tasks = []
        disconnected = []
        
        for websocket in self._connections:
            try:
                task = websocket.send_json(message)
                tasks.append((websocket, task))
            except Exception as e:
                logger.error(f"Prepare broadcast error: {e}")
                disconnected.append(websocket)
        
        # Execute all sends
        for websocket, task in tasks:
            try:
                await task
                self._stats["messages_sent"] += 1
            except Exception as e:
                logger.error(f"Send error: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections.discard(ws)
                self._stats["current_connections"] = len(self._connections)
    
    async def handle_client(self, websocket: WebSocket):
        """Main client handler - manages connection lifecycle"""
        await self.connect(websocket)
        
        try:
            # Keep connection alive and handle client messages
            while True:
                try:
                    # Wait for client message (with timeout)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    
                    # Handle client requests (if any)
                    await self._handle_client_message(websocket, data)
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    await websocket.send_json(diff_engine.get_heartbeat())
                    
        except WebSocketDisconnect:
            logger.info("Client disconnected normally")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.disconnect(websocket)
    
    async def _handle_client_message(self, websocket: WebSocket, data: str):
        """Handle incoming client messages"""
        try:
            import json
            message = json.loads(data)
            msg_type = message.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif msg_type == "request_full_state":
                await self._send_full_state(websocket)
            
            else:
                logger.debug(f"Unknown client message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from client: {data}")
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    def get_stats(self) -> Dict:
        """Get WebSocket statistics"""
        uptime = datetime.now() - self._stats["start_time"]
        return {
            **self._stats,
            "uptime_seconds": uptime.total_seconds(),
            "messages_per_second": self._stats["messages_sent"] / max(uptime.total_seconds(), 1)
        }


# Global singleton
ws_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """FastAPI WebSocket endpoint handler"""
    await ws_manager.handle_client(websocket)


# Event bus integration
async def on_state_change(event: Dict):
    """Handle state change events from event bus"""
    event_type = event.get("type")
    payload = event.get("payload", {})
    
    if event_type == "state_diff":
        # Convert dict back to StateDiff
        diff = StateDiff(
            added=payload.get("added", []),
            updated=payload.get("updated", []),
            removed=payload.get("removed", []),
            timestamp=payload.get("timestamp", datetime.now().isoformat())
        )
        await ws_manager.broadcast_diff(diff)
    
    elif event_type == "full_state":
        # Send full state to all clients (e.g., after reconnect)
        pass  # Handled per-client on connect

# Subscribe to events
event_bus.subscribe(on_state_change)
