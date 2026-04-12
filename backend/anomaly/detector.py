"""
TULPAR Anomali Motoru v2
────────────────────────
Katmanlı hybrid skorlama:
  L1 — Squawk acil kodları   (7500/7600/7700 → anında 100, Kritik)
  L2 — Kural tabanlı         (stratejik bölge, irtifa/hız tutarsızlığı)
  L3 — IsolationForest       (sadece 0-20 katkı, gürültüyü düşürdük)
  L4 — Askeri zone yakınlık  (track_store'dan gelen aktif askeri bölgeler)
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Stratejik bölgeler (merkez lat, lon, kritik yarıçap km, ad) ───────────────
# Sadece EN YAKIN bölge skora katkıda bulunur → çoklu sayım engellendi
STRATEGIC_ZONES: List[Tuple[float, float, float, str]] = [
    (41.1,  29.05,  30,  "İstanbul Boğazı"),
    (40.15, 26.40,  25,  "Çanakkale Boğazı"),
    (39.00, 25.50,  60,  "Ege FIR Sınırı"),
    (36.50, 30.00,  80,  "Doğu Akdeniz"),
    (43.00, 32.00,  90,  "Karadeniz Batı"),
    (26.00, 56.50,  40,  "Hürmüz Boğazı"),
    (27.00, 52.00, 150,  "Körfez Bölgesi"),
    (31.60, 32.30,  30,  "Süveyş Kanalı"),
    (31.50, 35.00,  80,  "İsrail-Gazze"),
    (36.50, 40.00, 120,  "Suriye-Irak"),
    (49.00, 35.00, 200,  "Ukrayna Cephesi"),
    (54.00, 22.50,  60,  "Suwałki Koridoru"),
]

RESTRICTED_AIRSPACES = [
    (39.93, 32.86, 25, 0, 18000, "Ankara TMA"),
    (40.98, 28.81, 40, 0, 10000, "İstanbul TMA"),
    (38.29, 27.16, 30, 0, 10000, "İzmir TMA"),
]

# Squawk kodları ve Türkçe anlamları
EMERGENCY_SQUAWKS: Dict[str, str] = {
    "7500": "UÇAK KAÇIRMA",
    "7600": "RADYO ARIZASI",
    "7700": "ACİL DURUM / MAYDAY",
}

# Askeri callsign prefix'leri
MILITARY_PREFIXES = (
    "TUAF", "NATO", "RFF", "UKAF", "USAF", "ARMY", "NAVY",
    "RUS", "UAF", "ISR", "BRTN", "FRCE", "DENA", "GERM", "ITAL",
    "CTAF", "KRAL", "EFES", "MAVI",
)


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_strategic(lat: float, lon: float) -> Tuple[float, str]:
    """En yakın stratejik bölge → (mesafe/yarıçap oranı, ad)"""
    best_ratio = float("inf")
    best_name  = ""
    for zlat, zlon, zr, zname in STRATEGIC_ZONES:
        ratio = haversine_km(lat, lon, zlat, zlon) / zr
        if ratio < best_ratio:
            best_ratio, best_name = ratio, zname
    return best_ratio, best_name


def _in_restricted(lat: float, lon: float, alt: float) -> Optional[str]:
    for rlat, rlon, rr, rbot, rtop, rname in RESTRICTED_AIRSPACES:
        if haversine_km(lat, lon, rlat, rlon) < rr and rbot <= alt <= rtop:
            return rname
    return None


def _is_military_callsign(callsign: str) -> bool:
    cs = callsign.upper()
    return any(cs.startswith(p) for p in MILITARY_PREFIXES)


def _classify_risk(score: int) -> str:
    if score >= 75:  return "Kritik"
    if score >= 55:  return "Yüksek"
    if score >= 35:  return "Orta"
    return "Düşük"


# ── L1: Squawk acil kodları ────────────────────────────────────────────────────

def _squawk_check(ac: Dict[str, Any]) -> Optional[Tuple[int, str]]:
    """
    7500/7600/7700 squawk → (100, Türkçe açıklama) döner.
    Aksi halde None.
    """
    squawk = str(ac.get("squawk", "")).strip()
    if squawk in EMERGENCY_SQUAWKS:
        meaning = EMERGENCY_SQUAWKS[squawk]
        return 100, f"ACİL: Squawk {squawk} — {meaning}."
    return None


# ── L2: Kural tabanlı ─────────────────────────────────────────────────────────

def _rule_based_score(ac: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    score   = 0
    reasons: List[str] = []
    flags   = list(ac.get("flags", []))

    lat      = float(ac.get("lat",      0))
    lon      = float(ac.get("lon",      0))
    altitude = float(ac.get("altitude", 0))
    speed    = float(ac.get("speed",    0))
    callsign = str(ac.get("callsign",   "")).strip()
    ac_type  = str(ac.get("aircraft_type", "")).upper()

    # Transponder yok / bilinmeyen callsign (+25)
    if not callsign or callsign.upper() in ("UNKNOWN", "", "00000000"):
        score += 25
        reasons.append("Transponder bilgisi eksik")
        _add_flag(flags, "NO_TRANSPONDER")

    # Askeri sınıf uçak (+15, ayrıca kaydedilecek ama kendi başına yüksek skor değil)
    if ac_type in ("MILITARY", "F16", "F-16", "F18", "F-18", "F35", "F-35") \
       or _is_military_callsign(callsign):
        if "MILITARY" not in flags:
            flags.append("MILITARY")
        score += 15
        reasons.append("Askeri sınıf uçak")

    # Stratejik bölge — SADECE EN YAKIN (çoklu sayım yok)
    zone_ratio, zone_name = _nearest_strategic(lat, lon)
    if zone_ratio < 0.4:
        score += 20
        reasons.append(f"{zone_name} içinde")
        _add_flag(flags, "STRATEGIC_ZONE")
    elif zone_ratio < 0.8:
        score += 8
        reasons.append(f"{zone_name} yakınında")

    # Kısıtlı hava sahası
    restricted = _in_restricted(lat, lon, altitude)
    if restricted:
        score += 12
        reasons.append(f"{restricted} kısıtlı sahası")
        _add_flag(flags, "RESTRICTED_AIRSPACE")

    # Hız/irtifa tutarsızlığı
    if 2000 < altitude < 10000 and speed > 700:
        score += 18
        reasons.append(f"Alçak irtifada ({altitude:.0f} ft) yüksek hız ({speed:.0f} km/h)")
        _add_flag(flags, "LOW_ALT")
    elif altitude < 15000 and speed > 950:
        score += 22
        reasons.append(f"Alçak irtifada aşırı hız ({speed:.0f} km/h)")
        _add_flag(flags, "HIGH_SPEED")
    elif altitude > 30000 and speed < 400:
        score += 10
        reasons.append(f"Cruise irtifasında düşük hız ({speed:.0f} km/h)")

    # Loiter
    if "LOITER" in flags:
        score += 18
        reasons.append("Döngüsel uçuş paterni")

    score = min(score, 90)  # Hard cap — squawk haricinde max 90

    main = (
        " — ".join(reasons[:2]) + "."
        if reasons
        else "Normal seyrüsefer profili."
    )
    return score, main, flags


def _add_flag(flags: List[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


# ── L4: Askeri zone yakınlık ──────────────────────────────────────────────────

def _military_zone_boost(
    lat: float, lon: float,
    military_zones: List[Dict[str, Any]],
) -> Tuple[int, str]:
    """
    Aktif bir askeri bölgenin exclusion yarıçapına girildiyse skor boost.
    Döner: (ek puan, açıklama)
    """
    for zone in military_zones:
        ex_r = float(zone.get("exclusion_radius_km", 50))
        zl   = float(zone.get("center_lat", 0))
        zlo  = float(zone.get("center_lon", 0))
        dist = haversine_km(lat, lon, zl, zlo)
        if dist < ex_r:
            cs   = zone.get("callsign", "?")
            age  = zone.get("age_minutes", 0)
            return 30, f"{cs} askeri uçuş bölgesine {dist:.0f} km yakınlık (son görülme: {age} dk önce)"
    return 0, ""


# ── Ana batch fonksiyonları ────────────────────────────────────────────────────

def score_aircraft_batch(
    aircraft_list: List[Dict[str, Any]],
    military_zones: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Uçak listesini anomali skoru ile zenginleştirir.
    military_zones: track_store.get_military_zones() çıktısı (opsiyonel).
    """
    mzones = military_zones or []

    # IsolationForest — sadece 0-20 arası katkı (L3)
    ml_scores = _compute_ml_scores(aircraft_list)

    result = []
    for ac, ml_s in zip(aircraft_list, ml_scores):
        enriched = copy.deepcopy(ac)

        # L1: Squawk — anında kritik
        squawk_hit = _squawk_check(ac)
        if squawk_hit:
            final_score, reason = squawk_hit
            enriched["anomaly_score"]  = final_score
            enriched["risk_score"]     = final_score
            enriched["risk_level"]     = "Kritik"
            enriched["anomaly_flag"]   = True
            enriched["anomaly_reason"] = reason
            flags = list(ac.get("flags", []))
            _add_flag(flags, "SQUAWK_EMERGENCY")
            enriched["flags"] = flags
            result.append(enriched)
            continue

        # L2: Kurallar
        rule_score, reason, flags = _rule_based_score(ac)

        # L3: ML katkısı (max 20 puan)
        ml_contrib = int(float(ml_s))

        # L4: Askeri zone
        mil_boost, mil_reason = _military_zone_boost(
            float(ac.get("lat", 0)), float(ac.get("lon", 0)), mzones
        )
        if mil_boost:
            reason = mil_reason
            _add_flag(flags, "MILITARY_ZONE_PROXIMITY")

        final_score = min(rule_score + ml_contrib + mil_boost, 100)

        enriched["anomaly_score"]  = final_score
        enriched["risk_score"]     = final_score
        enriched["risk_level"]     = _classify_risk(final_score)
        enriched["anomaly_flag"]   = final_score >= 35
        enriched["anomaly_reason"] = reason
        enriched["flags"]          = flags
        result.append(enriched)

    return result


def score_vessel_batch(vessel_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gemi listesine kural tabanlı anomali skoru atar."""
    result = []
    for vessel in vessel_list:
        enriched = copy.deepcopy(vessel)

        score   = 0
        reasons: List[str] = []
        flags   = list(vessel.get("flags", []))

        lat   = float(vessel.get("lat",   0))
        lon   = float(vessel.get("lon",   0))
        speed = float(vessel.get("speed", 0))
        mmsi  = str(vessel.get("mmsi",    ""))

        # Geçersiz MMSI
        if not mmsi or mmsi.startswith("000"):
            score += 30
            reasons.append("Geçersiz MMSI")
            _add_flag(flags, "INVALID_MMSI")

        # Askeri gemi
        if vessel.get("ship_type_code") == 35 or "MILITARY" in flags:
            score += 15
            reasons.append("Askeri gemi")

        # AIS sinyal kesintisi
        if "AIS_GAP" in flags:
            score += 28
            reasons.append("AIS sinyal kesintisi")

        # Dark ship — stratejik bölgede AIS kaybı → ekstra puan
        zone_ratio, zone_name = _nearest_strategic(lat, lon)
        if zone_ratio < 0.5:
            score += 15
            reasons.append(f"{zone_name} içinde")

        # Hız anomalisi (gemi tipine göre)
        type_code = int(vessel.get("ship_type_code") or 0)
        if type_code in range(80, 90) and speed > 20:   # Tanker 20 knot üstü imkânsız
            score += 25
            reasons.append(f"Tanker aşırı hız ({speed:.1f} knot)")
        elif type_code in range(70, 80) and speed > 28:  # Kargo
            score += 20
            reasons.append(f"Kargo gemisi aşırı hız ({speed:.1f} knot)")

        # Rota sapması
        if "ROUTE_DEVIATION" in flags:
            score += 22
            reasons.append("Bildirilen güzergahtan sapma")

        score = min(score, 100)
        enriched["anomaly_score"]  = score
        enriched["risk_score"]     = score
        enriched["risk_level"]     = _classify_risk(score)
        enriched["anomaly_flag"]   = score >= 35
        enriched["flags"]          = flags
        enriched["anomaly_reason"] = (
            " — ".join(reasons[:2]) + "." if reasons else "Normal seyir profili."
        )
        result.append(enriched)
    return result


# ── IsolationForest yardımcısı ─────────────────────────────────────────────────

def _compute_ml_scores(aircraft_list: List[Dict[str, Any]]) -> List[float]:
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import MinMaxScaler
        import numpy as np

        features = []
        for ac in aircraft_list:
            features.append([
                float(ac.get("altitude", 0)) / 45000.0,
                float(ac.get("speed",    0)) / 1000.0,
                float(ac.get("heading",  0)) / 360.0,
                (float(ac.get("lat", 39)) - 25) / 30.0,
                (float(ac.get("lon", 35)) - 20) / 50.0,
            ])

        if len(features) < 10:
            return [0.0] * len(aircraft_list)

        X   = np.array(features)
        iso = IsolationForest(
            contamination=0.03,   # Sadece %3 anomali — gürültüyü çok azalttık
            n_estimators=100,
            random_state=42,
        )
        iso.fit(X)
        raw = iso.score_samples(X)
        # Katkı: maksimum 20 puan (sadece bir sinyal, sürücü değil)
        ml  = MinMaxScaler(feature_range=(0, 20)).fit_transform(
            (-raw).reshape(-1, 1)
        ).flatten()
        return [float(v) for v in ml]

    except ImportError:
        logger.warning("scikit-learn yok — ML katmanı devre dışı.")
    except Exception as e:
        logger.debug("IsolationForest hatası: %s", e)
    return [0.0] * len(aircraft_list)
