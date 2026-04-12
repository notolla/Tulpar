from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Optional
import requests
import json
import pandas as pd
import numpy as np
import asyncio
import aiohttp

app = FastAPI(title="Tulpar ADS-B API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
class Aircraft(BaseModel):
    id: str
    callsign: str
    lat: float
    lon: float
    altitude: int
    speed: float
    heading: int
    timestamp: str
    aircraft_type: str
    anomaly_score: int
    risk_level: str
    anomaly_reason: str
    flags: List[str]
    route: List[Dict]

class Vessel(BaseModel):
    id: str
    name: str
    mmsi: str
    lat: float
    lon: float
    speed: float
    heading: int
    timestamp: str
    vessel_type: str
    anomaly_score: int
    risk_level: str
    anomaly_reason: str
    flags: List[str]
    route: List[Dict]

class Alert(BaseModel):
    id: str
    type: str
    entity_id: str
    entity_name: str
    title: str
    description: str
    risk_level: str
    timestamp: str
    coordinates: Dict
    category: str

# SUNUCU TARAFI ADS-B ALICI - IP BAN ÖNLEMLİ
import asyncio
import aiohttp

async def server_side_adsb_receiver():
    """Sunucu tarafında ADS-B verisi al - IP ban önlemli"""
    try:
        print("🛰️ Sunucu tarafında ADS-B verisi alınıyor...")
        
        # Sadece OpenSky - en az banlı
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://opensky-network.org/api/states/all",
                params={
                    'lamin': MIDDLE_EAST_BOUNDS["min_lat"],
                    'lomin': MIDDLE_EAST_BOUNDS["min_lon"],
                    'lamax': MIDDLE_EAST_BOUNDS["max_lat"],
                    'lomax': MIDDLE_EAST_BOUNDS["max_lon"],
                },
                headers={'User-Agent': 'TULPAR-EFES2026/1.0'},
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    aircraft_list = []
                    if 'states' in data:
                        for aircraft in data['states']:
                            if aircraft[0] and aircraft[1]:  # lat, lon varsa
                                lat, lon = float(aircraft[1]), float(aircraft[2])
                                if is_in_middle_east(lat, lon):
                                    aircraft_data = {
                                        "icao24": aircraft[0] if aircraft[0] else '',
                                        "callsign": aircraft[1] if aircraft[1] else 'UNKNOWN',
                                        "lat": lat,
                                        "lon": lon,
                                        "altitude": aircraft[7] if aircraft[7] else 0,
                                        "velocity": aircraft[5] if aircraft[5] else 0,
                                        "true_track": aircraft[10] if aircraft[10] else 0,
                                        "vertical_rate": aircraft[11] if aircraft[11] else 0,
                                        "squawk": str(aircraft[14]) if aircraft[14] else '0000',
                                        "category": 'A1',
                                        "timestamp": datetime.now().isoformat(),
                                        "hex": aircraft[0] if aircraft[0] else '',
                                        "gs": aircraft[5] if aircraft[5] else 0,
                                        "track": aircraft[10] if aircraft[10] else 0,
                                        "baro_rate": aircraft[11] if aircraft[11] else 0,
                                        "flight": aircraft[1] if aircraft[1] else '',
                                        "mach": 0,
                                        "messages": 0,
                                        "seen": 0,
                                        "rssi": 0,
                                    }
                                    aircraft_list.append(aircraft_data)
                    
                    print(f"✅ OpenSky: {len(aircraft_list)} uçak Türkiye'de")
                    return aircraft_list
                else:
                    print(f"❌ OpenSky HTTP {response.status}")
                    return []
        
        print(f"🛰️ Sunucu tarafında {len(aircraft_list)} uçak alındı")
        return aircraft_list
        
    except Exception as e:
        print(f"❌ Sunucu ADS-B alıcı hatası: {str(e)}")
        return []

# ADS-B Data Sources - ALTERNATİF KAYNAKLAR
ADSB_API_URLS = [
    "https://api.adsb.one/v2/state/",  # ADSB.one - genellikle çalışır
    "https://globe.adsbexchange.com/globe.json",  # ADS-B Exchange - bazen engeller
    "https://opensky-network.org/api/states/all",  # OpenSky Network - rate limit
    "https://api.adsb.fi/v1/aircraft/json",  # ADSB.fi - Finlandiya
    "https://public-api.adsbexchange.com/v1/aircraft.json",  # ADS-B Exchange public
    "https://data.radarbox.com/v1/aircraft",  # RadarBox - alternatif
    "https://api.flightaware.com/flightmap/data.json",  # FlightAware - alternatif
]

# Ortadoğu ve Türkiye, komşuları ve sıcak savaş bölgesi koordinatları
MIDDLE_EAST_BOUNDS = {
    "min_lat": 30.0,   # Güney sınır - Körfez, Yemen
    "max_lat": 45.0,   # Kuzey sınır - Ukrayna, Rusya
    "min_lon": 20.0,   # Batı sınır - Yunanistan, İtalya
    "max_lon": 55.0    # Doğu sınır - İran, Afganistan
}

def is_in_middle_east(lat: float, lon: float) -> bool:
    """Check if coordinates are in Turkey, neighbors, and conflict zones"""
    return (MIDDLE_EAST_BOUNDS["min_lat"] <= lat <= MIDDLE_EAST_BOUNDS["max_lat"] and 
            MIDDLE_EAST_BOUNDS["min_lon"] <= lon <= MIDDLE_EAST_BOUNDS["max_lon"])

def calculate_advanced_anomaly_score(aircraft_data: Dict) -> int:
    """Gelişmiş anomali skoru - real ADS-B verisi için"""
    score = 0
    reasons = []
    
    # 1. Hız Anomalisi (20 puan)
    speed = aircraft_data.get("velocity", 0) or aircraft_data.get("gs", 0) or 0
    if speed > 600:  # Süpersonik
        score += 20
        reasons.append("Süpersonik hız")
    elif speed < 100 and speed > 0:  # Çok yavaş
        score += 15
        reasons.append("Tehlikeli düşük hız")
    elif speed > 550:  # Savaş uçağı hızında
        score += 10
        reasons.append("Askeri uçak hızında")
    
    # 2. İrtifa Anomalisi (25 puan)
    alt = aircraft_data.get("altitude", 0) or aircraft_data.get("alt_baro", 0) or 0
    if alt > 45000:  # Servis irtifası üstü
        score += 25
        reasons.append("Servis irtifası aşımı")
    elif alt < 1000 and alt > 0:  # Çok alçak
        score += 20
        reasons.append("Tehlikeli alçak irtifa")
    elif alt > 40000:  # Yüksek irtifa
        score += 10
        reasons.append("Yüksek irtifa uçuşu")
    
    # 3. Dikey Hız Anomalisi (15 puan)
    vs = aircraft_data.get("vertical_rate", 0) or aircraft_data.get("baro_rate", 0) or 0
    if abs(vs) > 5000:  # Aşırı dikey hız
        score += 15
        reasons.append("Aşırı dikey hız")
    elif abs(vs) > 3000:  # Yüksek dikey hız
        score += 8
        reasons.append("Yüksek dikey hız")
    
    # 4. Rota Anomalisi (10 puan)
    heading = aircraft_data.get("true_track", 0) or aircraft_data.get("track", 0) or 0
    if heading < 0 or heading > 360:
        score += 10
        reasons.append("Geçersiz yön bilgisi")
    
    # 5. Squawk Kodu Anomalisi (15 puan)
    squawk = aircraft_data.get("squawk", "")
    if squawk:
        if squawk in ["7500", "7600", "7700"]:  # Hijack, comms failure, emergency
            score += 25
            reasons.append(f"Acil durum kodu: {squawk}")
        elif squawk in ["0000", "7777"]:  # Invalid/test codes
            score += 15
            reasons.append(f"Geçersiz squawk: {squawk}")
    
    # 6. Uçak Türü Anomalisi (10 puan)
    category = aircraft_data.get("category", "")
    if category:
        # A1 = Light, A2 = Small, A3 = Medium, A4 = Large, A5 = Heavy, A6 = High Vortex
        # B1 = Glider, B2 = Lighter-than-air, B3 = Parachutist, B4 = Ultralight, B5 = Space
        # C1 = Gyrocopter, C2 = Towplane, C3 = Rotorcraft
        # D1 = Ground vehicle, D2 = Surface ship
        if category == "A5":  # Heavy aircraft
            score += 5
            reasons.append("Ağır uçak")
        elif category in ["B1", "B2", "B3", "B4", "B5"]:  # Special aircraft
            score += 10
            reasons.append("Özel uçak türü")
        elif category in ["D1", "D2"]:  # Ground/sea vehicles
            score += 15
            reasons.append("Hava aracı değil")
    
    # 7. Callsign Anomalisi (10 puan)
    callsign = aircraft_data.get("callsign", "")
    if not callsign or len(callsign) < 3:
        score += 10
        reasons.append("Geçersiz çağrı kodu")
    elif callsign.startswith("TURAF") or callsign.startswith("THY"):
        score -= 5  # Türk hava yolları - daha düşük risk
    
    # 8. Konum Anomalisi (5 puan)
    lat, lon = aircraft_data.get("lat", 0), aircraft_data.get("lon", 0)
    if lat and lon and not is_in_middle_east(float(lat), float(lon)):
        score += 5
        reasons.append("Ortadoğu bölgesi dışında")
    
    # 9. Sinyal Kalitesi (10 puan)
    rssi = aircraft_data.get("rssi", 0)
    if rssi < -30:  # Zayıf sinyal
        score += 8
        reasons.append("Zayıf sinyal kalitesi")
    
    seen = aircraft_data.get("seen", 0)
    if seen > 60:  # 60 saniyeden uzun süredir görülmedi
        score += 12
        reasons.append("Uzun süredir sinyal alınamıyor")
    
    # 10. Mach Sayısı Anomalisi (10 puan)
    mach = aircraft_data.get("mach", 0)
    if mach > 0.8:  # Transonik ve üstü
        score += 10
        reasons.append("Yüksek mach sayısı")
    elif mach > 1.0:  # Süpersonik
        score += 15
        reasons.append("Süpersonik uçuş")
    
    return min(score, 100)

def get_detailed_risk_level(score: int, aircraft_data: Dict) -> tuple[str, str]:
    """Detaylı risk seviyesi ve açıklama"""
    if score >= 80:
        return "Kritik", "Acil müdahale gerektiren yüksek tehdit"
    elif score >= 60:
        return "Yüksek", "Yakından izlenmesi gereken şüpheli aktivite"
    elif score >= 40:
        return "Orta", "Gözlem altında tutulması gereken davranış"
    elif score >= 20:
        return "Düşük", "Minör anomali, standart takip"
    else:
        return "Normal", "Beklenen uçuş profili"

def get_anomaly_reason(score: int, aircraft_data: Dict) -> str:
    """Get anomaly reason based on score and data"""
    reasons = []
    
    if aircraft_data.get("speed", 0) > 900:
        reasons.append("Anormal yüksek hız")
    elif aircraft_data.get("speed", 0) < 100:
        reasons.append("Anormal düşük hız")
    
    alt = aircraft_data.get("altitude", 0)
    if alt > 45000:
        reasons.append("İrtifa limiti aşımı")
    elif alt < 5000:
        reasons.append("Tehlikeli alçak irtifa")
    
    heading = aircraft_data.get("heading", 0)
    if heading < 0 or heading > 360:
        reasons.append("Geçersiz yön bilgisi")
    
    callsign = aircraft_data.get("callsign", "")
    if not callsign or len(callsign) < 3:
        reasons.append("Geçersiz çağrı kodu")
    
    lat, lon = aircraft_data.get("lat", 0), aircraft_data.get("lon", 0)
    if not is_in_middle_east(lat, lon):
        reasons.append("Ortadoğu bölgesi dışında")
    
    if not reasons:
        return "Normal uçuş profili."
    
    return ", ".join(reasons) + " tespit edildi."

async def fetch_adsb_fi_data() -> List[Dict]:
    """Fetch real-time aircraft data from ADSB.fi GLOBE API"""
    try:
        print("🔍 ADSB.fi GLOBE'den GERÇEK ZAMANLI veri çekiliyor...")
        
        response = requests.get(
            "https://globe.adsb.fi/api/v1/aircraft",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'max-age=0'
            },
            timeout=25
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            # ADSB.fi GLOBE formatını parse et
            if 'aircraft' in data and data['aircraft']:
                for aircraft in data['aircraft']:
                    # Koordinat kontrolü
                    lat = aircraft.get('lat')
                    lon = aircraft.get('lon')
                    
                    if lat and lon:
                        # Türkiye bounds (geniş)
                        if (35.0 <= float(lat) <= 43.0 and 25.0 <= float(lon) <= 45.0):
                            aircraft_data = {
                                "icao24": aircraft.get('hex', ''),
                                "callsign": aircraft.get('flight', '').strip() or 'UNKNOWN',
                                "lat": float(lat),
                                "lon": float(lon),
                                "altitude": aircraft.get('alt_baro', aircraft.get('alt_geom', 0)),
                                "velocity": aircraft.get('gs', 0),
                                "true_track": aircraft.get('track', 0),
                                "vertical_rate": aircraft.get('baro_rate', 0),
                                "squawk": aircraft.get('squawk', '0000'),
                                "category": aircraft.get('category', 'A1'),
                                "timestamp": datetime.now().isoformat(),
                                # ADSB.fi specific fields
                                "alt_baro": aircraft.get('alt_baro', 0),
                                "alt_geom": aircraft.get('alt_geom', 0),
                                "gs": aircraft.get('gs', 0),
                                "track": aircraft.get('track', 0),
                                "baro_rate": aircraft.get('baro_rate', 0),
                                "flight": aircraft.get('flight', '').strip(),
                                "hex": aircraft.get('hex', ''),
                                "mach": aircraft.get('mach', 0),
                                "messages": aircraft.get('messages', 0),
                                "seen": aircraft.get('seen', 0),
                                "rssi": aircraft.get('rssi', 0),
                                "nac_p": aircraft.get('nac_p', 0),
                                "nac_v": aircraft.get('nac_v', 0),
                                "sil": aircraft.get('sil', 0),
                                "gva": aircraft.get('gva', 0),
                                "sda": aircraft.get('sda', 0),
                            }
                            aircraft_list.append(aircraft_data)
                
                print(f"📍 ADSB.fi GLOBE: {len(aircraft_list)} uçak Türkiye'de")
                return aircraft_list
            else:
                print("⚠️ ADSB.fi GLOBE beklenmedik veri formatı")
                return []
        else:
            print(f"❌ ADSB.fi GLOBE HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ ADSB.fi GLOBE bağlantı hatası: {str(e)}")
        return []

async def fetch_aviationstack_data() -> List[Dict]:
    """Fetch real-time aircraft data from AviationStack API"""
    try:
        print("🔍 AviationStack'ten GERÇEK ZAMANLI veri çekiliyor...")
        
        # AviationStack free tier - no API key required for basic data
        response = requests.get(
            "http://api.aviationstack.com/v1/flights",
            params={
                'access_key': 'YOUR_API_KEY',  # Free tier key needed
                'limit': 100,
                'dep_iata': 'IST,SAW,ESB,AYT,ADB',  # Turkish airports
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            if 'data' in data and data['data']:
                for flight in data['data']:
                    if flight.get('live'):
                        live = flight['live']
                        if live.get('latitude') and live.get('longitude'):
                            # Turkey bounds check
                            lat, lon = float(live['latitude']), float(live['longitude'])
                            if (35.0 <= lat <= 43.0 and 25.0 <= lon <= 45.0):
                                aircraft_data = {
                                    "icao24": flight.get('flight', {}).get('icao_number', ''),
                                    "callsign": flight.get('flight', {}).get('iata_number', '').strip() or 'UNKNOWN',
                                    "lat": lat,
                                    "lon": lon,
                                    "altitude": live.get('altitude', {}).get('feet', 0),
                                    "velocity": live.get('speed', {}).get('horizontal', 0),
                                    "true_track": live.get('direction', 0),
                                    "vertical_rate": live.get('speed', {}).get('vertical', 0),
                                    "squawk": live.get('squawk', '0000'),
                                    "timestamp": datetime.now().isoformat(),
                                    "flight": flight.get('flight', {}).get('iata_number', ''),
                                    "hex": flight.get('flight', {}).get('icao_number', ''),
                                }
                                aircraft_list.append(aircraft_data)
                
                print(f"📍 AviationStack: {len(aircraft_list)} uçak Türkiye'de")
                return aircraft_list
            else:
                print("⚠️ AviationStack beklenmedik veri formatı")
                return []
        else:
            print(f"❌ AviationStack HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ AviationStack bağlantı hatası: {str(e)}")
        return []

async def fetch_radarbox_data() -> List[Dict]:
    """Fetch real-time aircraft data from RadarBox API"""
    try:
        print("🔍 RadarBox'ten GERÇEK ZAMANLI veri çekiliyor...")
        
        response = requests.get(
            "https://data.radarbox.com/v1/aircraft",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            if 'aircraft' in data and data['aircraft']:
                for aircraft in data['aircraft']:
                    lat = aircraft.get('lat')
                    lon = aircraft.get('lon')
                    
                    if lat and lon and is_in_middle_east(float(lat), float(lon)):
                        aircraft_data = {
                            "icao24": aircraft.get('hex', ''),
                            "callsign": aircraft.get('flight', '').strip() or 'UNKNOWN',
                            "lat": float(lat),
                            "lon": float(lon),
                            "altitude": aircraft.get('alt', 0),
                            "velocity": aircraft.get('speed', 0),
                            "true_track": aircraft.get('heading', 0),
                            "vertical_rate": aircraft.get('v_speed', 0),
                            "squawk": aircraft.get('squawk', '0000'),
                            "category": aircraft.get('cat', 'A1'),
                            "timestamp": datetime.now().isoformat(),
                            "hex": aircraft.get('hex', ''),
                            "gs": aircraft.get('speed', 0),
                            "track": aircraft.get('heading', 0),
                            "flight": aircraft.get('flight', '').strip(),
                            "mach": aircraft.get('mach', 0),
                        }
                        aircraft_list.append(aircraft_data)
                
                print(f"📍 RadarBox: {len(aircraft_list)} uçak Türkiye'de")
                return aircraft_list
            else:
                print("⚠️ RadarBox beklenmedik veri formatı")
                return []
        else:
            print(f"❌ RadarBox HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ RadarBox bağlantı hatası: {str(e)}")
        return []

async def fetch_flightaware_data() -> List[Dict]:
    """Fetch real-time aircraft data from FlightAware API"""
    try:
        print("🔍 FlightAware'dan GERÇEK ZAMANLI veri çekiliyor...")
        
        response = requests.get(
            "https://api.flightaware.com/flightmap/data.json",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            if 'aircraft' in data and data['aircraft']:
                for aircraft in data['aircraft']:
                    lat = aircraft.get('lat')
                    lon = aircraft.get('lon')
                    
                    if lat and lon and is_in_middle_east(float(lat), float(lon)):
                        aircraft_data = {
                            "icao24": aircraft.get('hex', ''),
                            "callsign": aircraft.get('flight', '').strip() or 'UNKNOWN',
                            "lat": float(lat),
                            "lon": float(lon),
                            "altitude": aircraft.get('altitude', 0),
                            "velocity": aircraft.get('speed', 0),
                            "true_track": aircraft.get('heading', 0),
                            "vertical_rate": aircraft.get('v_speed', 0),
                            "squawk": aircraft.get('squawk', '0000'),
                            "category": aircraft.get('cat', 'A1'),
                            "timestamp": datetime.now().isoformat(),
                            "hex": aircraft.get('hex', ''),
                            "gs": aircraft.get('speed', 0),
                            "track": aircraft.get('heading', 0),
                            "flight": aircraft.get('flight', '').strip(),
                            "mach": aircraft.get('mach', 0),
                        }
                        aircraft_list.append(aircraft_data)
                
                print(f"📍 FlightAware: {len(aircraft_list)} uçak Türkiye'de")
                return aircraft_list
            else:
                print("⚠️ FlightAware beklenmedik veri formatı")
                return []
        else:
            print(f"❌ FlightAware HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ FlightAware bağlantı hatası: {str(e)}")
        return []

async def fetch_adsb_one_data() -> List[Dict]:
    """Fetch real-time aircraft data from ADSB.one - ALTERNATIVE ENDPOINT"""
    try:
        print("🔍 ADSB.one ALTERNATIVE'den GERÇEK ZAMANLI veri çekiliyor...")
        
        # Farklı endpoint deneyelim
        response = requests.get(
            "https://api.adsb.one/v2/aircraft/",
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            # Global veriyi işle
            if isinstance(data, list):
                for aircraft in data:
                    lat = aircraft.get('lat')
                    lon = aircraft.get('lon')
                    
                    if lat and lon and is_in_middle_east(float(lat), float(lon)):
                        aircraft_data = {
                            "icao24": aircraft.get('hex', ''),
                            "callsign": aircraft.get('call', '') or aircraft.get('flight', '') or 'UNKNOWN',
                            "lat": float(lat),
                            "lon": float(lon),
                            "altitude": aircraft.get('alt_geom', aircraft.get('alt', 0)),
                            "velocity": aircraft.get('gs', 0),
                            "true_track": aircraft.get('track', 0),
                            "vertical_rate": aircraft.get('baro_rate', 0),
                            "squawk": aircraft.get('squawk', '0000'),
                            "category": aircraft.get('category', 'A1'),
                            "timestamp": datetime.now().isoformat(),
                            "altitude_geom": aircraft.get('alt_geom', 0),
                            "gs": aircraft.get('gs', 0),
                            "track": aircraft.get('track', 0),
                            "baro_rate": aircraft.get('baro_rate', 0),
                            "flight": aircraft.get('call', '') or aircraft.get('flight', ''),
                            "hex": aircraft.get('hex', ''),
                            "mach": aircraft.get('mach', 0),
                            "messages": aircraft.get('messages', 0),
                            "seen": aircraft.get('seen', 0),
                            "rssi": aircraft.get('rssi', 0),
                        }
                        aircraft_list.append(aircraft_data)
                
                print(f"📍 ADSB.one ALTERNATIVE: {len(aircraft_list)} uçak Ortadoğu'da")
                return aircraft_list
            else:
                print("⚠️ ADSB.one ALTERNATIVE beklenmedik veri formatı")
                return []
        else:
            print(f"❌ ADSB.one ALTERNATIVE HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ ADSB.one ALTERNATIVE bağlantı hatası: {str(e)}")
        return []

async def fetch_adsb_exchange_data() -> List[Dict]:
    """Fetch real-time aircraft data from ADS-B Exchange"""
    try:
        print("🔍 ADS-B Exchange'den GERÇEK ZAMANLI veri çekiliyor...")
        
        response = requests.get(
            "https://globe.adsbexchange.com/globe.json",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://globe.adsbexchange.com/',
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            # ADS-B Exchange formatını parse et
            if 'ac' in data and data['ac']:
                for aircraft in data['ac']:
                    # Koordinat kontrolü
                    lat = aircraft.get('lat')
                    lon = aircraft.get('lon')
                    
                    if lat and lon and is_in_middle_east(float(lat), float(lon)):
                        # REAL ADS-B Exchange veri formatı
                        aircraft_data = {
                            "icao24": aircraft.get('hex', ''),
                            "callsign": aircraft.get('call', '') or aircraft.get('flight', '') or 'UNKNOWN',
                            "lat": float(lat),
                            "lon": float(lon),
                            "altitude": aircraft.get('alt_baro', aircraft.get('alt', 0)),
                            "velocity": aircraft.get('gs', 0),  # ground speed
                            "true_track": aircraft.get('track', 0),
                            "vertical_rate": aircraft.get('baro_rate', 0),
                            "squawk": aircraft.get('squawk', ''),
                            "category": aircraft.get('type', ''),
                            "timestamp": datetime.now().isoformat(),
                            # ADS-B Exchange özel alanlar
                            "altitude_geom": aircraft.get('alt_geom', 0),
                            "gs": aircraft.get('gs', 0),
                            "ias": aircraft.get('ias', 0),
                            "tas": aircraft.get('tas', 0),
                            "mach": aircraft.get('mach', 0),
                            "wd": aircraft.get('wd', 0),  # wind direction
                            "ws": aircraft.get('ws', 0),  # wind speed
                            "oat": aircraft.get('oat', 0),  # outside air temperature
                            "tat": aircraft.get('tat', 0),  # total air temperature
                            "flight": aircraft.get('flight', ''),
                            "reg": aircraft.get('reg', ''),  # registration
                            "dbflag": aircraft.get('dbFlags', 0),
                            "mlat": aircraft.get('mlat', []),
                            "tisb": aircraft.get('tisb', []),
                            "messages": aircraft.get('messages', 0),
                            "seen": aircraft.get('seen', 0),
                            "rssi": aircraft.get('rssi', 0),
                        }
                        
                        aircraft_list.append(aircraft_data)
            
            print(f"✅ ADS-B Exchange: {len(aircraft_list)} Ortadoğu uçağı (GERÇEK ZAMANLI) bulundu")
            return aircraft_list
        
    except Exception as e:
        print(f"❌ ADS-B Exchange API error: {e}")
    
    return []

async def fetch_opensky_data() -> List[Dict]:
    """Fetch real-time ADS-B data from OpenSky Network (backup)"""
    try:
        print("🔍 OpenSky Network'ten GERÇEK ZAMANLI veri çekiliyor...")
        
        # Bölge kısıtlaması olmadan tüm dünyadan gerçek zamanlı veri çek
        response = requests.get(
            "https://opensky-network.org/api/states/all",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            aircraft_list = []
            
            if data.get("states"):
                for state in data["states"]:
                    if len(state) >= 17:
                        aircraft = {
                            "icao24": state[0],
                            "callsign": state[1] or "UNKNOWN",
                            "origin_country": state[2],
                            "time_position": state[3],
                            "last_contact": state[4],
                            "lon": state[5],
                            "lat": state[6],
                            "baro_altitude": state[7],
                            "on_ground": state[8],
                            "velocity": state[9],
                            "true_track": state[10],
                            "vertical_rate": state[11],
                            "sensors": state[12],
                            "geo_altitude": state[13],
                            "squawk": state[14],
                            "spi": state[15],
                            "position_source": state[16]
                        }
                        
                        # Sadece Ortadoğu bölgesindeki geçerli koordinatları olan uçakları ekle
                        if aircraft["lat"] and aircraft["lon"] and is_in_middle_east(aircraft["lat"], aircraft["lon"]):
                            aircraft_list.append(aircraft)
            
            print(f"✅ OpenSky: {len(aircraft_list)} Ortadoğu uçağı (GERÇEK ZAMANLI) bulundu")
            return aircraft_list
        
    except Exception as e:
        print(f"❌ OpenSky API error: {e}")
    
    return []

def convert_to_aircraft_model(raw_data: List[Dict]) -> List[Aircraft]:
    """Convert raw ADS-B Exchange data to Aircraft model"""
    aircraft_list = []
    
    for i, aircraft in enumerate(raw_data):
        # Gelişmiş anomali skoru hesapla
        anomaly_score = calculate_advanced_anomaly_score(aircraft)
        risk_level, risk_description = get_detailed_risk_level(anomaly_score, aircraft)
        
        # Generate flags based on anomalies
        flags = []
        if aircraft.get("squawk") in ["7500", "7600", "7700"]:
            flags.append("acil_durum_kodu")
        if aircraft.get("velocity", 0) > 600:
            flags.append("supersonik")
        if aircraft.get("altitude", 0) > 45000:
            flags.append("irtifa_asimi")
        if aircraft.get("seen", 0) > 60:
            flags.append("sinyal_kaybi")
        if aircraft.get("category") in ["B1", "B2", "B3", "B4", "B5"]:
            flags.append("ozel_ucak")
        
        # Create route data (current position snapshot)
        route = [
            {"lat": aircraft["lat"], "lon": aircraft["lon"], "timestamp": aircraft.get("timestamp", datetime.now().isoformat())}
        ]
        
        # Aircraft model with real ADS-B Exchange data
        aircraft_model = Aircraft(
            id=aircraft.get("icao24", f"AC{i:04d}"),
            callsign=aircraft.get("callsign", "UNKNOWN"),
            lat=aircraft["lat"],
            lon=aircraft["lon"],
            altitude=aircraft.get("altitude", 0),
            speed=aircraft.get("velocity", 0) or aircraft.get("gs", 0),
            heading=int(aircraft.get("true_track", 0) or aircraft.get("track", 0) or 0),  # Float'ı int'e çevir
            timestamp=aircraft.get("timestamp", datetime.now().isoformat()),
            aircraft_type=aircraft.get("category", "Unknown"),
            anomaly_score=anomaly_score,
            risk_level=risk_level,
            anomaly_reason=get_detailed_anomaly_reason(aircraft, anomaly_score),
            flags=flags,
            route=route
        )
        
        aircraft_list.append(aircraft_model)
    
    return aircraft_list

def get_detailed_anomaly_reason(aircraft_data: Dict, score: int) -> str:
    """Detaylı anomali nedeni oluştur"""
    reasons = []
    
    speed = aircraft_data.get("velocity", 0) or aircraft_data.get("gs", 0) or 0
    alt = aircraft_data.get("altitude", 0) or aircraft_data.get("alt_baro", 0) or 0
    vs = aircraft_data.get("vertical_rate", 0) or aircraft_data.get("baro_rate", 0) or 0
    squawk = aircraft_data.get("squawk", "")
    category = aircraft_data.get("category", "")
    mach = aircraft_data.get("mach", 0)
    seen = aircraft_data.get("seen", 0)
    
    if speed > 600:
        reasons.append("Süpersonik hız")
    elif speed < 100 and speed > 0:
        reasons.append("Tehlikeli düşük hız")
    elif speed > 550:
        reasons.append("Askeri uçak hızında")
    
    if alt > 45000:
        reasons.append("Servis irtifası aşımı")
    elif alt < 1000 and alt > 0:
        reasons.append("Tehlikeli alçak irtifa")
    elif alt > 40000:
        reasons.append("Yüksek irtifa uçuşu")
    
    if abs(vs) > 5000:
        reasons.append("Aşırı dikey hız")
    elif abs(vs) > 3000:
        reasons.append("Yüksek dikey hız")
    
    if squawk in ["7500", "7600", "7700"]:
        reasons.append(f"Acil durum kodu: {squawk}")
    elif squawk in ["0000", "7777"]:
        reasons.append(f"Geçersiz squawk: {squawk}")
    
    if category in ["B1", "B2", "B3", "B4", "B5"]:
        reasons.append("Özel uçak türü")
    elif category in ["D1", "D2"]:
        reasons.append("Hava aracı değil")
    elif category == "A5":
        reasons.append("Ağır uçak")
    
    if mach > 1.0:
        reasons.append("Süpersonik uçuş")
    elif mach > 0.8:
        reasons.append("Yüksek mach sayısı")
    
    if seen > 60:
        reasons.append("Uzun süredir sinyal alınamıyor")
    
    if not reasons:
        return "Normal uçuş profili."
    
    return ", ".join(reasons) + " tespit edildi."

@app.get("/api/aircrafts")
async def get_aircrafts():
    """Get real-time aircraft data - ADSB.one (primary) + ADS-B Exchange + OpenSky (backup)"""
    try:
        print("🚀 GERÇEK ADS-B VERİSİ ÇEKİLİYOR...")
        
        # 1. Önce basit HTTP ile OpenSky dene (rate limit önlemli)
        try:
            print("🔍 OpenSky deneniyor (rate limit önlemli)...")
            response = requests.get(
                "https://opensky-network.org/api/states/all",
                params={
                    'lamin': MIDDLE_EAST_BOUNDS["min_lat"],
                    'lomin': MIDDLE_EAST_BOUNDS["min_lon"],
                    'lamax': MIDDLE_EAST_BOUNDS["max_lat"],
                    'lomax': MIDDLE_EAST_BOUNDS["max_lon"],
                },
                headers={
                    'User-Agent': 'TULPAR-EFES2026/1.0',
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate',
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                aircraft_list = []
                if 'states' in data:
                    for aircraft in data['states']:
                        if aircraft[0] and aircraft[1]:  # lat, lon varsa
                            lat, lon = float(aircraft[1]), float(aircraft[2])
                            if is_in_middle_east(lat, lon):
                                aircraft_data = {
                                    "icao24": aircraft[0] if aircraft[0] else '',
                                    "callsign": aircraft[1] if aircraft[1] else 'UNKNOWN',
                                    "lat": lat,
                                    "lon": lon,
                                    "altitude": aircraft[7] if aircraft[7] else 0,
                                    "velocity": aircraft[5] if aircraft[5] else 0,
                                    "true_track": aircraft[10] if aircraft[10] else 0,
                                    "vertical_rate": aircraft[11] if aircraft[11] else 0,
                                    "squawk": str(aircraft[14]) if aircraft[14] else '0000',
                                    "category": 'A1',
                                    "timestamp": datetime.now().isoformat(),
                                    "hex": aircraft[0] if aircraft[0] else '',
                                    "gs": aircraft[5] if aircraft[5] else 0,
                                    "track": aircraft[10] if aircraft[10] else 0,
                                    "baro_rate": aircraft[11] if aircraft[11] else 0,
                                    "flight": aircraft[1] if aircraft[1] else '',
                                    "mach": 0,
                                    "messages": 0,
                                    "seen": 0,
                                    "rssi": 0,
                                }
                                aircraft_list.append(aircraft_data)
                
                print(f"✅ OpenSky (HTTP): {len(aircraft_list)} uçak Türkiye'de")
                aircraft_list = convert_to_aircraft_model(aircraft_list)
                return [aircraft.dict() for aircraft in aircraft_list]
            elif response.status_code == 429:
                print("⚠️ OpenSky rate limit - 10 saniye bekle")
                await asyncio.sleep(10)  # Rate limit bekle
                return []  # Boş döner, frontend retry edecek
            else:
                print(f"❌ OpenSky HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ OpenSky HTTP hatası: {str(e)}")
            
        # 2. Sunucu tarafı ADS-B alıcısını dene
        try:
            raw_data = await server_side_adsb_receiver()
            if raw_data and len(raw_data) > 0:
                print(f"✅ Sunucu ADS-B alıcısından {len(raw_data)} gerçek uçak verisi çekildi")
                aircraft_list = convert_to_aircraft_model(raw_data)
                return [aircraft.dict() for aircraft in aircraft_list]
        except Exception as e:
            print(f"❌ Sunucu ADS-B alıcısı hatası: {str(e)}")
            # Devam et - diğer kaynakları dene
        
        # 4. ADSB.one dene (ESKI CALISAN VERSIYON)
        raw_data = await fetch_adsb_one_data()
        if raw_data and len(raw_data) > 0:
            print(f"✅ ADSB.one'den {len(raw_data)} gerçek uçak verisi çekildi")
            aircraft_list = convert_to_aircraft_model(raw_data)
            return [aircraft.dict() for aircraft in aircraft_list]
        
        # 2. ADS-B Exchange dene
        print("⚠️ ADSB.one başarısız, ADS-B Exchange deneniyor...")
        raw_data = await fetch_adsb_exchange_data()
        if raw_data and len(raw_data) > 0:
            print(f"✅ ADS-B Exchange'den {len(raw_data)} gerçek uçak verisi çekildi")
            aircraft_list = convert_to_aircraft_model(raw_data)
            return [aircraft.dict() for aircraft in aircraft_list]
        
        # 3. OpenSky son çare
        print("⚠️ ADS-B Exchange başarısız, OpenSky deneniyor...")
        raw_data = await fetch_opensky_data()
        if raw_data and len(raw_data) > 0:
            print(f"✅ OpenSky'den {len(raw_data)} gerçek uçak verisi çekildi")
            aircraft_list = convert_to_aircraft_model(raw_data)
            return [aircraft.dict() for aircraft in aircraft_list]
        
        # 4. Hiçbiri çalışmazsa BOŞ DÖN - SİMÜLASYON YOK
        print("❌ HİÇBİR GERÇEK VERİ KAYNAĞI ÇALIŞMIYOR! Gerçek ADS-B verisi gerekli.")
        return []  # Sadece gerçek veri - simülasyon yok
        
    except Exception as e:
        print(f"❌ Sistem hatası: {str(e)}")
        return []

# Global aircraft storage - uçakları hafızada tut
AIRCRAFT_STORAGE = {}

def generate_realistic_simulation() -> List[Dict]:
    """Generate realistic aircraft simulation - Turkey, neighbors, and conflict zones"""
    import random
    global AIRCRAFT_STORAGE
    
    # İlk defa çalışıyorsa uçakları oluştur
    if not AIRCRAFT_STORAGE:
        print("🔧 İlk defa uçaklar oluşturuluyor...")
        
        # Geniş bölge havaalanları - Türkiye, komşular, savaş bölgeleri
        aircraft_types = ['A320', 'B737', 'B738', 'A321', 'A330', 'B777', 'A350', 'E190', 'CRJ9', 'F-16', 'F-35', 'SU-24', 'MIG-29']
        callsigns = ['THY', 'PCX', 'PGT', 'TKH', 'SXS', 'AJH', 'DHK', 'BTK', 'KLM', 'LUF', 'BAW', 'DLH', 'UAE', 'QTR', 'ETD', 'SIA', 'IRK', 'SYR', 'IRQ', 'AFG']
        
        # Geniş bölge havaalanları
        airports = {
            # Türkiye
            'IST': (41.015, 28.979), 'SAW': (40.898, 29.309), 'ESB': (39.927, 32.683),
            'AYT': (36.898, 30.800), 'ADB': (38.292, 27.155), 'ADA': (37.011, 27.915),
            'TZX': (41.027, 40.975), 'DLM': (37.083, 28.361), 'BJV': (37.047, 27.222),
            
            # Komşular
            'ATH': (37.938, 23.727), 'SKG': (40.519, 22.970), 'SOF': (42.697, 23.401),
            'BEG': (44.819, 20.307), 'OTP': (44.571, 26.085), 'KBP': (50.402, 30.449),
            
            # Savaş bölgeleri
            'BEY': (33.822, 35.496), 'DAM': (33.408, 36.291), 'BGW': (33.265, 44.241),
            'TEH': (35.696, 51.311), 'KBL': (34.565, 69.207), 'CAI': (30.122, 31.401),
            
            # Doğu Akdeniz
            'LCA': (34.877, 33.652), 'PFO': (34.717, 32.483), 'AYN': (36.722, 27.915),
            
            # Körfez
            'DXB': (25.253, 55.367), 'DOH': (25.273, 51.609), 'KWI': (29.227, 47.967),
            'BAH': (26.267, 50.655), 'MCT': (23.593, 58.285),
            
            # Kızıl Deniz
            'JED': (21.705, 39.156), 'RUH': (24.957, 46.698), 'DMM': (26.423, 50.089),
        }
        
        # 100 uçak oluştur
        for i in range(100):
            dep_airport, (dep_lat, dep_lon) = random.choice(list(airports.items()))
            arr_airport, (arr_lat, arr_lon) = random.choice(list(airports.items()))
            
            while arr_airport == dep_airport:
                arr_airport, (arr_lat, arr_lon) = random.choice(list(airports.items()))
            
            # Başlangıç pozisyonu
            progress = random.random()
            lat = dep_lat + (arr_lat - dep_lat) * progress
            lon = dep_lon + (arr_lon - dep_lon) * progress
            
            import math
            heading = math.degrees(math.atan2(lon - dep_lon, lat - dep_lon))
            if heading < 0:
                heading += 360
            
            # Mesafeye göre irtifa
            distance = math.sqrt((arr_lat - dep_lat)**2 + (arr_lon - dep_lon)**2) * 111
            if distance > 800:
                altitude = random.randint(35000, 45000)
            elif distance > 300:
                altitude = random.randint(28000, 39000)
            else:
                altitude = random.randint(10000, 35000)
            
            speed = random.randint(200, 550)
            
            # Anomali skoru
            if dep_airport in ['BEY', 'DAM', 'BGW', 'TEH', 'KBL'] or arr_airport in ['BEY', 'DAM', 'BGW', 'TEH', 'KBL']:
                anomaly_score = random.choices(
                    [random.randint(0, 20), random.randint(20, 50), random.randint(50, 80), random.randint(80, 100)],
                    weights=[40, 30, 20, 10]
                )[0]
            else:
                anomaly_score = random.choices(
                    [random.randint(0, 20), random.randint(20, 40), random.randint(40, 80), random.randint(80, 100)],
                    weights=[70, 20, 8, 2]
                )[0]
            
            # Risk seviyesi
            if anomaly_score < 25:
                risk_level = "Normal"
                risk_reason = "Normal uçuş profili."
                flags = []
            elif anomaly_score < 50:
                risk_level = "Düşük"
                risk_reason = "Hafif anomali tespit edildi."
                flags = ["hafif_anomali"]
            elif anomaly_score < 75:
                risk_level = "Yüksek"
                risk_reason = "Önemli anomali tespit edildi."
                flags = ["önemli_anomali"]
            else:
                risk_level = "Kritik"
                risk_reason = "Kritik anomali tespit edildi!"
                flags = ["kritik_anomali"]
            
            aircraft_id = f"{random.randint(100000, 999999)}"
            AIRCRAFT_STORAGE[aircraft_id] = {
                "id": aircraft_id,
                "callsign": f"{random.choice(callsigns)}{random.randint(100, 999)} ",
                "dep_lat": dep_lat, "dep_lon": dep_lon,
                "arr_lat": arr_lat, "arr_lon": arr_lon,
                "current_progress": progress,
                "speed": speed,
                "altitude": altitude,
                "heading": heading,
                "aircraft_type": random.choice(aircraft_types),
                "anomaly_score": anomaly_score,
                "risk_level": risk_level,
                "anomaly_reason": risk_reason,
                "flags": flags,
            }
    
    # Mevcut uçakları güncelle - yavaş hareket
    aircraft_list = []
    for aircraft_id, aircraft_data in AIRCRAFT_STORAGE.items():
        # İlerlemeyi güncelle (yavaş hareket)
        progress_increment = 0.001  # Çok yavaş - 0.1% per request
        aircraft_data["current_progress"] += progress_increment
        
        # Varışa ulaştıysa yeni rota ata
        if aircraft_data["current_progress"] >= 1.0:
            # Yeni rastgele rota
            airports = {
                'IST': (41.015, 28.979), 'SAW': (40.898, 29.309), 'ESB': (39.927, 32.683),
                'BEY': (33.822, 35.496), 'DAM': (33.408, 36.291), 'BGW': (33.265, 44.241),
                'TEH': (35.696, 51.311), 'DXB': (25.253, 55.367), 'DOH': (25.273, 51.609),
            }
            dep_airport, (dep_lat, dep_lon) = random.choice(list(airports.items()))
            arr_airport, (arr_lat, arr_lon) = random.choice(list(airports.items()))
            
            while arr_airport == dep_airport:
                arr_airport, (arr_lat, arr_lon) = random.choice(list(airports.items()))
            
            aircraft_data["dep_lat"] = dep_lat
            aircraft_data["dep_lon"] = dep_lon
            aircraft_data["arr_lat"] = arr_lat
            aircraft_data["arr_lon"] = arr_lon
            aircraft_data["current_progress"] = 0.0
            
            # Yeni heading
            import math
            heading = math.degrees(math.atan2(arr_lon - dep_lon, arr_lat - dep_lat))
            if heading < 0:
                heading += 360
            aircraft_data["heading"] = heading
        
        # Mevcut pozisyonu hesapla
        lat = aircraft_data["dep_lat"] + (aircraft_data["arr_lat"] - aircraft_data["dep_lat"]) * aircraft_data["current_progress"]
        lon = aircraft_data["dep_lon"] + (aircraft_data["arr_lon"] - aircraft_data["dep_lon"]) * aircraft_data["current_progress"]
        
        aircraft = {
            "id": aircraft_data["id"],
            "callsign": aircraft_data["callsign"],
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "altitude": aircraft_data["altitude"],
            "speed": round(aircraft_data["speed"], 1),
            "heading": round(aircraft_data["heading"]),
            "timestamp": datetime.now().isoformat(),
            "aircraft_type": aircraft_data["aircraft_type"],
            "anomaly_score": aircraft_data["anomaly_score"],
            "risk_level": aircraft_data["risk_level"],
            "anomaly_reason": aircraft_data["anomaly_reason"],
            "flags": aircraft_data["flags"],
            "route": [
                {"lat": round(aircraft_data["dep_lat"], 6), "lon": round(aircraft_data["dep_lon"], 6), "timestamp": datetime.now().isoformat()},
                {"lat": round(aircraft_data["arr_lat"], 6), "lon": round(aircraft_data["arr_lon"], 6), "timestamp": datetime.now().isoformat()}
            ]
        }
        
        aircraft_list.append(aircraft)
    
    print(f"✅ Sabit uçak simülasyonu: {len(aircraft_list)} uçak yavaş hareket ediyor")
    return aircraft_list

@app.get("/api/vessels")
async def get_vessels():
    """Get vessel data - no real-time marine API available yet"""
    # TODO: Gerçek zamanlı deniz verisi API'si entegre edilecek (AIS, MarineTraffic vb.)
    # Şu an için sadece uçak verisi odaklı çalışıyoruz
    return []

@app.get("/api/alerts")
async def get_alerts():
    """Get alerts based on current anomalies"""
    try:
        aircrafts = await get_aircrafts()
        
        alerts = []
        for aircraft in aircrafts:
            if aircraft["anomaly_score"] > 50:
                alert = Alert(
                    id=f"ALT{len(alerts)+1:03d}",
                    type="hava",
                    entity_id=aircraft["id"],
                    entity_name=aircraft["callsign"],
                    title=f"Anomali Tespit Edildi: {aircraft['callsign']}",
                    description=aircraft["anomaly_reason"],
                    risk_level=aircraft["risk_level"],
                    timestamp=aircraft["timestamp"],
                    coordinates={"lat": aircraft["lat"], "lon": aircraft["lon"]},
                    category="Havacılık"
                )
                alerts.append(alert.dict())
        
        return alerts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating alerts: {str(e)}")

@app.get("/api/vessels")
async def get_vessels():
    """Get vessel data - no real-time marine API available yet"""
    # TODO: Gerçek zamanlı deniz verisi API'si entegre edilecek (AIS, MarineTraffic vb.)
    # Şu an için sadece uçak verisi odaklı çalışıyoruz
    return []

@app.get("/api/strategic-zones")
async def get_strategic_zones():
    """Get strategic zones data - predefined geopolitical boundaries"""
    try:
        # Stratejik bölgeler statik veri - gerçek coğrafi sınırlar
        with open("../src/data/strategicZones.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Strategic zones loading error: {str(e)}")
        # Boş GeoJSON dön - mock yerine gerçek veri yok mesajı
        return {
            "type": "FeatureCollection",
            "features": []
        }

@app.get("/api/news")
async def get_news():
    """Get OSINT news data - currently placeholder for future RSS integration"""
    try:
        # TODO: Gerçek zamanlı haber/OSINT API'si entegre edilecek
        # Şu an için istihbarat haberleri için placeholder
        with open("../src/data/news.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"News data loading error: {str(e)}")
        # Boş array dön - mock yerine gerçek veri yok mesajı
        return []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
