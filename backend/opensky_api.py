"""
OpenSky ADS-B API
Gerçek uçak verisi sunan backend API
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import uvicorn
import logging
import asyncio

# OpenSky collector'ı import et
from opensky_collector import collector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tulpar OpenSky API", version="1.0.0")

# CORS - frontend bağlantısı için (tüm portlar ve browser preview)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:10845",
        "http://localhost:3000",
        "*"  # Fallback - tüm originlere izin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/aircraft")
async def get_aircraft():
    """Gerçek OpenSky uçak verisi - cache'li"""
    try:
        aircraft_list = collector.fetch_aircraft()
        
        return JSONResponse({
            'success': True,
            'count': len(aircraft_list),
            'data': aircraft_list,
            'source': 'opensky',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ API hatası: {str(e)}")
        return JSONResponse({
            'success': False,
            'error': str(e),
            'data': [],
            'timestamp': datetime.now().isoformat()
        }, status_code=500)

@app.get("/api/aircraft/live-count")
async def get_live_count():
    """Canlı uçak sayısı ve cache durumu"""
    aircraft = collector.fetch_aircraft()
    cache_info = "fresh"
    
    if 'aircraft' in collector.cache:
        cache_age = datetime.now().timestamp() - collector.cache['aircraft']['timestamp']
        if cache_age > collector.cache_ttl:
            cache_info = f"stale ({cache_age:.0f}s)"
        else:
            cache_info = f"fresh ({cache_age:.0f}s ago)"
    
    return JSONResponse({
        'count': len(aircraft),
        'cache_status': cache_info,
        'timestamp': datetime.now().isoformat()
    })

@app.get("/api/vessels")
async def get_vessels():
    """Gemi verisi - mock AIS data"""
    vessels = [
        {
            'id': 'VESSEL001',
            'name': 'MV KEMAL KÖPRÜSÜ',
            'mmsi': '271000123',
            'lat': 40.8,
            'lon': 29.2,
            'speed': 15.5,
            'heading': 135,
            'timestamp': datetime.now().isoformat(),
            'vessel_type': 'cargo',
            'anomaly_score': 0,
            'risk_level': 'Normal',
            'anomaly_reason': 'Normal seyir'
        },
        {
            'id': 'VESSEL002',
            'name': 'TCG GELİBOLU',
            'mmsi': '271045678',
            'lat': 39.5,
            'lon': 26.2,
            'speed': 22.0,
            'heading': 45,
            'timestamp': datetime.now().isoformat(),
            'vessel_type': 'military',
            'anomaly_score': 0,
            'risk_level': 'Normal',
            'anomaly_reason': 'Askeri devriye'
        }
    ]
    return JSONResponse({
        'success': True,
        'count': len(vessels),
        'data': vessels,
        'timestamp': datetime.now().isoformat()
    })

@app.get("/api/strategic-zones")
async def get_strategic_zones():
    """Stratejik bölgeler"""
    zones = [
        {
            'id': 'ZONE001',
            'name': 'İstanbul Boğazı',
            'type': 'maritime_chokepoint',
            'coordinates': [[41.2, 28.9], [41.3, 29.1]],
            'risk_level': 'Yüksek'
        },
        {
            'id': 'ZONE002',
            'name': 'Çanakkale Boğazı',
            'type': 'maritime_chokepoint',
            'coordinates': [[40.2, 26.4], [40.3, 26.5]],
            'risk_level': 'Yüksek'
        },
        {
            'id': 'ZONE003',
            'name': 'Ege FIR Bölgesi',
            'type': 'airspace',
            'coordinates': [[37.0, 26.0], [40.0, 28.0]],
            'risk_level': 'Orta'
        }
    ]
    return JSONResponse({
        'success': True,
        'count': len(zones),
        'data': zones,
        'timestamp': datetime.now().isoformat()
    })

@app.websocket("/ws/sitrep")
async def sitrep_ws(websocket: WebSocket):
    """WebSocket sitrep bağlantısı"""
    await websocket.accept()
    logger.info("🔌 WebSocket bağlantısı kabul edildi")
    try:
        while True:
            await websocket.send_json({
                "type": "heartbeat",
                "status": "live",
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(1)
    except Exception as e:
        logger.info(f"🔌 WebSocket bağlantısı kapandı: {e}")

@app.get("/health")
async def health_check():
    """Sağlık kontrolü"""
    return JSONResponse({
        'status': 'ok',
        'service': 'opensky-api',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == "__main__":
    logger.info("🚀 OpenSky API başlatılıyor...")
    logger.info("🛰️ Gerçek uçak verisi için OpenSky bağlantısı hazır")
    logger.info("📡 Port 8000 - WebSocket aktif")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
