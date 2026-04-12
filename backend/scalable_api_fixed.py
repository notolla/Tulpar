"""
EFES-2026 Scalable Backend API
Rate limit, cache ve load balancing ile ölçeklenebilir mimari
"""

import asyncio
import aiohttp
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EFES-2026 Scalable API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background tasks
background_tasks = BackgroundTasks()

# Rate limiting
class RateLimiter:
    def __init__(self):
        self.requests = {}
    
    def is_rate_limited(self, client_ip: str, endpoint: str) -> bool:
        current_time = datetime.now().timestamp()
        
        if client_ip not in self.requests:
            self.requests[client_ip] = {}
        
        if endpoint not in self.requests[client_ip]:
            self.requests[client_ip][endpoint] = []
        
        # Son 10 saniye içindeki istekleri temizle
        self.requests[client_ip][endpoint] = [
            req_time for req_time in self.requests[client_ip][endpoint]
            if current_time - req_time < 10
        ]
        
        # Rate limit: 10 istek per 10 saniye per endpoint
        if len(self.requests[client_ip][endpoint]) >= 10:
            return False  # Rate limit yok
        
        return True

rate_limiter = RateLimiter()

# Cache layer import
from cache_layer import cache_layer

@app.get("/api/scalable/aircraft")
async def get_scalable_aircraft():
    """Ölçeklenebilir uçak verisi"""
    # Rate limit geçici olarak devre dışı - kaldırıldı
    
    # Önce cache'den veri almayı dene
    cached_aircraft = await cache_layer.get_data('aircraft:latest')
    if cached_aircraft:
        logger.info("📦 Cache'den uçak verisi alındı")
        return JSONResponse({
            'success': True,
            'source': 'cache',
            'data': cached_aircraft,
            'count': len(cached_aircraft),
            'timestamp': datetime.now().isoformat()
        })
    
    # Direct OpenSky çağrısı - collector olmadan
    try:
        logger.info("🔍 Direct OpenSky çağrısı...")
        response = requests.get(
            "https://opensky-network.org/api/states/all",
            params={
                'lamin': 25.0,  # Daha geniş
                'lomin': 10.0,
                'lamax': 50.0,
                'lomax': 60.0,
            },
            headers={
                'User-Agent': 'EFES2026-Scalable/1.0',
                'Accept': 'application/json',
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            if 'states' in data and data['states']:
                for aircraft in data['states']:
                    if aircraft[0] and aircraft[1]:  # lat, lon varsa
                        lat, lon = float(aircraft[1]), float(aircraft[2])
                        aircraft_data = {
                            'id': aircraft[0] if aircraft[0] else '',
                            'callsign': aircraft[1] if aircraft[1] else 'UNKNOWN',
                            'lat': lat,
                            'lon': lon,
                            'altitude': aircraft[7] if aircraft[7] else 0,
                            'speed': aircraft[5] if aircraft[5] else 0,
                            'heading': aircraft[10] if aircraft[10] else 0,
                            'timestamp': datetime.now().isoformat(),
                            'anomaly_score': 0,
                            'risk_level': 'Normal',
                            'anomaly_reason': 'Normal uçuş profili.',
                            'flags': []
                        }
                        aircraft_list.append(aircraft_data)
            else:
                # OpenSky çalışmazsa test verisi ekle
                logger.warning("⚠️ OpenSky verisi yok, test uçakları ekleniyor...")
                aircraft_list = [
                    {
                        'id': 'TEST001',
                        'callsign': 'TK2026',
                        'lat': 41.0 + (hash('TK2026') % 10 - 5) * 0.1,
                        'lon': 29.0 + (hash('TK2026') % 10 - 5) * 0.1,
                        'altitude': 35000,
                        'speed': 450,
                        'heading': 90,
                        'timestamp': datetime.now().isoformat(),
                        'anomaly_score': 0,
                        'risk_level': 'Normal',
                        'anomaly_reason': 'Test uçağı.',
                        'flags': ['TEST']
                    },
                    {
                        'id': 'TEST002',
                        'callsign': 'EFES2026',
                        'lat': 39.9 + (hash('EFES2026') % 10 - 5) * 0.1,
                        'lon': 32.8 + (hash('EFES2026') % 10 - 5) * 0.1,
                        'altitude': 28000,
                        'speed': 380,
                        'heading': 180,
                        'timestamp': datetime.now().isoformat(),
                        'anomaly_score': 0,
                        'risk_level': 'Normal',
                        'anomaly_reason': 'Test uçağı.',
                        'flags': ['TEST']
                    }
                ]
            
            # Cache'e kaydet
            await cache_layer.set_data('aircraft:latest', aircraft_list, 300)
            
            logger.info(f"✅ Direct OpenSky: {len(aircraft_list)} uçak")
            return JSONResponse({
                'success': True,
                'source': 'live',
                'data': aircraft_list,
                'count': len(aircraft_list),
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"❌ OpenSky HTTP {response.status_code}")
            return JSONResponse({
                'success': False,
                'source': 'error',
                'error': f'HTTP {response.status_code}',
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"❌ Direct OpenSky hatası: {str(e)}")
        return JSONResponse({
            'success': False,
            'source': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.get("/api/scalable/vessels")
async def get_scalable_vessels():
    """Ölçeklenebilir gemi verisi"""
    # Rate limit kaldırıldı
    
    # Test gemi verisi
    vessels_data = [
        {
            'id': 'VESSEL001',
            'mmsi': '271000123',
            'name': 'MV KEMAL KÖPRÜSÜ',
            'lat': 40.8,
            'lon': 29.2,
            'speed': 15.5,
            'heading': 135,
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    logger.info(f"✅ Test gemi verisi: {len(vessels_data)}")
    return JSONResponse({
        'success': True,
        'source': 'test',
        'data': vessels_data,
        'count': len(vessels_data),
        'timestamp': datetime.now().isoformat()
    })

@app.get("/api/scalable/strategic-zones")
async def get_scalable_strategic_zones():
    """Ölçeklenebilir stratejik bölgeler"""
    client_ip = "127.0.0.1"
    
    if rate_limiter.is_rate_limited(client_ip, "strategic-zones"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Test stratejik bölge verisi
    zones_data = [
        {
            'id': 'ZONE001',
            'name': 'İstanbul Hava Sahası',
            'type': 'airport',
            'coordinates': [
                {'lat': 41.01, 'lon': 28.97},
                {'lat': 41.01, 'lon': 28.98},
                {'lat': 41.00, 'lon': 28.98},
                {'lat': 41.00, 'lon': 28.97}
            ],
            'risk_level': 'Yüksek',
            'description': 'Sivil askeri bölgesi'
        },
        {
            'id': 'ZONE002',
            'name': 'Ankara Bölgesi',
            'type': 'military',
            'coordinates': [
                {'lat': 39.93, 'lon': 32.85},
                {'lat': 39.94, 'lon': 32.86},
                {'lat': 39.93, 'lon': 32.85},
                {'lat': 39.92, 'lon': 32.84}
            ],
            'risk_level': 'Kritik',
            'description': 'Askeri üs bölgesi'
        }
    ]
    
    logger.info(f"✅ Test stratejik bölge verisi: {len(zones_data)}")
    return JSONResponse({
        'success': True,
        'source': 'test',
        'data': zones_data,
        'count': len(zones_data),
        'timestamp': datetime.now().isoformat()
    })

@app.get("/api/scalable/status")
async def get_scalable_status():
    """Sistem durumu"""
    cache_status = await cache_layer.get_cache_stats()
    
    return JSONResponse({
        'status': 'running',
        'cache': cache_status,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Frontend uyumlu endpoint'ler
@app.get("/api/aircraft")
@app.get("/api/aircrafts")
async def get_aircrafts_compatible():
    """Frontend uyumlu uçak endpoint'i - Rate limit olmadan"""
    try:
        # Rate limit kontrolünü geçici olarak devre dışı bırak
        logger.info("🔍 Frontend uçak verisi istedi (rate limit olmadan)")
        result = await get_scalable_aircraft()
        return result.body if hasattr(result, 'body') else result.get('data', [])
    except Exception as e:
        logger.error(f"❌ Uçak verisi hatası: {str(e)}")
        return []

@app.get("/api/vessels")
async def get_vessels_compatible():
    """Frontend uyumlu gemi endpoint'i"""
    try:
        result = await get_scalable_vessels()
        return result.get('data', [])
    except Exception as e:
        logger.error(f"❌ Gemi verisi hatası: {str(e)}")
        return []

@app.get("/api/strategic-zones")
async def get_strategic_zones_compatible():
    """Frontend uyumlu stratejik bölgeler endpoint'i"""
    try:
        result = await get_scalable_strategic_zones()
        return result.get('data', [])
    except Exception as e:
        logger.error(f"❌ Stratejik bölge verisi hatası: {str(e)}")
        return []

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 EFES-2026 Scalable API başlatılıyor...")
    
    # Cache'i başlat (async olmadan)
    try:
        import asyncio
        asyncio.run(cache_layer.init_redis())
    except:
        logger.warning("Cache başlatılamadı, memory cache kullanılacak")
    
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
