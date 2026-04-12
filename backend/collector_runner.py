"""
EFES Savunma — arka plan collector döngüsü (ayrı süreç).
Örnek:  python collector_runner.py

ADS-B dış API'yi sadece bu süreç çağırır; gateway doğrudan çağırmaz.
"""

from __future__ import annotations

import asyncio
import logging
import os

from cache_layer import cache_layer
from collector_service import data_collector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collector_runner")

INTERVAL = float(os.getenv("EFES_COLLECTOR_INTERVAL", "12"))


async def loop() -> None:
    await cache_layer.init_redis()
    bounds = {
        "min_lat": float(os.getenv("EFES_BOUNDS_MIN_LAT", "34")),
        "max_lat": float(os.getenv("EFES_BOUNDS_MAX_LAT", "43")),
        "min_lon": float(os.getenv("EFES_BOUNDS_MIN_LON", "25")),
        "max_lon": float(os.getenv("EFES_BOUNDS_MAX_LON", "45")),
    }
    logger.info("Collector döngüsü başladı interval=%ss bounds=%s", INTERVAL, bounds)
    while True:
        try:
            ac = await data_collector.collect_opensky_data(bounds)
            if ac:
                await data_collector.publish_aircraft(ac)
            vs = await data_collector.collect_ais_data(bounds)
            if vs:
                await data_collector.publish_vessels(vs)
        except Exception as e:
            logger.exception("Collector tick hatası: %s", e)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(loop())
