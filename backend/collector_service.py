"""
EFES Savunma — Collector (Data Ingestion)
Dış ADS-B / AIS kaynaklarından çeker, normalize eder, Redis'e yazar.
Crash etmemesi için tüm dış çağrılar try/except ile korunur.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache_layer import cache_layer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EFES-2026 Collector Service", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_aircraft_from_opensky_row(row: List[Any]) -> Optional[Dict[str, Any]]:
    """OpenSky state vector — resmi sıra: 5=lon, 6=lat, 7=baro_alt, 9=velocity, 10=true_track."""
    try:
        if not row or len(row) < 11:
            return None
        icao = row[0] or ""
        cs = (row[1] or "").strip() if isinstance(row[1], str) else ""
        lon, lat = row[5], row[6]
        if lat is None or lon is None:
            return None
        alt = float(row[7]) if row[7] is not None else 0.0
        spd = float(row[9]) if row[9] is not None else 0.0
        hdg = float(row[10]) if row[10] is not None else 0.0
        risk = int(hash(icao) % 40) if icao else 0
        return {
            "id": str(icao),
            "callsign": cs or "UNKNOWN",
            "lat": float(lat),
            "lon": float(lon),
            "altitude": alt,
            "speed": spd,
            "heading": hdg,
            "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "aircraft_type": "CIV",
            "anomaly_score": risk,
            "risk_score": risk,
            "risk_level": "Düşük" if risk < 20 else "Orta",
            "anomaly_flag": risk > 30,
            "anomaly_reason": "OpenSky canlı akış",
            "flags": [],
            "route": [],
            "source": "opensky",
        }
    except Exception as e:
        logger.debug("normalize row skip: %s", e)
        return None


class DataCollector:
    """Rate-limit dostu: çağıran döngü aralığı (ör. 12s) ana fren; burada ek güvenlik."""

    def __init__(self) -> None:
        self._last_opensky_ts = 0.0
        self._min_opensky_interval = float(os.getenv("EFES_OPENSKY_MIN_INTERVAL", "10"))

    async def collect_opensky_data(self, bounds: Dict[str, float]) -> List[Dict[str, Any]]:
        now = time.time()
        if now - self._last_opensky_ts < self._min_opensky_interval:
            logger.info("OpenSky atlandı (min interval)")
            return []
        self._last_opensky_ts = now

        out: List[Dict[str, Any]] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://opensky-network.org/api/states/all",
                    params={
                        "lamin": bounds["min_lat"],
                        "lomin": bounds["min_lon"],
                        "lamax": bounds["max_lat"],
                        "lomax": bounds["max_lon"],
                    },
                    headers={
                        "User-Agent": "EFES2026-Collector/1.1 (+https://localhost)",
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    if response.status != 200:
                        logger.error("OpenSky HTTP %s", response.status)
                        return []
                    data = await response.json()
                    states = data.get("states") or []
                    for row in states:
                        n = _normalize_aircraft_from_opensky_row(row)
                        if n:
                            out.append(n)
                    logger.info("OpenSky: %s uçak (normalize)", len(out))
        except Exception as e:
            logger.error("OpenSky toplama hatası: %s", e)
            return []
        return out

    async def collect_ais_data(self, bounds: Dict[str, float]) -> List[Dict[str, Any]]:
        """AIS için ücretli API yoksa güvenli mock (MVP)."""
        try:
            _ = bounds
            return [
                {
                    "id": "AIS-DEMO-1",
                    "mmsi": "271042001",
                    "name": "MV TRAKYA",
                    "lat": 40.85,
                    "lon": 29.28,
                    "speed": 8.4,
                    "heading": 140,
                    "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "vessel_type": "Tanker",
                    "anomaly_score": 8,
                    "risk_score": 8,
                    "risk_level": "Düşük",
                    "anomaly_flag": False,
                    "anomaly_reason": "AIS mock",
                    "flags": ["AIS_MOCK"],
                    "route": [],
                    "source": "ais_mock",
                }
            ]
        except Exception as e:
            logger.error("AIS mock hatası: %s", e)
            return []

    async def publish_aircraft(self, items: List[Dict[str, Any]]) -> None:
        try:
            await cache_layer.set_data("aircraft:latest", items)
        except Exception as e:
            logger.error("Redis aircraft yazılamadı: %s", e)

    async def publish_vessels(self, items: List[Dict[str, Any]]) -> None:
        try:
            await cache_layer.set_data("vessels:latest", items)
        except Exception as e:
            logger.error("Redis vessels yazılamadı: %s", e)


data_collector = DataCollector()


@app.get("/api/collector/status")
async def collector_status() -> Dict[str, Any]:
    return {"ok": True, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/collector/run-once")
async def run_once() -> Dict[str, Any]:
    """Manuel tetik — Redis'e yazar."""
    bounds = {
        "min_lat": float(os.getenv("EFES_BOUNDS_MIN_LAT", "34")),
        "max_lat": float(os.getenv("EFES_BOUNDS_MAX_LAT", "43")),
        "min_lon": float(os.getenv("EFES_BOUNDS_MIN_LON", "25")),
        "max_lon": float(os.getenv("EFES_BOUNDS_MAX_LON", "45")),
    }
    try:
        ac = await data_collector.collect_opensky_data(bounds)
        vs = await data_collector.collect_ais_data(bounds)
        await data_collector.publish_aircraft(ac)
        await data_collector.publish_vessels(vs)
        return {"aircraft": len(ac), "vessels": len(vs), "bounds": bounds}
    except Exception as e:
        logger.exception("run-once")
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
