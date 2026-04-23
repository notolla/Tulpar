"""
TULPAR — Ana API (FastAPI)
Port: 8000 | Proxy: Vite /api → localhost:8000

Veri hiyerarşisi:
  1. OpenSky (60 sn'de bir, kimlik doğrulamalı) → bellek cache
  2. Cache dolu ise cache'den döner
  3. Her ikisi de başarısızsa test_flights.json / test_vessels.json
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from cache_layer import TTL_STRATEGIC_ZONES, cache_layer
from efes.mock_data import (
    enrich_zone_features,
    load_strategic_zones_geojson,
    mock_aircraft,
    mock_vessels,
)
from efes.opensky_client import default_bounds, fetch_opensky_aircraft
from ais_collector import ais_collector
from track_store import track_store
from gdelt_news_feed import (
    run_background_task as gdelt_background_task,
    get_news as gdelt_get_news,
    force_refresh as gdelt_force_refresh,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── Sabitler ────────────────────────────────────────────────────────────────
OPENSKY_INTERVAL = int(os.getenv("OPENSKY_INTERVAL", "62"))   # saniye
_last_opensky_fetch: float = 0.0
_opensky_lock = asyncio.Lock()
_data_source: str = "test"          # "live" | "cache" | "test"
_last_live_at: float = 0.0          # son başarılı OpenSky zamanı


# ─── OpenSky arka plan görevi ─────────────────────────────────────────────────
async def _opensky_background():
    """Sürekli OpenSky'ı poll eder, cache'e yazar."""
    global _last_opensky_fetch, _data_source, _last_live_at
    await asyncio.sleep(2)                    # uygulama başlangıcında 2 sn bekle
    while True:
        try:
            logger.info("OpenSky çekimi başlatılıyor…")
            aircraft = await fetch_opensky_aircraft(default_bounds())
            if aircraft:
                # Aktif askeri zonları al (track_store'dan) ve anomali skoru ekle
                try:
                    from anomaly.detector import score_aircraft_batch
                    mil_zones = track_store.get_military_zones(hours=6)
                    aircraft = score_aircraft_batch(aircraft, military_zones=mil_zones)
                except Exception as e:
                    logger.warning("Anomali skoru hesaplanamadı: %s", e)

                # Askeri uçakları ve squawk alarmlarını kaydet
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _process_military_and_squawk, aircraft)

                await cache_layer.set_data("aircraft:latest", aircraft)
                await cache_layer.set_data(
                    "aircraft:meta",
                    {"count": len(aircraft), "source": "live", "ts": datetime.utcnow().isoformat()},
                )
                _data_source = "live"
                _last_live_at = time.time()
                mil_count = sum(1 for a in aircraft if "MILITARY" in a.get("flags", []))
                logger.info("OpenSky: %d uçak (%d askeri) cache'e yazıldı.", len(aircraft), mil_count)
            else:
                logger.warning("OpenSky boş döndü — test verisi kullanılacak.")
                _data_source = "test" if not _last_live_at else "cache"
        except Exception as e:
            logger.error("OpenSky arka plan hatası: %s", e)
        _last_opensky_fetch = time.time()
        await asyncio.sleep(OPENSKY_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache_layer.init_redis()
    # Stratejik bölgeleri önceden cache'e al
    try:
        fc = enrich_zone_features(load_strategic_zones_geojson())
        await cache_layer.set_data("strategic_zones:latest", fc, ttl=TTL_STRATEGIC_ZONES)
    except Exception as e:
        logger.warning("Stratejik bölge önbelleği: %s", e)

    opensky_task = asyncio.create_task(_opensky_background())
    ais_task     = asyncio.create_task(ais_collector.run_forever())
    gdelt_task   = asyncio.create_task(gdelt_background_task(cache_layer))
    yield
    opensky_task.cancel()
    ais_task.cancel()
    gdelt_task.cancel()
    ais_collector.stop()
    await cache_layer.close()


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="TULPAR API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Cache yardımcıları ───────────────────────────────────────────────────────
async def _get_aircraft() -> List[Dict[str, Any]]:
    cached = await cache_layer.get_data("aircraft:latest")
    if isinstance(cached, list) and cached:
        return cached
    # Cache boş → test verisi + anomali skoru
    data = mock_aircraft()
    try:
        from anomaly.detector import score_aircraft_batch
        data = score_aircraft_batch(data)
    except Exception:
        pass
    return data


async def _get_vessels() -> List[Dict[str, Any]]:
    # 1. Canlı AIS verisi
    live = ais_collector.get_vessels()
    if live:
        try:
            from anomaly.detector import score_vessel_batch
            live = score_vessel_batch(live)
        except Exception:
            pass
        return live

    # 2. Cache
    cached = await cache_layer.get_data("vessels:latest")
    if isinstance(cached, list) and cached:
        return cached

    # 3. Test verisi (AIS henüz bağlanmadı)
    data = mock_vessels()
    try:
        from anomaly.detector import score_vessel_batch
        data = score_vessel_batch(data)
    except Exception:
        pass
    return data


async def _get_zones() -> Dict[str, Any]:
    cached = await cache_layer.get_data("strategic_zones:latest")
    if isinstance(cached, dict) and cached.get("features"):
        return cached
    return enrich_zone_features(load_strategic_zones_geojson())


# ─── Statik haberler (RSS entegrasyonu placeholder) ───────────────────────────
_MOCK_NEWS = [
    {
        "id": "n1", "title": "Doğu Akdeniz'de NATO deniz tatbikatı başladı",
        "source": "Defense News", "time": "13:45", "category": "Savunma",
        "region": "Doğu Akdeniz",
        "summary": "NATO üye devletlerinin katılımıyla başlayan tatbikat 5 gün sürecek.",
    },
    {
        "id": "n2", "title": "Ege hava sahasında NOTAM yayımlandı",
        "source": "DHMİ", "time": "14:10", "category": "Havacılık",
        "region": "Ege",
        "summary": "Yunanistan FIR'ına ait kısıtlama NOTAM'ı uçuş operatörlerine iletildi.",
    },
    {
        "id": "n3", "title": "İstanbul Boğazı'nda tanker geçiş yoğunluğu arttı",
        "source": "Kıyı Emniyeti", "time": "14:20", "category": "Denizcilik",
        "region": "İstanbul Boğazı",
        "summary": "Son 24 saatte Boğaz'dan geçen tanker sayısı aylık ortalamanın %35 üzerinde.",
    },
    {
        "id": "n4", "title": "Karadeniz'de Rusya deniz tatbikatı",
        "source": "TASS / Reuters", "time": "11:30", "category": "Savunma",
        "region": "Karadeniz",
        "summary": "Rus Karadeniz Filosu'nun tatbikat koordinatları açıklandı.",
    },
    {
        "id": "n5", "title": "Türkiye-Yunanistan CBM görüşmeleri devam ediyor",
        "source": "Dışişleri Bakanlığı", "time": "10:15", "category": "Diplomasi",
        "region": "Ege",
        "summary": "İkili güven artırıcı önlemler kapsamındaki teknik toplantı Atina'da yapıldı.",
    },
    {
        "id": "n6", "title": "F-35B teslimatları hızlanıyor — Türkiye alternatifleri değerlendiriyor",
        "source": "Jane's Defence", "time": "09:00", "category": "Savunma",
        "region": "Türkiye",
        "summary": "Savunma Sanayii Başkanlığı'nın KAAN programına tahsis arttırıldı.",
    },
]


# ─── Endpointler ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "service": "TULPAR"}


@app.get("/api/aircraft")
async def api_aircraft():
    try:
        return await _get_aircraft()
    except Exception as e:
        logger.error("/api/aircraft: %s", e)
        return mock_aircraft()


@app.get("/api/aircrafts")
async def api_aircraft_alias():
    return await api_aircraft()


@app.get("/api/aircraft/live-count")
async def api_live_count():
    """Veri kaynağı durumu: gerçek / cache / test"""
    meta = await cache_layer.get_data("aircraft:meta")
    aircraft = await cache_layer.get_data("aircraft:latest")
    count = len(aircraft) if isinstance(aircraft, list) else 0
    age_s = int(time.time() - _last_live_at) if _last_live_at else None

    if _data_source == "live" and count > 0:
        status = "live"
        label = f"{count} gerçek uçak"
    elif count > 0:
        status = "cache"
        label = f"Cache: {count} uçak ({age_s} sn önce)" if age_s else f"Cache: {count} uçak"
    else:
        data = mock_aircraft()
        status = "test"
        label = f"Test verisi: {len(data)} uçak"
        count = len(data)

    return {
        "status": status,
        "count": count,
        "label": label,
        "last_live_seconds_ago": age_s,
        "meta": meta,
    }


@app.get("/api/vessels")
async def api_vessels():
    try:
        return await _get_vessels()
    except Exception as e:
        logger.error("/api/vessels: %s", e)
        return mock_vessels()


@app.get("/api/strategic-zones")
async def api_strategic_zones():
    try:
        return await _get_zones()
    except Exception as e:
        logger.error("/api/strategic-zones: %s", e)
        return enrich_zone_features(load_strategic_zones_geojson())


@app.get("/api/alerts")
async def api_alerts():
    """Anomali bayrağı taşıyan varlıklardan otomatik uyarı üret."""
    aircraft = await _get_aircraft()
    vessels = await _get_vessels()
    alerts = []

    for ac in aircraft:
        if ac.get("anomaly_flag") or ac.get("anomaly_score", 0) >= 25:
            lat, lon = ac.get("lat", 0), ac.get("lon", 0)
            alerts.append({
                "id": f"ac-{ac.get('id', 'unk')}",
                "type": "hava",
                "entity_id": ac.get("id", ""),
                "entity_name": ac.get("callsign", "UNKNOWN"),
                "title": _alert_title(ac.get("risk_level", "Orta"), "uçak"),
                "description": ac.get("anomaly_reason", "Anomali tespit edildi."),
                "risk_level": ac.get("risk_level", "Orta"),
                "timestamp": ac.get("timestamp", datetime.utcnow().isoformat()),
                "coordinates": {"lat": lat, "lon": lon},
                "region": _coords_to_region(lat, lon),
                "category": "hava",
                "anomaly_score": ac.get("anomaly_score", 0),
                "flags": ac.get("flags", []),
            })

    for v in vessels:
        if v.get("anomaly_flag") or v.get("anomaly_score", 0) >= 25:
            lat, lon = v.get("lat", 0), v.get("lon", 0)
            alerts.append({
                "id": f"vs-{v.get('id', 'unk')}",
                "type": "deniz",
                "entity_id": v.get("id", ""),
                "entity_name": v.get("name", "UNKNOWN"),
                "title": _alert_title(v.get("risk_level", "Orta"), "gemi"),
                "description": v.get("anomaly_reason", "Anomali tespit edildi."),
                "risk_level": v.get("risk_level", "Orta"),
                "timestamp": v.get("timestamp", datetime.utcnow().isoformat()),
                "coordinates": {"lat": lat, "lon": lon},
                "region": _coords_to_region(lat, lon),
                "category": "deniz",
                "anomaly_score": v.get("anomaly_score", 0),
                "flags": v.get("flags", []),
            })

    # Skora göre sırala (en yüksek önce)
    alerts.sort(key=lambda x: x.get("anomaly_score", 0), reverse=True)
    return alerts


@app.get("/api/news")
async def api_news(
    region: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    regions: Optional[str] = None,   # virgülle ayrılmış çoklu bölge (anomali filtresi)
):
    news = await gdelt_get_news(fallback=[])
    if category:
        news = [n for n in news if category.lower() in n.get("category", "").lower()]
    if source:
        news = [n for n in news if source.lower() in n.get("source", "").lower()]
    if regions:
        region_list = [r.strip().lower() for r in regions.split(",") if r.strip()]
        news = [n for n in news if any(r in n.get("region", "").lower() for r in region_list)]
    elif region:
        news = [n for n in news if region.lower() in n.get("region", "").lower()]
    return news


@app.post("/api/news/refresh")
async def api_news_refresh():
    count = await gdelt_force_refresh()
    return {"status": "ok", "count": count}


@app.get("/api/news/debug")
async def api_news_debug():
    import gdelt_news_feed as gn
    from collections import Counter
    na_result = await gn.fetch_news_from_newsapi()
    rss_result = await gn.fetch_news_from_rss()
    return {
        "newsapi_key_set": bool(os.getenv("NEWSAPI_KEY")),
        "newsapi_count":   len(na_result)  if isinstance(na_result, list)  else str(na_result),
        "rss_count":       len(rss_result) if isinstance(rss_result, list) else str(rss_result),
        "rss_sources":     dict(Counter(n["source"] for n in rss_result)) if isinstance(rss_result, list) else {},
        "store_count":     len(gn._store),
        "store_age_s":     int(time.time() - gn._store_ts),
    }


@app.get("/api/vessels/live-count")
async def api_vessels_count():
    ais_stats = ais_collector.get_stats()
    live = ais_collector.get_vessels()
    count = len(live)
    if count > 0:
        status = "live"
        label  = f"{count} gerçek gemi (AIS canlı)"
    else:
        test = mock_vessels()
        status = "test"
        label  = f"Test verisi: {len(test)} gemi"
        count  = len(test)
    return {
        "status":      status,
        "count":       count,
        "label":       label,
        "ais_stats":   ais_stats,
    }


@app.get("/api/stats")
async def api_stats():
    aircraft = await _get_aircraft()
    vessels  = await _get_vessels()
    anomaly_ac = [a for a in aircraft if a.get("anomaly_flag")]
    anomaly_vs = [v for v in vessels  if v.get("anomaly_flag")]
    ais_stats  = ais_collector.get_stats()
    return {
        "aircraft_count": len(aircraft),
        "vessel_count":   len(vessels),
        "anomaly_count":  len(anomaly_ac) + len(anomaly_vs),
        "critical_count": sum(1 for x in aircraft + vessels if x.get("risk_level") == "Kritik"),
        "data_source":    _data_source,
        "ais_connected":  ais_stats["connected"],
        "ais_vessels":    ais_stats["vessel_count"],
        "timestamp":      datetime.utcnow().isoformat(),
    }


def _process_military_and_squawk(aircraft: List[Dict[str, Any]]) -> None:
    """
    Her OpenSky döngüsünde:
    - MILITARY flag'li uçakları DB'ye kaydet
    - Squawk 7500/7600/7700 tespitinde alert kaydet
    """
    for ac in aircraft:
        flags  = ac.get("flags", [])
        squawk = str(ac.get("squawk", "")).strip()

        # Squawk acil kodu
        if squawk in ("7500", "7600", "7700"):
            is_new = track_store.save_squawk_alert(ac, squawk)
            if is_new:
                logger.warning(
                    "🚨 SQUAWK %s — %s @ (%.2f, %.2f)",
                    squawk, ac.get("callsign", "?"),
                    ac.get("lat", 0), ac.get("lon", 0),
                )

        # Askeri / bilinmeyen uçak kaydı
        if "MILITARY" in flags or "NO_TRANSPONDER" in flags:
            record = dict(ac)
            # UNKNOWN callsign → ICAO24 ID ile kaydet (ayrı zone)
            cs = str(record.get("callsign", "")).strip()
            if not cs or cs.upper() in ("UNKNOWN", "", "00000000"):
                record["callsign"] = f"UNKN-{record.get('id', 'X')[:6]}"
            track_store.save_military_sighting(record)


# ── Military endpointleri ──────────────────────────────────────────────────────

@app.get("/api/military/zones")
async def api_military_zones(hours: int = 12):
    """Son N saatteki askeri aktivite bölgelerini döner."""
    try:
        zones = track_store.get_military_zones(hours=hours)
        return {"zones": zones, "count": len(zones), "hours": hours}
    except Exception as e:
        logger.error("/api/military/zones: %s", e)
        return {"zones": [], "count": 0, "hours": hours}


@app.get("/api/military/aircraft")
async def api_military_aircraft():
    """Şu an görülen askeri uçaklar."""
    aircraft = await _get_aircraft()
    mil = [a for a in aircraft if "MILITARY" in a.get("flags", [])]
    return {"aircraft": mil, "count": len(mil)}


@app.get("/api/military/squawk-alerts")
async def api_squawk_alerts(hours: int = 24):
    """Son N saatteki squawk alarmları."""
    try:
        alerts = track_store.get_squawk_alerts(hours=hours)
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        logger.error("/api/military/squawk-alerts: %s", e)
        return {"alerts": [], "count": 0}


@app.get("/api/military/summary")
async def api_military_summary(hours: int = 24):
    """
    LLM özetleme için ham veri.
    Sonraki adımda: POST /api/military/summary/generate → LLM çağrısı
    """
    try:
        data = track_store.get_summary_data(hours=hours)
        data["generated_at"] = datetime.utcnow().isoformat()
        return data
    except Exception as e:
        logger.error("/api/military/summary: %s", e)
        return {"error": str(e)}


@app.get("/api/military/db-stats")
async def api_military_db_stats():
    """DB kayıt istatistikleri."""
    return track_store.stats()


def _coords_to_region(lat: float, lon: float) -> str:
    """
    Koordinattan bölge adı çıkar.
    İsimler gdelt_news_feed._infer_region() çıktısıyla birebir eşleşmeli
    ki anomali filtresi haberleri doğru eşleştirsin.
    Sıralama önemli — en küçük/spesifik kutu üstte olmalı.
    """
    boxes = [
        # lat_min, lon_min, lat_max, lon_max
        # ── Türkiye (Boğaz dahil, Ege/Akdeniz'den önce) ──────────────────────
        ("Türkiye",         36.0,  26.0,  42.5,  45.0),

        # ── Karadeniz ────────────────────────────────────────────────────────
        ("Karadeniz",       41.0,  28.0,  46.5,  42.0),

        # ── Ege / Doğu Akdeniz (Doğu sınırı 34°D — İsrail/Suriye başlamadan önce)
        ("Ege/Akdeniz",     30.0,  18.0,  42.0,  34.0),

        # ── Ukrayna ───────────────────────────────────────────────────────────
        ("Ukrayna",         44.0,  22.0,  53.0,  40.0),

        # ── Körfez (İran, Irak, körfez ülkeleri, Hürmüz) ─────────────────────
        ("Körfez",          21.0,  48.0,  31.0,  63.0),

        # ── Kızıldeniz / Yemen ────────────────────────────────────────────────
        ("Kızıldeniz",      10.0,  32.0,  30.0,  45.0),

        # ── Orta Doğu (İsrail, Suriye, Lübnan, Filistin, Ürdün) ─────────────
        ("Orta Doğu",       28.0,  34.0,  38.0,  43.0),

        # ── Balkanlar ─────────────────────────────────────────────────────────
        ("Balkanlar",       40.0,  13.0,  47.0,  23.0),

        # ── NATO/Avrupa ───────────────────────────────────────────────────────
        ("NATO/Avrupa",     35.0, -10.0,  72.0,  32.0),

        # ── Rusya ─────────────────────────────────────────────────────────────
        ("Rusya",           50.0,  27.0,  77.0, 180.0),

        # ── Güney Asya ────────────────────────────────────────────────────────
        ("Güney Asya",       8.0,  60.0,  38.0,  90.0),

        # ── Çin / Tayvan ──────────────────────────────────────────────────────
        ("Çin/Tayvan",      18.0,  98.0,  53.0, 123.0),

        # ── Kore ──────────────────────────────────────────────────────────────
        ("Kore",            33.0, 124.0,  44.0, 132.0),

        # ── Japonya / Pasifik ─────────────────────────────────────────────────
        ("Japonya/Pasifik", 24.0, 123.0,  46.0, 146.0),

        # ── Afrika ────────────────────────────────────────────────────────────
        ("Afrika",         -35.0, -20.0,  37.0,  52.0),

        # ── ABD / Kuzey Amerika ───────────────────────────────────────────────
        ("ABD",             25.0,-130.0,  50.0, -65.0),

        # ── Orta Asya ─────────────────────────────────────────────────────────
        ("Orta Asya",       35.0,  46.0,  55.0,  80.0),
    ]
    for name, lat_min, lon_min, lat_max, lon_max in boxes:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return "Global"


def _alert_title(risk_level: str, entity_type: str) -> str:
    titles = {
        "Kritik": f"KRİTİK — Olağandışı {entity_type} hareketi",
        "Yüksek": f"Yüksek risk — {entity_type.capitalize()} anomalisi",
        "Orta": f"Anomali tespit — {entity_type.capitalize()}",
    }
    return titles.get(risk_level, f"Bilgi — {entity_type.capitalize()} izleme")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
