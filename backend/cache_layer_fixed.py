"""
EFES-2026 Redis Cache Layer
Veri cache'leme ve hızlı erişim
"""

import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheLayer:
    """Redis cache yönetimi"""
    
    def __init__(self):
        self.cache_data = {}
        self.cache_ttl = {
            'aircraft': 300,  # 5 dakika
            'vessels': 600,  # 10 dakika
            'strategic_zones': 3600,  # 1 saat
            'alerts': 180  # 3 dakika
        }
        
    async def init_redis(self):
        """Redis bağlantısı - Memory cache"""
        try:
            logger.info("✅ Memory cache başlatıldı")
            return True
        except Exception as e:
            logger.error(f"❌ Cache başlatma hatası: {str(e)}")
            return False
    
    async def set_data(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Veri cache'e kaydet"""
        try:
            cache_ttl = ttl or self.cache_ttl.get(key.split(':')[0], 300)
            
            self.cache_data[f"efes2026:{key}"] = {
                'data': data,
                'timestamp': datetime.now().timestamp(),
                'ttl': cache_ttl
            }
            
            logger.info(f"✅ Cache'e kaydedildi: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Cache kayıt hatası: {str(e)}")
            return False
    
    async def get_data(self, key: str) -> Optional[Any]:
        """Cache'den veri oku"""
        try:
            cache_key = f"efes2026:{key}"
            if cache_key in self.cache_data:
                cached_item = self.cache_data[cache_key]
                
                # TTL kontrolü
                current_time = datetime.now().timestamp()
                if current_time - cached_item['timestamp'] < cached_item['ttl']:
                    logger.info(f"📦 Cache'den okundu: {key}")
                    return cached_item['data']
                else:
                    # Süresi geçmiş, sil
                    del self.cache_data[cache_key]
            
            return None
        except Exception as e:
            logger.error(f"❌ Cache okuma hatası: {str(e)}")
            return None
    
    async def delete_data(self, key: str) -> bool:
        """Cache'den veri sil"""
        try:
            cache_key = f"efes2026:{key}"
            if cache_key in self.cache_data:
                del self.cache_data[cache_key]
                logger.info(f"🗑️ Cache'den silindi: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Cache silme hatası: {str(e)}")
            return False
    
    async def get_all_keys(self, pattern: str) -> List[str]:
        """Pattern'e göre tüm anahtarları getir"""
        try:
            keys = []
            for key in self.cache_data.keys():
                if pattern in key:
                    keys.append(key)
            return keys
        except Exception as e:
            logger.error(f"❌ Anahtar listeleme hatası: {str(e)}")
            return []
    
    async def get_cache_stats(self) -> Dict:
        """Cache istatistikleri"""
        try:
            return {
                'cache_type': 'memory',
                'total_keys': len(self.cache_data),
                'memory_usage': f"{len(str(self.cache_data))} bytes",
                'last_update': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Cache istatistik hatası: {str(e)}")
            return {'error': str(e)}
    
    async def cleanup_expired(self):
        """Süresi geçmiş verileri temizle"""
        try:
            current_time = datetime.now().timestamp()
            expired_keys = []
            
            for key, value in self.cache_data.items():
                if current_time - value['timestamp'] > value['ttl']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache_data[key]
            
            if expired_keys:
                logger.info(f"🧹 {len(expired_keys)} eski veri temizlendi")
        except Exception as e:
            logger.error(f"❌ Cache temizleme hatası: {str(e)}")

# Global cache instance
cache_layer = CacheLayer()
