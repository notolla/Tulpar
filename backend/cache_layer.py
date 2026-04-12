"""
EFES Savunma — Redis cache (async). TTL: uçak/gemi 30–60 sn aralığında yapılandırılabilir.
Redis yoksa bellek içi fallback (geliştirme / dayanıklılık).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# TTL saniye — env ile override
TTL_AIRCRAFT = int(os.getenv("EFES_CACHE_TTL_AIRCRAFT", "120"))   # OpenSky 62s'de günceller
TTL_VESSELS = int(os.getenv("EFES_CACHE_TTL_VESSELS", "120"))
TTL_STRATEGIC_ZONES = int(os.getenv("EFES_CACHE_TTL_ZONES", "3600"))


def _ttl_for_key(key: str) -> int:
    base = key.split(":")[0]
    if base == "aircraft":
        return TTL_AIRCRAFT
    if base == "vessels":
        return TTL_VESSELS
    if base == "strategic_zones":
        return TTL_STRATEGIC_ZONES
    return int(os.getenv("EFES_CACHE_TTL_DEFAULT", "60"))


class _MemoryFallback:
    """Redis kapalıyken kısa TTL bellek deposu."""

    def __init__(self) -> None:
        self._store: Dict[str, tuple[float, Any]] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = (time.time() + ttl, value)

    def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if not item:
            return None
        exp, val = item
        if time.time() > exp:
            del self._store[key]
            return None
        return val

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class CacheLayer:
    def __init__(self) -> None:
        self._redis = None
        self._memory = _MemoryFallback()
        self._use_redis = False

    async def init_redis(self) -> bool:
        try:
            import redis.asyncio as redis  # type: ignore

            host = os.getenv("EFES_REDIS_HOST", "localhost")
            port = int(os.getenv("EFES_REDIS_PORT", "6379"))
            db = int(os.getenv("EFES_REDIS_DB", "0"))
            self._redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            await asyncio.wait_for(self._redis.ping(), timeout=3.0)
            self._use_redis = True
            logger.info("Redis cache bağlandı (%s:%s db=%s)", host, port, db)
            return True
        except Exception as e:
            logger.warning("Redis yok — bellek fallback: %s", e)
            self._redis = None
            self._use_redis = False
            return False

    async def close(self) -> None:
        if self._redis and self._use_redis:
            try:
                await self._redis.close()
            except Exception as e:
                logger.debug("Redis close: %s", e)

    async def set_data(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl if ttl is not None else _ttl_for_key(key)
        serialized = json.dumps(data, default=str)
        rkey = f"efes2026:{key}"
        try:
            if self._use_redis and self._redis:
                await self._redis.setex(rkey, ttl, serialized)
            else:
                self._memory.setex(rkey, ttl, serialized)
            return True
        except Exception as e:
            logger.error("Cache yazma hatası %s: %s", key, e)
            return False

    async def get_data(self, key: str) -> Optional[Any]:
        rkey = f"efes2026:{key}"
        try:
            if self._use_redis and self._redis:
                raw = await self._redis.get(rkey)
            else:
                raw = self._memory.get(rkey)
            if not raw:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.error("Cache okuma hatası %s: %s", key, e)
            return None

    async def delete_data(self, key: str) -> bool:
        rkey = f"efes2026:{key}"
        try:
            if self._use_redis and self._redis:
                await self._redis.delete(rkey)
            else:
                self._memory.delete(rkey)
            return True
        except Exception as e:
            logger.error("Cache silme hatası: %s", e)
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        if self._use_redis and self._redis:
            try:
                info = await self._redis.info()
                return {
                    "redis_connected": True,
                    "used_memory": info.get("used_memory_human", "N/A"),
                    "connected_clients": info.get("connected_clients", "N/A"),
                }
            except Exception as e:
                return {"redis_connected": False, "error": str(e)}
        return {"redis_connected": False, "backend": "memory_fallback"}


cache_layer = CacheLayer()
