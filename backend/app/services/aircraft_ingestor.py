"""
AircraftIngestor - Async data ingestion from OpenSky
Parallelized, fault-tolerant, with circuit breaker pattern
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ..core.state_store import state_store
from ..core.diff_engine import diff_engine
from ..core.event_bus import event_bus

logger = logging.getLogger(__name__)


class OpenSkyClient:
    """
    Async OpenSky API client with:
    - Circuit breaker pattern
    - Timeout protection
    - Automatic failover to test data
    """
    
    def __init__(self):
        self.base_url = "https://opensky-network.org/api"
        self.timeout = aiohttp.ClientTimeout(total=10, connect=5)
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_open = False
        self.fail_count = 0
        self.max_failures = 3
        self.circuit_reset_time = 60  # seconds
        self.last_failure: Optional[datetime] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_states(self, lamin: float, lomin: float, 
                          lamax: float, lomax: float) -> List[Dict[str, Any]]:
        """
        Fetch aircraft states from OpenSky
        Returns list of aircraft or empty list on failure
        """
        # Check circuit breaker
        if self.circuit_open:
            if self._should_reset_circuit():
                self._reset_circuit()
            else:
                logger.warning("Circuit breaker open, using fallback data")
                return self._generate_fallback_data()
        
        try:
            url = f"{self.base_url}/states/all"
            params = {
                "lamin": lamin,
                "lomin": lomin,
                "lamax": lamax,
                "lomax": lomax
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    aircraft_list = self._parse_opensky_data(data)
                    self._reset_circuit()  # Success, reset failures
                    return aircraft_list
                    
                elif response.status == 429:
                    logger.warning("OpenSky rate limit hit")
                    self._record_failure()
                    return self._generate_fallback_data()
                    
                else:
                    logger.error(f"OpenSky error: {response.status}")
                    self._record_failure()
                    return self._generate_fallback_data()
                    
        except asyncio.TimeoutError:
            logger.error("OpenSky timeout")
            self._record_failure()
            return self._generate_fallback_data()
            
        except Exception as e:
            logger.error(f"OpenSky fetch error: {e}")
            self._record_failure()
            return self._generate_fallback_data()
    
    def _parse_opensky_data(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse OpenSky states response into normalized aircraft data"""
        aircraft_list = []
        
        states = data.get("states", [])
        if not states:
            return []
        
        for state in states:
            # OpenSky format: [icao24, callsign, origin_country, time_position, 
            # last_contact, lat, lon, baro_altitude, on_ground, velocity, 
            # true_track, vertical_rate, sensors, geo_altitude, squawk, spi, 
            # position_source]
            
            if not state[5] or not state[6]:  # Skip if no position
                continue
            
            aircraft = {
                "id": state[0] if state[0] else f"UNK{len(aircraft_list)}",
                "callsign": (state[1] or "UNKNOWN").strip(),
                "lat": float(state[6]),
                "lon": float(state[5]),
                "altitude": float(state[7] or 0),
                "speed": float(state[9] or 0),
                "heading": float(state[10] or 0),
                "source": "opensky",
                "anomaly_score": 0.0,
                "status": "active"
            }
            aircraft_list.append(aircraft)
        
        return aircraft_list
    
    def _generate_fallback_data(self) -> List[Dict[str, Any]]:
        """Generate realistic test data when API fails"""
        import random
        
        # Turkish airports coordinates
        airports = [
            (41.015, 28.979, "IST"),  # Istanbul
            (39.927, 32.683, "ESB"),  # Ankara
            (36.898, 30.800, "AYT"),  # Antalya
            (38.292, 27.155, "ADB"),  # Izmir
            (40.898, 29.309, "SAW"),  # Sabiha
        ]
        
        airlines = ["THY", "PGS", "SXS", "AJT", "DHK"]
        aircraft_list = []
        
        for i in range(25):  # Generate 25 aircraft
            base_lat, base_lon, airport = random.choice(airports)
            
            # Random offset from airport
            lat = base_lat + random.uniform(-0.5, 0.5)
            lon = base_lon + random.uniform(-0.5, 0.5)
            
            aircraft = {
                "id": f"FALLBACK{i:03d}",
                "callsign": f"{random.choice(airlines)}{random.randint(100, 9999)}",
                "lat": lat,
                "lon": lon,
                "altitude": random.choice([5000, 15000, 25000, 35000, 41000]),
                "speed": random.randint(300, 550),
                "heading": random.randint(0, 359),
                "source": "fallback",
                "anomaly_score": 0.0,
                "status": "active"
            }
            aircraft_list.append(aircraft)
        
        logger.info(f"Generated {len(aircraft_list)} fallback aircraft")
        return aircraft_list
    
    def _record_failure(self):
        """Record API failure for circuit breaker"""
        self.fail_count += 1
        self.last_failure = datetime.now()
        
        if self.fail_count >= self.max_failures:
            self.circuit_open = True
            logger.error(f"Circuit breaker opened after {self.fail_count} failures")
    
    def _should_reset_circuit(self) -> bool:
        """Check if circuit breaker should reset"""
        if not self.last_failure:
            return True
        elapsed = (datetime.now() - self.last_failure).total_seconds()
        return elapsed > self.circuit_reset_time
    
    def _reset_circuit(self):
        """Reset circuit breaker"""
        self.circuit_open = False
        self.fail_count = 0
        logger.info("Circuit breaker reset")


class AircraftIngestor:
    """
    Main ingestion orchestrator
    - Periodic state updates
    - Async pipeline
    - Diff computation and event publishing
    """
    
    def __init__(self, update_interval: float = 2.0):
        self.update_interval = update_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.opensky = OpenSkyClient()
        
        # Turkey region bounds
        self.bounds = {
            "lamin": 35.0,
            "lomin": 25.0,
            "lamax": 42.0,
            "lomax": 45.0
        }
    
    async def start(self):
        """Start ingestion loop"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._ingestion_loop())
        logger.info(f"AircraftIngestor started (interval: {self.update_interval}s)")
    
    async def stop(self):
        """Stop ingestion loop"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AircraftIngestor stopped")
    
    async def _ingestion_loop(self):
        """Main ingestion loop"""
        async with self.opensky:
            while self._running:
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    # Fetch aircraft data
                    aircraft_list = await self._fetch_and_update()
                    
                    # Compute and broadcast diff
                    await self._compute_and_broadcast_diff()
                    
                    # Calculate sleep time to maintain interval
                    elapsed = asyncio.get_event_loop().time() - start_time
                    sleep_time = max(0, self.update_interval - elapsed)
                    
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                        
                except Exception as e:
                    logger.error(f"Ingestion loop error: {e}")
                    await asyncio.sleep(self.update_interval)
    
    async def _fetch_and_update(self) -> List[Dict[str, Any]]:
        """Fetch aircraft and update state store"""
        try:
            # Fetch from OpenSky
            aircraft_list = await self.opensky.fetch_states(
                **self.bounds
            )
            
            # Update state store
            if aircraft_list:
                await state_store.update_batch(aircraft_list)
                logger.debug(f"Updated {len(aircraft_list)} aircraft in state store")
            
            return aircraft_list
            
        except Exception as e:
            logger.error(f"Fetch and update error: {e}")
            return []
    
    async def _compute_and_broadcast_diff(self):
        """Compute state diff and publish to event bus"""
        try:
            # Get current state snapshot
            current_state = await state_store.get_snapshot()
            
            # Compute diff
            diff = diff_engine.compute_diff(current_state)
            
            # Publish if not empty
            if not diff.is_empty():
                await event_bus.publish_state_diff(diff.to_dict())
                logger.debug(f"Published diff: {diff.size()} changes")
            
        except Exception as e:
            logger.error(f"Diff computation error: {e}")
    
    async def force_update(self):
        """Force immediate update (for testing)"""
        await self._fetch_and_update()
        await self._compute_and_broadcast_diff()


# Global singleton
ingestor = AircraftIngestor(update_interval=2.0)
