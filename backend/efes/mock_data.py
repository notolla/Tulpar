"""
Gateway fallback: test_flights.json ve test_vessels.json'dan gerçekçi veri.
Üretimde collector doldurur; bu veriler dayanıklılık ve demo içindir.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_TEST_FLIGHTS = _BACKEND_ROOT / "data" / "test_flights.json"
_TEST_VESSELS = _BACKEND_ROOT / "data" / "test_vessels.json"
_STRATEGIC_ZONES = _BACKEND_ROOT / "data" / "strategicZones.json"


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("JSON yüklenemedi %s: %s", path, e)
        return None


def mock_aircraft() -> List[Dict[str, Any]]:
    """test_flights.json'dan gerçekçi uçak listesi döner (28 uçak)."""
    data = _load_json(_TEST_FLIGHTS)
    if isinstance(data, list) and data:
        ts = _now()
        result = []
        for ac in data:
            entry = dict(ac)
            entry["timestamp"] = ts
            # Eksik alanları doldur
            entry.setdefault("risk_score", entry.get("anomaly_score", 0))
            entry.setdefault("anomaly_flag", entry.get("anomaly_score", 0) >= 25)
            entry.setdefault("route", [])
            entry.setdefault("flags", [])
            entry["source"] = "test_data"
            result.append(entry)
        logger.info("Test verisi: %d uçak yüklendi.", len(result))
        return result

    # Son çare: 2 temel mock
    logger.warning("test_flights.json yüklenemedi, minimal mock kullanılıyor.")
    return [
        {
            "id": "MOCK-1", "callsign": "THY0001",
            "lat": 39.92, "lon": 32.85,
            "altitude": 10600, "speed": 420, "heading": 85,
            "timestamp": _now(), "aircraft_type": "CIV",
            "anomaly_score": 12, "risk_score": 12,
            "risk_level": "Düşük", "anomaly_flag": False,
            "anomaly_reason": "Mock veri.", "flags": ["MOCK"], "route": [], "source": "mock",
        },
    ]


def mock_vessels() -> List[Dict[str, Any]]:
    """test_vessels.json'dan gerçekçi gemi listesi döner (18 gemi)."""
    data = _load_json(_TEST_VESSELS)
    if isinstance(data, list) and data:
        ts = _now()
        result = []
        for v in data:
            entry = dict(v)
            entry["timestamp"] = ts
            entry.setdefault("risk_score", entry.get("anomaly_score", 0))
            entry.setdefault("anomaly_flag", entry.get("anomaly_score", 0) >= 25)
            entry.setdefault("route", [])
            entry.setdefault("flags", [])
            entry["source"] = "test_data"
            result.append(entry)
        logger.info("Test verisi: %d gemi yüklendi.", len(result))
        return result

    logger.warning("test_vessels.json yüklenemedi, minimal mock kullanılıyor.")
    return [
        {
            "id": "MMSI-MOCK-1", "mmsi": "271000999",
            "name": "MV EFES DENİZ",
            "lat": 40.75, "lon": 29.0,
            "speed": 12.0, "heading": 95,
            "timestamp": _now(), "vessel_type": "Cargo",
            "anomaly_score": 5, "risk_score": 5,
            "risk_level": "Düşük", "anomaly_flag": False,
            "anomaly_reason": "Mock gemi.", "flags": ["MOCK"], "route": [], "source": "mock",
        },
    ]


def load_strategic_zones_geojson() -> Dict[str, Any]:
    path = _STRATEGIC_ZONES
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"type": "FeatureCollection", "features": []}


def enrich_zone_features(fc: Dict[str, Any]) -> Dict[str, Any]:
    """Leaflet/Cesium katmanları için name / importance türet."""
    out = dict(fc)
    feats = []
    for f in fc.get("features", []) or []:
        if f.get("type") != "Feature":
            continue
        p = dict(f.get("properties") or {})
        p.setdefault("name", p.get("ad", "Bölge"))
        imp = p.get("importance") or p.get("onemSeviyesi", "Orta")
        p["importance"] = imp
        feats.append({**f, "properties": p})
    out["features"] = feats
    return out
