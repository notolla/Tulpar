"""
OpenSky ADS-B Collector
Gerçek uçak verisi için 60 saniyelik cache ile çalışan servis
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenSkyCollector:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 55  # 55 saniye cache (OpenSky 60sn'de bir güncellenir)
        self.last_fetch = 0
        # OpenSky API credentials
        self.client_id = "notolla-api-client"
        self.client_secret = "GHIkva2lDrdGUuNGplugyxqCZCsCCI0V"
        
    def fetch_aircraft(self) -> List[Dict]:
        """OpenSky'dan gerçek uçak verisi çek - cache ile"""
        current_time = time.time()
        
        # Cache kontrolü
        if 'aircraft' in self.cache:
            cache_age = current_time - self.cache['aircraft']['timestamp']
            if cache_age < self.cache_ttl:
                logger.info(f"📦 Cache'den {len(self.cache['aircraft']['data'])} uçak döndürülüyor ({cache_age:.0f}s önce)")
                return self.cache['aircraft']['data']
        
        # OpenSky API çağrısı - Türkiye ve çevresi
        try:
            logger.info("🛰️ OpenSky'dan gerçek uçak verisi çekiliyor...")
            
            # Türkiye bbox: lat 35-42, lon 25-45
            params = {
                'lamin': 35.0,
                'lomin': 25.0,
                'lamax': 42.0,
                'lomax': 45.0
            }
            
            headers = {
                'User-Agent': 'TULPAR-EFES2026/1.0'
            }
            
            # API credentials ile authentication
            auth = (self.client_id, self.client_secret) if self.client_id and self.client_secret else None
            
            response = requests.get(
                "https://opensky-network.org/api/states/all",
                params=params,
                headers=headers,
                auth=auth,
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                aircraft_list = []
                
                if 'states' in data and data['states']:
                    for state in data['states']:
                        # OpenSky format: [icao24, callsign, origin_country, time_position, last_contact, 
                        # lat, lon, baro_altitude, on_ground, velocity, true_track, vertical_rate, 
                        # sensors, geo_altitude, squawk, spi, position_source]
                        if state[5] and state[6]:  # lat, lon varsa
                            aircraft = {
                                'id': state[0] if state[0] else 'UNKNOWN',
                                'callsign': state[1].strip() if state[1] else 'UNKNOWN',
                                'lat': float(state[5]),
                                'lon': float(state[6]),
                                'altitude': int(state[7]) if state[7] else 0,
                                'speed': float(state[9]) if state[9] else 0,
                                'heading': int(state[10]) if state[10] else 0,
                                'timestamp': datetime.now().isoformat(),
                                'anomaly_score': 0,
                                'risk_level': 'Normal',
                                'anomaly_reason': 'Normal uçuş profili',
                                'flags': []
                            }
                            aircraft_list.append(aircraft)
                
                # Cache'e kaydet
                self.cache['aircraft'] = {
                    'data': aircraft_list,
                    'timestamp': current_time
                }
                
                logger.info(f"✅ OpenSky'dan {len(aircraft_list)} gerçek uçak alındı")
                return aircraft_list
                
            elif response.status_code == 429:
                logger.warning("⚠️ OpenSky rate limit - gerçekçi test verisi kullanılıyor")
                return self._generate_realistic_test_aircraft()
            else:
                logger.error(f"❌ OpenSky HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ OpenSky hatası: {str(e)}")
            # Hata durumunda cache'den döndür
            if 'aircraft' in self.cache:
                return self.cache['aircraft']['data']
            return self._generate_realistic_test_aircraft()
    
    def _generate_realistic_test_aircraft(self) -> List[Dict]:
        """Gerçekçi test uçakları üret - THY, Pegasus, askeri uçuşlar"""
        import random
        
        # Türk havayolları ve askeri uçuşlar
        airlines = [
            ('THY', 'Turkish Airlines', 'A321'),
            ('THY', 'Turkish Airlines', 'B738'),
            ('THY', 'Turkish Airlines', 'A330'),
            ('PGS', 'Pegasus', 'B738'),
            ('PGS', 'Pegasus', 'A320'),
            ('SRK', 'SunExpress', 'B738'),
            ('AJT', 'AJet', 'B738'),
            ('NATO', 'NATO', 'C17'),
            ('TUAF', 'Turkish AF', 'F16'),
            ('TC', 'Private', 'C172'),
        ]
        
        # Türkiye üzerinde gerçekçi rota noktaları
        route_points = [
            (41.0, 28.8),   # İstanbul
            (39.9, 32.8),   # Ankara
            (38.4, 27.1),   # İzmir
            (36.9, 30.7),   # Antalya
            (40.6, 43.1),   # Kars
            (37.0, 35.3),   # Adana
            (40.1, 29.0),   # Bursa
            (41.3, 36.3),   # Samsun
            (37.9, 40.2),   # Diyarbakır
            (39.8, 30.5),   # Eskişehir
            (38.5, 29.4),   # Denizli
            (37.7, 29.1),   # Muğla
            (36.2, 36.1),   # Hatay
            (39.5, 44.0),   # Ağrı
            (41.2, 27.0),   # Tekirdağ
            (40.8, 31.0),   # Bolu
            (38.0, 27.5),   # Manisa
            (37.2, 28.8),   # Bodrum
            (39.0, 35.0),   # Nevşehir
            (41.8, 26.5),   # Edirne
            (38.3, 34.4),   # Konya
            (37.6, 36.9),   # Kahramanmaraş
            (39.6, 27.9),   # Balıkesir
            (40.3, 27.8),   # Çanakkale
            (36.7, 37.1),   # Gaziantep
        ]
        
        aircraft_list = []
        current_time = datetime.now().isoformat()
        
        for i in range(min(30, len(route_points))):
            lat, lon = route_points[i]
            # Rastgele uçak tipi seç
            prefix, airline, ac_type = random.choice(airlines)
            
            # Gerçekçi uçuş numarası
            flight_num = random.randint(100, 3999)
            callsign = f"{prefix}{flight_num}"
            
            # Gerçekçi irtifa ve hız
            altitude = random.choice([8000, 15000, 25000, 32000, 36000, 41000])
            speed = random.randint(380, 520) if altitude > 20000 else random.randint(250, 350)
            
            # Gerçekçi yön
            heading = random.randint(0, 359)
            
            aircraft = {
                'id': f"TEST{flight_num:04d}",
                'callsign': callsign,
                'lat': lat + random.uniform(-0.1, 0.1),
                'lon': lon + random.uniform(-0.1, 0.1),
                'altitude': altitude,
                'speed': speed,
                'heading': heading,
                'timestamp': current_time,
                'anomaly_score': 0,
                'risk_level': 'Normal',
                'anomaly_reason': 'Gerçekçi test uçuşu',
                'flags': []
            }
            aircraft_list.append(aircraft)
        
        logger.info(f"🎯 {len(aircraft_list)} gerçekçi test uçak üretildi")
        return aircraft_list

# Global instance
collector = OpenSkyCollector()

if __name__ == "__main__":
    # Test
    aircrafts = collector.fetch_aircraft()
    print(f"Test: {len(aircrafts)} uçak bulundu")
    if aircrafts:
        print(f"Örnek: {aircrafts[0]}")
