"""
EFES-2026 Production Real-Time Streaming Engine
Main entry point for production-grade command center

Architecture:
- Async ingestion pipeline (OpenSky)
- In-memory state store (authoritative)
- Diff engine (delta computation)
- Event bus (async distribution)
- WebSocket broadcaster (real-time updates)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import our production modules
from app.core.state_store import state_store
from app.core.diff_engine import diff_engine
from app.core.event_bus import event_bus
from app.ws.sitrep import websocket_endpoint, ws_manager
from app.services.aircraft_ingestor import ingestor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    - Start ingestion on startup
    - Graceful shutdown on exit
    """
    logger.info("🚀 EFES-2026 Production Engine Starting...")
    
    # Start event bus
    await event_bus.start()
    logger.info("✅ EventBus started")
    
    # Start aircraft ingestor
    await ingestor.start()
    logger.info("✅ AircraftIngestor started (2s interval)")
    
    # Start WebSocket heartbeat task
    heartbeat_task = asyncio.create_task(websocket_heartbeat())
    logger.info("✅ WebSocket heartbeat started")
    
    logger.info("🎯 Production engine ready - Port 8000")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    
    heartbeat_task.cancel()
    await ingestor.stop()
    await event_bus.stop()
    
    logger.info("👋 Shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="TULPAR Command Center - Production",
    version="2.0.0",
    lifespan=lifespan
)

# CORS for all origins (production: restrict this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:10845",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def websocket_heartbeat():
    """Send periodic heartbeats to all connected WebSocket clients"""
    while True:
        try:
            await asyncio.sleep(5)  # Every 5 seconds
            await ws_manager.broadcast_heartbeat()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")


# REST Endpoints (for HTTP fallback and health checks)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok",
        "version": "2.0.0",
        "engine": "production",
        "websocket_connections": ws_manager._stats["current_connections"],
        "aircraft_tracked": state_store.count,
        "timestamp": state_store.last_update.isoformat()
    })


@app.get("/api/aircraft")
async def get_aircraft():
    """
    Get all aircraft (HTTP fallback)
    For WebSocket clients, use /ws/sitrep for real-time updates
    """
    try:
        state = await state_store.get_snapshot()
        return JSONResponse({
            "type": "full",
            "count": len(state),
            "aircraft": list(state.values()),
            "timestamp": state_store.last_update.isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting aircraft: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.get("/api/aircraft/diff")
async def get_aircraft_diff():
    """
    Get current state diff (for testing)
    """
    try:
        current_state = await state_store.get_snapshot()
        diff = diff_engine.compute_diff(current_state)
        return JSONResponse(diff.to_dict())
    except Exception as e:
        logger.error(f"Error computing diff: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    try:
        ws_stats = ws_manager.get_stats()
        
        return JSONResponse({
            "websocket": ws_stats,
            "aircraft": {
                "tracked": state_store.count,
                "last_update": state_store.last_update.isoformat()
            },
            "event_bus": {
                "queue_size": event_bus.queue_size,
                "subscribers": event_bus.subscriber_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# WebSocket Endpoint
@app.websocket("/ws/sitrep")
async def sitrep_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time situational awareness
    - Accepts connections
    - Sends full state on connect
    - Broadcasts diffs automatically via event bus
    - Handles client ping/pong
    """
    await websocket_endpoint(websocket)


# Vessel and strategic zones endpoints (mock for now)

@app.get("/api/vessels")
async def get_vessels():
    """Get vessels (mock data for now)"""
    return JSONResponse({
        "type": "full",
        "count": 2,
        "data": [
            {
                "id": "VESSEL001",
                "name": "MV KEMAL KÖPRÜSÜ",
                "lat": 40.8,
                "lon": 29.2,
                "speed": 15.5,
                "heading": 135
            },
            {
                "id": "VESSEL002",
                "name": "TCG GELİBOLU",
                "lat": 39.5,
                "lon": 26.2,
                "speed": 22.0,
                "heading": 45
            }
        ]
    })


@app.get("/api/strategic-zones")
async def get_strategic_zones():
    """Get strategic zones"""
    return JSONResponse({
        "type": "full",
        "count": 3,
        "data": [
            {
                "id": "ZONE001",
                "name": "İstanbul Boğazı",
                "type": "maritime_chokepoint",
                "coordinates": [[41.2, 28.9], [41.3, 29.1]],
                "risk_level": "Yüksek"
            },
            {
                "id": "ZONE002",
                "name": "Çanakkale Boğazı",
                "type": "maritime_chokepoint",
                "coordinates": [[40.2, 26.4], [40.3, 26.5]],
                "risk_level": "Yüksek"
            },
            {
                "id": "ZONE003",
                "name": "Ege FIR Bölgesi",
                "type": "airspace",
                "coordinates": [[37.0, 26.0], [40.0, 28.0]],
                "risk_level": "Orta"
            }
        ]
    })


# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting EFES-2026 Production Engine")
    logger.info("📡 WebSocket: ws://localhost:8000/ws/sitrep")
    logger.info("🎯 Real-time aircraft tracking active")
    
    uvicorn.run(
        "main_production:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False  # Production mode
    )
