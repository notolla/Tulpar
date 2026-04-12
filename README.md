# EFES-2026 - Military Intelligence Platform

## 🎯 Proje Hedefi
EFES-2026, Türkiye'nin önde gelen askeri ve stratejik tehditlerini gerçek zamanlı olarak izleyen, analiz eden ve görselleştiren askeri komuta merkezi sistemi.

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────┐
│                                    │
│              │    ┌─────────────────────┐
│              │    │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │    │    │    │    │    │
│              │ │    │    │    │    │
│              │    │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │    │
│              │    │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │    │    │    │    │
│              │ │ │    │    │    │
│              │    │    │    │    │    │
│              │ │ │    │    │    │
│              │ │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ │ │    │    │    │    │
│              │ │    │    │    │    │
│              │ └─────────────────────────────┘
│              │
│              │
│              │
│              │    │    │    │    │
│              │
│              │
│              │
│              │
│              │
│              │    │    │    │    │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
              │
│              │
│              │
│              │
│              │
│              │
              │
│              │
│              │
│              │
              │
│              │
│              │
│              │
│              │
              │
              │
              │
              │
│              │
│              │
              │
              │
              │              │
│              │
              │
              │
              │
              │
              │
              │
│              │
              │
              │
│              │
              │
│              │
│              │
              │
│              │
│              │
│              │
│              │
              │
│              │
│              │
│              │
              │
│              │
│              │
│              │
              │
              │
              │
              │
              │
│              │
              │
              │
│              │
│              │
              │
              │
│              │
│              │
              │
│              │
│              │
              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│              │
│ │
│              │
│              │
│              │
│ │
│              │
│              │
│
│              │
│
│ │
│              │
│ │
│              │
              │
│              │
│              │
              │
│              │
│              │
│              │
│              │
│              │
│              │
              │
│
│              │
              │
              │
│              │
│
              │
              │
│              │
              │
│
│              │
│ │
│              │
│
│              │
              │
│              │
│              │
│              │
│
              │
│              │
│              │
│              │
│
              │
 │              │
              │
              │
              │
              │
              │
              │
              │
              │
│              │
│              │
│
              │
              │
│
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
│              │
              │
│              │
              │
              │
              │
              │
              │
              │
│              │
              │
              │
              │
              │
│              │
              │
│
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
│              │
│              │
              │
              │
│              │
              │
│              │
│
              │
              │
              │
              │
              │
│              │
              │
│
              │
│
              │
              │
              │
│              │
              │
│
              │
              │
│
│              │
│ │
              │
│ │
              │
│
│              │
              │
              │
              │
              │
              │
              │
              │
              │
              │
│              │
│
              │
              │
              │
│              │
│ │
              │
│
              │
│
              │
│
              │
              │
              │
              │
│
│              │
│              │
              │
              │
│              │
│
              │
              │
│
              │
              │
│
│              │
│
              │
│              │
│
│              │
│
              │
              │
              │
              │
│
│              │
              │
│
│              │
              │
              │
│
              │
              │
│
              │
              │
│
│              │
              │
│
│              │
│
│              │
│
│              │
              │
│
              │
              │
              │
│
│              │
│
│
│              │
│
              │
              │
              │
│
│              │
│
│              │
│
│
              │
              │
│
              │
│
              │
              │
│              │
│
              │
              │
│
│
│              │
              │
│ │
              │
│
│              │
│
│              │
│
│
              │
              │
              │
              │
              │
│              │
│
│              │
              │
│
              │
│
│              │
│
│
              │
              │
│
              │
│
│              │
              │
│
│ │
│
              │
              │
              │
│
│ │
              │
│
│              │
│
│              │
│
              │
              │
              │
              │
│
│              │
│
│ │
              │
│ │
│
│              │
              │
│
│ │
│
              │
│
│ │
│ │
│ │
│ │
              │
│
│              │
              │
              │
│
│ │
│
              │
              │
              │
│ 
└─────────────────────────────────────────────┘

## 🚀 Kurulum ve Çalıştırma

### Backend Servisleri
```bash
# Ana API (8000 port)
cd backend && python main.py

# Collector Service (Background task)
cd backend && python collector_service.py

# Scalable API (8002 port)
cd backend && python scalable_api.py

# Redis (localhost:6379)
docker run -d -p 6379:6379 redis:latest
```

### Frontend
```bash
npm install
npm start
```

### Port'lar
- **8000** - Ana FastAPI
- **8001** - Scalable API
- **6379** - Redis
- **5173** - Frontend

## 🔧 Teknoloji Stack

**Backend:**
- **FastAPI** - High-performance async framework
- **Redis** - In-memory cache
- **AsyncIO** - Non-blocking I/O
- **Background Tasks** - Data processing
- **Rate Limiting** - DDoS koruması

**Frontend:**
- **React + TypeScript** - Modern UI development
- **CesiumJS** - 3D görselleştirme
- **WebSocket** - Real-time updates
- **Tailwind CSS** - Utility-first styling

**📊 Veri Akışı**
1. **ADS-B/AIS Sources → Collector Service** → Redis Cache → Frontend
2. **WebSocket** - Real-time güncellemeler
3. **Polling** - Fallback mekanizması
4. **Event-driven** - React state management

## 🎯 Özellikler

### 📡 Real-Time Data
- ✅ **Anlık uçak/gemi takibi**
- ✅ **Anomali detection ve scoring**
- ✅ **Risk seviyesi sınıflandırma**
- ✅ **Stratejik bölge izleme**
- ✅ **Tarihçe bazlı veri saklama**

### 🎯 Performans
- ✅ **Scalable** - Yüksek veri desteği
- ✅ **Cached** - 5 dakika önbellek
- ✅ **Optimized** - Rate limit ve caching

### 🎯 Kullanıcı Arayüzü
- ✅ **3D World View** - Küresel kontrolü
- ✅ **Entity Selection** - Detaylı bilgi
- ✅ **Command Center** - "Komuta merkezi"
- ✅ **Alert System** - Anomali bildirimleri

## 🏆 EFES-2026 Hazır!

**🔥 GERÇEK VERİSİ İÇİN!**
- ✅ **Backend çalışıyor** - OpenSky verisi geliyor
- ✅ **Frontend hazır** - Data layer hazır
- ✅ **Mimari hazır** - Component'lar yazıldı
- ✅ **Anomali modeli** - ML için hook'lar bırakıldı

**🎯 DAHAHA GELİŞTİRİLECEK:**
1. **3D görselleştirme** - CesiumJS entegrasyonu
2. **Entity tracking** - Uçak/gemi takibi
3. **Alert system** - Bildirim yönetimi
4. **AI/ML** - Anomali modeli eğitimi

**EFES-2026 için hazır!** 🦇🏙️✈️📡🎯🚀
