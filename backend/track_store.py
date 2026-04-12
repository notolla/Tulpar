"""
TULPAR — Kalıcı İz Veritabanı (SQLite)

Tablolar:
  military_sightings  — Askeri/bilinmeyen uçakların tüm konum kayıtları (silinmez)
  squawk_alerts       — 7500/7600/7700 acil squawk kayıtları (silinmez)
  military_vessels    — Askeri gemi geçişleri
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(__file__)
DB_PATH = os.path.join(_BASE, "data", "tulpar.db")

SQUAWK_MEANINGS = {
    "7500": "UÇAK KAÇIRMA",
    "7600": "RADYO ARIZASI",
    "7700": "ACİL DURUM",
}


class TrackStore:
    """Thread-safe SQLite sarmalayıcı."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        self._lock    = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        logger.info("TrackStore hazır → %s", db_path)

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    # ── Şema ──────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._lock:
            c = self._conn()
            c.executescript("""
                CREATE TABLE IF NOT EXISTS military_sightings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign    TEXT    NOT NULL,
                    lat         REAL    NOT NULL,
                    lon         REAL    NOT NULL,
                    altitude    REAL    DEFAULT 0,
                    speed       REAL    DEFAULT 0,
                    heading     REAL    DEFAULT 0,
                    squawk      TEXT    DEFAULT '',
                    flags       TEXT    DEFAULT '',
                    aircraft_type TEXT  DEFAULT '',
                    risk_score  INTEGER DEFAULT 0,
                    timestamp   INTEGER NOT NULL,
                    source      TEXT    DEFAULT 'adsb'
                );

                CREATE TABLE IF NOT EXISTS squawk_alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign    TEXT    NOT NULL,
                    squawk      TEXT    NOT NULL,
                    meaning     TEXT    NOT NULL,
                    lat         REAL,
                    lon         REAL,
                    altitude    REAL,
                    speed       REAL,
                    timestamp   INTEGER NOT NULL,
                    acknowledged INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS military_vessels (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    mmsi        TEXT    NOT NULL,
                    name        TEXT    DEFAULT '',
                    lat         REAL    NOT NULL,
                    lon         REAL    NOT NULL,
                    speed       REAL    DEFAULT 0,
                    heading     REAL    DEFAULT 0,
                    timestamp   INTEGER NOT NULL,
                    source      TEXT    DEFAULT 'ais'
                );

                CREATE INDEX IF NOT EXISTS idx_mil_ts       ON military_sightings(timestamp);
                CREATE INDEX IF NOT EXISTS idx_mil_cs       ON military_sightings(callsign);
                CREATE INDEX IF NOT EXISTS idx_squawk_ts    ON squawk_alerts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_milves_ts    ON military_vessels(timestamp);
            """)
            c.commit()
            c.close()

    # ── Askeri uçak kaydetme ──────────────────────────────────────────────────

    def save_military_sighting(self, ac: Dict[str, Any]) -> None:
        ts = int(datetime.now(timezone.utc).timestamp())
        with self._lock:
            c = self._conn()
            c.execute(
                """
                INSERT INTO military_sightings
                (callsign, lat, lon, altitude, speed, heading, squawk, flags,
                 aircraft_type, risk_score, timestamp, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ac.get("callsign", ""),
                    float(ac.get("lat", 0)),
                    float(ac.get("lon", 0)),
                    float(ac.get("altitude", 0)),
                    float(ac.get("speed", 0)),
                    float(ac.get("heading", 0)),
                    ac.get("squawk", ""),
                    ",".join(ac.get("flags", [])),
                    ac.get("aircraft_type", ""),
                    int(ac.get("risk_score", 0)),
                    ts,
                    ac.get("source", "adsb"),
                ),
            )
            c.commit()
            c.close()

    # ── Squawk alert kaydetme ──────────────────────────────────────────────────

    def save_squawk_alert(self, ac: Dict[str, Any], squawk: str) -> bool:
        """Aynı callsign için 5 dakika içinde tekrar kaydetme. True = yeni kayıt."""
        ts      = int(datetime.now(timezone.utc).timestamp())
        meaning = SQUAWK_MEANINGS.get(squawk, f"SQUAWK {squawk}")
        with self._lock:
            c = self._conn()
            dup = c.execute(
                "SELECT id FROM squawk_alerts WHERE callsign=? AND squawk=? AND timestamp>? LIMIT 1",
                (ac.get("callsign", ""), squawk, ts - 300),
            ).fetchone()
            if dup:
                c.close()
                return False
            c.execute(
                """
                INSERT INTO squawk_alerts
                (callsign, squawk, meaning, lat, lon, altitude, speed, timestamp)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    ac.get("callsign", ""),
                    squawk,
                    meaning,
                    float(ac.get("lat", 0)),
                    float(ac.get("lon", 0)),
                    float(ac.get("altitude", 0)),
                    float(ac.get("speed", 0)),
                    ts,
                ),
            )
            c.commit()
            c.close()
            logger.warning("SQUAWK ALARM: %s → %s (%s)", ac.get("callsign"), squawk, meaning)
            return True

    # ── Askeri gemi kaydetme ──────────────────────────────────────────────────

    def save_military_vessel(self, vessel: Dict[str, Any]) -> None:
        ts = int(datetime.now(timezone.utc).timestamp())
        with self._lock:
            c = self._conn()
            c.execute(
                """
                INSERT INTO military_vessels (mmsi, name, lat, lon, speed, heading, timestamp, source)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    vessel.get("mmsi", ""),
                    vessel.get("name", ""),
                    float(vessel.get("lat", 0)),
                    float(vessel.get("lon", 0)),
                    float(vessel.get("speed", 0)),
                    float(vessel.get("heading", 0)),
                    ts,
                    vessel.get("source", "ais"),
                ),
            )
            c.commit()
            c.close()

    # ── Sorgu metodları ───────────────────────────────────────────────────────

    def get_military_zones(self, hours: int = 12) -> List[Dict[str, Any]]:
        """
        Son N saatteki askeri aktiviteden bölgeler türetir.
        Her benzersiz callsign → bir bölge.
        """
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        with self._lock:
            c = self._conn()
            rows = c.execute(
                """
                SELECT
                    callsign,
                    AVG(lat)       AS center_lat,
                    AVG(lon)       AS center_lon,
                    MAX(lat) - MIN(lat) AS lat_span,
                    MAX(lon) - MIN(lon) AS lon_span,
                    MAX(altitude)  AS max_altitude,
                    AVG(speed)     AS avg_speed,
                    COUNT(*)       AS point_count,
                    MIN(timestamp) AS first_seen,
                    MAX(timestamp) AS last_seen,
                    MAX(risk_score) AS peak_risk
                FROM military_sightings
                WHERE timestamp > ?
                GROUP BY callsign
                HAVING point_count >= 1
                ORDER BY last_seen DESC
                """,
                (since,),
            ).fetchall()
            c.close()

        zones = []
        for r in rows:
            r = dict(r)
            # Yarıçap hesabı
            lat_km = r["lat_span"] * 111.0
            lon_km = r["lon_span"] * 111.0 * abs(math.cos(math.radians(r["center_lat"])))
            radius = max(25.0, (lat_km + lon_km) / 2 + 20)
            age_min = int((datetime.now(timezone.utc).timestamp() - r["last_seen"]) / 60)

            zones.append({
                "callsign":         r["callsign"],
                "center_lat":       round(r["center_lat"], 4),
                "center_lon":       round(r["center_lon"], 4),
                "radius_km":        round(radius, 1),
                "exclusion_radius_km": round(radius * 1.4 + 15, 1),
                "point_count":      r["point_count"],
                "first_seen":       r["first_seen"],
                "last_seen":        r["last_seen"],
                "age_minutes":      age_min,
                "max_altitude":     r["max_altitude"],
                "avg_speed":        round(r["avg_speed"] or 0, 1),
                "peak_risk":        r["peak_risk"],
                "active":           age_min < 60,   # Son 60 dakikada görüldüyse aktif
            })
        return zones

    def get_squawk_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        with self._lock:
            c = self._conn()
            rows = c.execute(
                "SELECT * FROM squawk_alerts WHERE timestamp > ? ORDER BY timestamp DESC",
                (since,),
            ).fetchall()
            c.close()
        return [dict(r) for r in rows]

    def get_military_vessel_zones(self, hours: int = 12) -> List[Dict[str, Any]]:
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        with self._lock:
            c = self._conn()
            rows = c.execute(
                """
                SELECT
                    mmsi, name,
                    AVG(lat) AS center_lat, AVG(lon) AS center_lon,
                    COUNT(*) AS point_count,
                    MAX(timestamp) AS last_seen
                FROM military_vessels
                WHERE timestamp > ?
                GROUP BY mmsi
                ORDER BY last_seen DESC
                """,
                (since,),
            ).fetchall()
            c.close()
        return [dict(r) for r in rows]

    def get_summary_data(self, hours: int = 24) -> Dict[str, Any]:
        """LLM özetlemesi için ham veri paketi."""
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        with self._lock:
            c = self._conn()
            aircraft_rows = c.execute(
                """
                SELECT
                    callsign,
                    COUNT(*)       AS observations,
                    AVG(lat)       AS avg_lat,
                    AVG(lon)       AS avg_lon,
                    MAX(altitude)  AS max_altitude,
                    AVG(speed)     AS avg_speed,
                    MIN(timestamp) AS first_seen,
                    MAX(timestamp) AS last_seen,
                    MAX(risk_score) AS peak_risk
                FROM military_sightings
                WHERE timestamp > ?
                GROUP BY callsign
                ORDER BY peak_risk DESC, observations DESC
                """,
                (since,),
            ).fetchall()

            squawk_rows = c.execute(
                "SELECT * FROM squawk_alerts WHERE timestamp > ? ORDER BY timestamp DESC",
                (since,),
            ).fetchall()

            vessel_rows = c.execute(
                """
                SELECT mmsi, name, COUNT(*) AS obs,
                       AVG(lat) AS avg_lat, AVG(lon) AS avg_lon,
                       MAX(timestamp) AS last_seen
                FROM military_vessels
                WHERE timestamp > ?
                GROUP BY mmsi
                ORDER BY last_seen DESC
                """,
                (since,),
            ).fetchall()
            c.close()

        return {
            "period_hours":           hours,
            "military_aircraft":      [dict(r) for r in aircraft_rows],
            "squawk_alerts":          [dict(r) for r in squawk_rows],
            "military_vessels":       [dict(r) for r in vessel_rows],
            "total_mil_observations": sum(r["observations"] for r in aircraft_rows),
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            c = self._conn()
            mil   = c.execute("SELECT COUNT(*) FROM military_sightings").fetchone()[0]
            sqk   = c.execute("SELECT COUNT(*) FROM squawk_alerts").fetchone()[0]
            ves   = c.execute("SELECT COUNT(*) FROM military_vessels").fetchone()[0]
            c.close()
        return {"military_sightings": mil, "squawk_alerts": sqk, "military_vessels": ves}


# Uygulama genelinde tek örnek
track_store = TrackStore()
