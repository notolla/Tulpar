"""
OpenSky Network — tek kaynaklı ADS-B çekimi (collector ve gateway paylaşır).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


def default_bounds() -> Dict[str, float]:
    """
    Genişletilmiş izleme bölgesi:
    - Kuzey: Ukrayna / Karadeniz kuzeyi (55°N)
    - Güney: Hürmüz Boğazı / Kızıldeniz (20°N)
    - Batı: Balkanlar / İtalya (10°E)
    - Doğu: İran / Körfez (70°E)
    Kapsam: Türkiye, Yunanistan, Balkanlar, Ukrayna-Rusya,
            Suriye, Irak, İran, İsrail, Körfez, Hürmüz, Süveyş
    """
    return {
        "min_lat": float(os.getenv("EFES_BOUNDS_MIN_LAT", "20")),
        "max_lat": float(os.getenv("EFES_BOUNDS_MAX_LAT", "55")),
        "min_lon": float(os.getenv("EFES_BOUNDS_MIN_LON", "10")),
        "max_lon": float(os.getenv("EFES_BOUNDS_MAX_LON", "70")),
    }


def _normalize_row(row: List[Any]) -> Optional[Dict[str, Any]]:
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
        risk = int(hash(str(icao)) % 40) if icao else 0
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
            "anomaly_reason": "OpenSky",
            "flags": [],
            "route": [],
            "source": "opensky",
        }
    except Exception as e:
        logger.debug("opensky row skip: %s", e)
        return None


OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", "notolla-api-client")
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "GHIkva2lDrdGUuNGplugyxqCZCsCCI0V")


async def fetch_opensky_aircraft(
    bounds: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    b = bounds or default_bounds()
    out: List[Dict[str, Any]] = []
    try:
        auth = aiohttp.BasicAuth(
            login=OPENSKY_CLIENT_ID, password=OPENSKY_CLIENT_SECRET
        ) if OPENSKY_CLIENT_ID else None

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://opensky-network.org/api/states/all",
                params={
                    "lamin": b["min_lat"],
                    "lomin": b["min_lon"],
                    "lamax": b["max_lat"],
                    "lomax": b["max_lon"],
                },
                headers={
                    "User-Agent": "TULPAR-EFES/2.0",
                    "Accept": "application/json",
                },
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as response:
                if response.status == 429:
                    logger.warning("OpenSky rate limit (429)")
                    return []
                if response.status == 401:
                    logger.warning("OpenSky kimlik doğrulama hatası (401)")
                    return []
                if response.status != 200:
                    logger.warning("OpenSky HTTP %s", response.status)
                    return []
                data = await response.json()
                for row in data.get("states") or []:
                    n = _normalize_row(row)
                    if n:
                        out.append(n)
                logger.info("OpenSky: %s gerçek uçak alındı", len(out))
    except Exception as e:
        logger.warning("OpenSky istek hatası: %s", e)
        return []
    return out
