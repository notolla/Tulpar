# EFES-2026 YARIN İÇİN CHECKPOINT

## 🎯 AÇIK HATALAR (YARIN DÜZELTİLECEK)

### 1. KRİTİK: /api/vessels Formatı
- **Dosya:** `backend/main_production.py` satır 201-225
- **Sorun:** Object döndürüyor `{type, count, data}`, array olmalı
- **Düzeltme:** `return JSONResponse([...])` yap

### 2. WebSocket Bağlantı
- **Endpoint:** `ws://localhost:8000/ws/sitrep`
- **Durum:** Hâlâ failed
- **Kontrol:** `app/ws/sitrep.py` websocket.accept() var mı?

### 3. Frontend Crash
- **VesselLayer.tsx** array bekliyor ama object geliyor
- **Hata:** `vessels.forEach is not a function`

---

## ✅ ÇALIŞAN ŞEYLER

### Backend (Port 8000)
- ✅ `main_production.py` çalışıyor
- ✅ `/api/aircraft` 25 uçak dönüyor
- ✅ StateStore, DiffEngine, EventBus hazır
- ✅ AircraftIngestor 2sn interval çalışıyor

### Production Mimarisi
```
app/core/state_store.py       ✅
app/core/diff_engine.py       ✅
app/core/event_bus.py         ✅
app/ws/sitrep.py              ✅
app/services/aircraft_ingestor.py  ✅
```

---

## 🔧 YARIN İLK İŞLEM

1. Backend'de `/api/vessels` düzelt
2. Servisleri restart et
3. Frontend test et
4. WebSocket bağlantı kontrol et

---

## 📂 ÖNEMLİ DOSYALAR

- `backend/main_production.py` - Entry point
- `src/hooks/useRealtimeAircraft.ts` - Frontend WS client
- `src/components/map/VesselLayer.tsx` - Gemi katmanı
- `backend/app/ws/sitrep.py` - WebSocket handler

---

## 🔗 SERVİS URL'LERİ

```
Backend:   http://localhost:8000
WebSocket: ws://localhost:8000/ws/sitrep
Frontend:  http://localhost:5173
```

## 🎯 HEDEF

Uçaklar haritada gerçek zamanlı görünecek, gemiler array formatında dönecek, WebSocket stabil çalışacak.
