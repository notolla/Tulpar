"""
StateStore - In-memory authoritative aircraft state management
Single source of truth for all aircraft data
"""

import asyncio
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AircraftState:
    """Normalized aircraft state representation"""
    id: str
    callsign: str
    lat: float
    lon: float
    heading: float
    speed: float
    altitude: float
    anomaly_score: float = 0.0
    status: str = "active"
    last_update: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "callsign": self.callsign,
            "lat": self.lat,
            "lon": self.lon,
            "heading": self.heading,
            "speed": self.speed,
            "altitude": self.altitude,
            "anomaly_score": self.anomaly_score,
            "status": self.status,
            "last_update": self.last_update.isoformat(),
            "source": self.source
        }


class StateStore:
    """
    Thread-safe in-memory aircraft state store
    - Authoritative source of truth
    - Async safe operations
    - State versioning for diff tracking
    """
    
    def __init__(self):
        self._store: Dict[str, AircraftState] = {}
        self._lock = asyncio.Lock()
        self._version = 0
        self._last_update = datetime.now()
        
    async def update_aircraft(self, aircraft_data: Dict[str, Any]) -> AircraftState:
        """Update or insert aircraft state"""
        async with self._lock:
            aircraft_id = aircraft_data.get("id")
            if not aircraft_id:
                raise ValueError("Aircraft ID required")
            
            # Normalize incoming data
            state = AircraftState(
                id=aircraft_id,
                callsign=aircraft_data.get("callsign", "UNKNOWN"),
                lat=float(aircraft_data.get("lat", 0)),
                lon=float(aircraft_data.get("lon", 0)),
                heading=float(aircraft_data.get("heading", 0)),
                speed=float(aircraft_data.get("speed", 0)),
                altitude=float(aircraft_data.get("altitude", 0)),
                anomaly_score=float(aircraft_data.get("anomaly_score", 0)),
                status=aircraft_data.get("status", "active"),
                source=aircraft_data.get("source", "opensky"),
                last_update=datetime.now()
            )
            
            self._store[aircraft_id] = state
            self._version += 1
            self._last_update = datetime.now()
            
            return state
    
    async def update_batch(self, aircraft_list: List[Dict[str, Any]]) -> List[AircraftState]:
        """Batch update aircraft states"""
        async with self._lock:
            updated = []
            for aircraft_data in aircraft_list:
                try:
                    state = await self._update_single(aircraft_data)
                    updated.append(state)
                except Exception as e:
                    logger.error(f"Failed to update aircraft {aircraft_data.get('id')}: {e}")
            
            self._version += 1
            self._last_update = datetime.now()
            return updated
    
    async def _update_single(self, aircraft_data: Dict[str, Any]) -> AircraftState:
        """Internal single update without lock"""
        aircraft_id = aircraft_data.get("id")
        state = AircraftState(
            id=aircraft_id,
            callsign=aircraft_data.get("callsign", "UNKNOWN"),
            lat=float(aircraft_data.get("lat", 0)),
            lon=float(aircraft_data.get("lon", 0)),
            heading=float(aircraft_data.get("heading", 0)),
            speed=float(aircraft_data.get("speed", 0)),
            altitude=float(aircraft_data.get("altitude", 0)),
            anomaly_score=float(aircraft_data.get("anomaly_score", 0)),
            status=aircraft_data.get("status", "active"),
            source=aircraft_data.get("source", "opensky"),
            last_update=datetime.now()
        )
        self._store[aircraft_id] = state
        return state
    
    async def remove_aircraft(self, aircraft_id: str) -> Optional[AircraftState]:
        """Remove aircraft from store"""
        async with self._lock:
            if aircraft_id in self._store:
                removed = self._store.pop(aircraft_id)
                self._version += 1
                return removed
            return None
    
    async def get_aircraft(self, aircraft_id: str) -> Optional[AircraftState]:
        """Get single aircraft state"""
        async with self._lock:
            return self._store.get(aircraft_id)
    
    async def get_all(self) -> Dict[str, AircraftState]:
        """Get all aircraft states"""
        async with self._lock:
            return self._store.copy()
    
    async def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get serializable snapshot of all aircraft"""
        async with self._lock:
            return {k: v.to_dict() for k, v in self._store.items()}
    
    async def cleanup_stale(self, max_age_seconds: int = 300) -> List[str]:
        """Remove aircraft not updated within max_age_seconds"""
        async with self._lock:
            now = datetime.now()
            removed = []
            
            for aircraft_id, state in list(self._store.items()):
                age = (now - state.last_update).total_seconds()
                if age > max_age_seconds:
                    del self._store[aircraft_id]
                    removed.append(aircraft_id)
            
            if removed:
                self._version += 1
                logger.info(f"Cleaned up {len(removed)} stale aircraft")
            
            return removed
    
    @property
    def version(self) -> int:
        """Current state version for diff tracking"""
        return self._version
    
    @property
    def count(self) -> int:
        """Number of tracked aircraft"""
        return len(self._store)
    
    @property
    def last_update(self) -> datetime:
        """Timestamp of last state update"""
        return self._last_update


# Global singleton instance
state_store = StateStore()
