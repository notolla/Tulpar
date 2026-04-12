"""
TULPAR — AIS Gemi Verisi Toplayıcı (aisstream.io WebSocket)
Gerçek zamanlı AIS akışı → bellek cache → /api/vessels endpoint

Kapsam: Akdeniz, Karadeniz, Körfez, Hürmüz, Kızıldeniz, Ege
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AIS_API_KEY = os.getenv("AIS_API_KEY", "232c2b8b24c4bd936bed3f8db2f5b106aa5c00e2")
AIS_WS_URL  = "wss://stream.aisstream.io/v0/stream"

# İzleme bölgeleri — [min_lat, min_lon, max_lat, max_lon]
AIS_BOUNDING_BOXES = [
    # Ege + Türkiye kıyıları
    [34.0, 22.0, 43.0, 36.0],
    # Karadeniz
    [40.5, 27.5, 47.5, 42.0],
    # Doğu Akdeniz + Süveyş
    [28.0, 29.0, 37.0, 43.0],
    # Körfez + Hürmüz
    [22.0, 48.0, 31.0, 60.0],
    # Kızıldeniz + Aden
    [10.0, 38.0, 30.0, 50.0],
]

# Gemi tipi kodu → Türkçe ad
SHIP_TYPE_MAP = {
    0:  "Bilinmiyor", 1: "Yük Gemisi", 2: "Yük Gemisi", 3: "Yük Gemisi",
    20: "Kanat Gemisi", 21: "Yüksek Hızlı", 22: "Yüksek Hızlı",
    30: "Balıkçı", 31: "Çekici", 32: "Çekici", 33: "İşaret Aracı",
    34: "Dalış", 35: "Askeri", 36: "Yelkenli", 37: "Zevk Teknesi",
    40: "Yüksek Hız", 41: "Yüksek Hız", 42: "Yüksek Hız",
    50: "Pilot Gemisi", 51: "SAR", 52: "Römorkör", 53: "Liman Gemisi",
    54: "Seyir Gemisi", 55: "Polis", 58: "Tıbbi", 59: "RIB",
    60: "Yolcu", 61: "Yolcu", 62: "Yolcu", 63: "Yolcu", 69: "Yolcu",
    70: "Kargo", 71: "Kargo", 72: "Kargo", 73: "Kargo", 79: "Kargo",
    80: "Tanker", 81: "Tanker", 82: "Tanker", 83: "Tanker", 89: "Tanker",
    90: "Diğer", 99: "Diğer",
}

VESSEL_TYPE_LABELS = {
    35: "Askeri",
    80: "Tanker", 81: "Tanker", 82: "Tanker", 83: "Tanker", 89: "Tanker",
    60: "Yolcu",  61: "Yolcu",  62: "Yolcu",  63: "Yolcu",  69: "Yolcu",
    70: "Kargo",  71: "Kargo",  72: "Kargo",  73: "Kargo",  79: "Kargo",
    30: "Balıkçı",
}


class AISCollector:
    """
    aisstream.io WebSocket bağlantısını yönetir.
    Gelen konumları cache'e yazar, bağlantı kopunca yeniden bağlanır.
    """

    def __init__(self) -> None:
        self._vessels: Dict[str, Dict[str, Any]] = {}   # mmsi → vessel dict
        self._running  = False
        self._connected = False
        self._msg_count = 0
        self._last_update: Optional[datetime] = None

    # ── Dışarıya açık arayüz ──────────────────────────────────

    def get_vessels(self) -> List[Dict[str, Any]]:
        """Mevcut gemi listesini döner (cache'den)."""
        return list(self._vessels.values())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected":    self._connected,
            "vessel_count": len(self._vessels),
            "msg_count":    self._msg_count,
            "last_update":  self._last_update.isoformat() if self._last_update else None,
        }

    async def run_forever(self) -> None:
        """Arka planda sürekli çalışır; bağlantı kopunca yeniden bağlanır."""
        self._running = True
        backoff = 2.0
        while self._running:
            try:
                await self._connect_and_stream()
                backoff = 2.0
            except Exception as e:
                self._connected = False
                logger.warning("AIS bağlantısı kesildi: %s — %ss sonra tekrar deneniyor.", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    def stop(self) -> None:
        self._running = False

    # ── İç metodlar ────────────────────────────────────────────

    async def _connect_and_stream(self) -> None:
        try:
            import websockets  # type: ignore
        except ImportError:
            logger.error("websockets kütüphanesi yok. 'pip install websockets' çalıştırın.")
            await asyncio.sleep(30)
            return

        subscribe_msg = json.dumps({
            "APIKey":        AIS_API_KEY,
            "BoundingBoxes": [
                [[bb[0], bb[1]], [bb[2], bb[3]]]
                for bb in AIS_BOUNDING_BOXES
            ],
            "FilterMessageTypes": ["PositionReport", "ExtendedClassBPositionReport"],
        })

        logger.info("AIS WebSocket bağlanıyor → %s", AIS_WS_URL)
        async with websockets.connect(
            AIS_WS_URL,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
            max_size=2**20,
        ) as ws:
            await ws.send(subscribe_msg)
            self._connected = True
            logger.info("AIS akışı başladı.")

            async for raw in ws:
                if not self._running:
                    break
                try:
                    self._process_message(json.loads(raw))
                except Exception as e:
                    logger.debug("AIS mesaj işleme hatası: %s", e)

    def _process_message(self, msg: Dict[str, Any]) -> None:
        meta = msg.get("MetaData", {})
        mmsi = str(meta.get("MMSI", "")).strip()
        if not mmsi:
            return

        msg_type = msg.get("MessageType", "")
        payload  = msg.get("Message", {})

        report = (
            payload.get("PositionReport")
            or payload.get("ExtendedClassBPositionReport")
            or {}
        )

        lat = float(report.get("Latitude",  meta.get("latitude",  0)))
        lon = float(report.get("Longitude", meta.get("longitude", 0)))

        # Geçersiz konumları filtrele
        if lat == 0.0 and lon == 0.0:
            return
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return

        sog     = float(report.get("Sog",          meta.get("ShipSpeed",   0)) or 0)
        cog     = float(report.get("Cog",          0) or 0)
        heading = float(report.get("TrueHeading",  cog) or cog)
        if heading >= 511:   # NMEA geçersiz değeri
            heading = cog

        ship_name = str(meta.get("ShipName", "")).strip() or f"MMSI-{mmsi}"
        ship_type_code = int(meta.get("ShipType", 0) or 0)
        ship_type_label = SHIP_TYPE_MAP.get(ship_type_code // 10 * 10,
                          SHIP_TYPE_MAP.get(ship_type_code, "Bilinmiyor"))

        # Anomali skoru sonradan anomaly module tarafından atanacak
        vessel = {
            "id":           f"MMSI-{mmsi}",
            "mmsi":         mmsi,
            "name":         ship_name,
            "lat":          lat,
            "lon":          lon,
            "speed":        round(sog, 1),       # knot
            "heading":      round(heading, 0),
            "vessel_type":  ship_type_label,
            "ship_type_code": ship_type_code,
            "timestamp":    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "anomaly_score": 0,
            "risk_score":    0,
            "risk_level":    "Düşük",
            "anomaly_flag":  False,
            "anomaly_reason": "Canlı AIS verisi.",
            "flags":        ["AIS_LIVE"],
            "route":        [],
            "source":       "aisstream",
        }

        # Askeri gemi özel işaretleme
        if ship_type_code == 35:
            vessel["flags"].append("MILITARY")
            vessel["anomaly_score"] = 30
            vessel["risk_level"]    = "Orta"
            vessel["anomaly_reason"] = "Askeri gemi — standart izleme."
            # DB'ye kaydet
            try:
                from track_store import track_store
                track_store.save_military_vessel(vessel)
            except Exception:
                pass

        self._vessels[mmsi] = vessel
        self._msg_count += 1
        self._last_update = datetime.now(timezone.utc)

        if self._msg_count % 500 == 0:
            logger.info("AIS: %d gemi izleniyor (toplam %d mesaj)", len(self._vessels), self._msg_count)


# Global instance — scalable_api.py'den import edilir
ais_collector = AISCollector()
