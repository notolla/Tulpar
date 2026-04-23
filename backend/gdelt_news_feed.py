"""
OSINT News Feed Adapter — SkySentinel AI
=========================================
RSS tabanlı haber beslemesi. Defense News, Reuters, BBC ve Jane's gibi
askeri/havacılık odaklı kaynaklardan gerçek zamanlı haber çeker.

scalable_api.py ile arayüz: get_news(fallback) ve run_background_task()
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import aiohttp

logger = logging.getLogger(__name__)

FETCH_INTERVAL  = int(os.getenv("NEWS_INTERVAL_SECONDS", "900"))  # 15 dakika
REQUEST_TIMEOUT = 10  # saniye
NEWSAPI_KEY     = os.getenv("NEWSAPI_KEY", "")  # ilk değer; fetch sırasında tekrar okunur

# ── Haber kaynakları ──────────────────────────────────────────────────────────
_SOURCES = [
    {
        "url":      "https://www.defensenews.com/arc/outboundfeeds/rss/",
        "name":     "Defense News",
        "category": "Savunma",
        "filter":   None,
    },
    {
        "url":      "https://maritime-executive.com/articles.rss",
        "name":     "Maritime Executive",
        "category": "Denizcilik",
        "filter":   None,
    },
    {
        "url":      "https://theaviationist.com/feed/",
        "name":     "The Aviationist",
        "category": "Havacılık",
        "filter":   None,
    },
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate",
}

# ── Kategori / bölge çıkarımı ─────────────────────────────────────────────────
_CATEGORY_MAP = [
    (r"aviation|aircraft|airspace|notam|flight|airline|pilot|helicopter", "Havacılık"),
    (r"naval|navy|warship|submarine|fleet|destroyer|frigate|carrier|ship", "Denizcilik"),
    (r"cyber|hack|malware|ransomware|breach|espionage",                    "Siber"),
    (r"sanction|embargo|diplomacy|treaty|negotiat|summit",                 "Diplomasi"),
    (r"missile|nuclear|weapon|airstrike|bombing|artillery",                "Füze/Silah"),
    (r"military|army|troops|combat|war|conflict|soldier|defense|NATO",     "Savunma"),
]

# Eşleme mantığı: spesifik aktörler/ülkeler → geniş jeopolitik bölge.
# Sıralama önemli — ilk eşleşen döner, en spesifik üstte olmalı.
_REGION_MAP = [
    # ── Türkiye ───────────────────────────────────────────────────────────────
    (r"turkey|turkish|türk|ankara|erdogan|bosphorus|bosporus", "Türkiye"),

    # ── Ukrayna / Rusya ───────────────────────────────────────────────────────
    (r"ukraine|ukrainian|kyiv|zelensky|mariupol|kharkiv|odesa", "Ukrayna"),
    (r"russia|russian|moscow|kremlin|putin|wagner|kursk",        "Rusya"),

    # ── Körfez (İran, Irak, Körfez ülkeleri, Hürmüz dahil) ───────────────────
    (r"iran|iranian|tehran|khamenei|irgc|hormuz|persian gulf|"
     r"iraq|baghdad|kuwait|bahrain|qatar|oman|uae|emirates",     "Körfez"),

    # ── Kızıldeniz / Yemen / Husi ─────────────────────────────────────────────
    (r"red sea|houthi|houthis|yemen|yemeni|aden|suez",           "Kızıldeniz"),

    # ── İsrail / Filistin / Lübnan / Suriye ──────────────────────────────────
    (r"israel|israeli|gaza|palestine|palestinian|hamas|hezbollah|"
     r"lebanon|lebanese|syria|syrian|damascus|west bank",         "Orta Doğu"),

    # ── Suudi Arabistan / Körfez ülkeleri (İran yoksa) ───────────────────────
    (r"saudi|riyadh|arabia|jordan|jordanian",                     "Orta Doğu"),

    # ── Karadeniz / Kırım ────────────────────────────────────────────────────
    (r"black sea|crimea|crimean",                                 "Karadeniz"),

    # ── Ege / Doğu Akdeniz / Yunanistan ──────────────────────────────────────
    (r"aegean|greece|greek|cyprus|mediterranean",                 "Ege/Akdeniz"),

    # ── Çin / Tayvan / Güney Çin Denizi ──────────────────────────────────────
    (r"china|chinese|taiwan|taiwanese|beijing|xi jinping|"
     r"south china sea|pla|people.s liberation",                  "Çin/Tayvan"),

    # ── Kore Yarımadası ───────────────────────────────────────────────────────
    (r"korea|korean|pyongyang|seoul|kim jong",                    "Kore"),

    # ── Japonya / Pasifik ─────────────────────────────────────────────────────
    (r"japan|japanese|tokyo|indo.pacific|pacific command",        "Japonya/Pasifik"),

    # ── Güney Asya ────────────────────────────────────────────────────────────
    (r"india|indian|pakistan|pakistani|afghanistan|afghan|kashmir", "Güney Asya"),

    # ── NATO / Avrupa ─────────────────────────────────────────────────────────
    (r"nato|germany|german|france|french|britain|british|uk |"
     r"poland|polish|finland|finland|sweden|swedish|"
     r"baltic|estonia|latvia|lithuania|norway|danish|denmark",    "NATO/Avrupa"),

    # ── Balkanlar ─────────────────────────────────────────────────────────────
    (r"balkans|serbia|serbian|kosovo|bosnia|croatia|albania",     "Balkanlar"),

    # ── ABD / Pentagon ────────────────────────────────────────────────────────
    (r"pentagon|u\.s\. military|us military|us army|us navy|us air force|"
     r"joint chiefs|secretary of defense|congress|senate",         "ABD"),

    # ── Afrika ────────────────────────────────────────────────────────────────
    (r"africa|sahel|mali|niger|nigeria|sudan|somalia|ethiopia|"
     r"libya|libyan|mozambique|angola",                            "Afrika"),

    # ── Orta Asya ─────────────────────────────────────────────────────────────
    (r"central asia|kazakhstan|uzbekistan|tajikistan|kyrgyz",     "Orta Asya"),
]


def _infer_category(title: str, default: Optional[str]) -> str:
    t = title.lower()
    for pattern, cat in _CATEGORY_MAP:
        if re.search(pattern, t):
            return cat
    return default or "İstihbarat"


def _infer_region(title: str) -> str:
    t = title.lower()
    for pattern, region in _REGION_MAP:
        if re.search(pattern, t):
            return region
    return "Global"


def _stable_id(url: str) -> str:
    return "r-" + hashlib.md5(url.encode()).hexdigest()[:8]


def _parse_pub_date(raw: str) -> str:
    """RFC 2822 tarih → 'HH:MM UTC' formatı."""
    try:
        dt = parsedate_to_datetime(raw).astimezone(timezone.utc)
        return dt.strftime("%H:%M UTC")
    except Exception:
        return ""


def _extract_text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


# ── RSS çekici ────────────────────────────────────────────────────────────────

async def _fetch_rss(session: aiohttp.ClientSession, source: Dict) -> List[Dict[str, Any]]:
    try:
        async with session.get(source["url"], headers=_HEADERS) as resp:
            if resp.status != 200:
                logger.warning("%s HTTP %s", source["name"], resp.status)
                return []
            xml_text = await resp.text(errors="replace")
    except asyncio.TimeoutError:
        logger.warning("%s zaman aşımı", source["name"])
        return []
    except Exception as e:
        logger.warning("%s hata: %s", source["name"], e)
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("%s XML parse hatası: %s", source["name"], e)
        return []

    atom_ns = "http://www.w3.org/2005/Atom"
    is_atom = atom_ns in (root.tag or "")
    limit   = int(os.getenv("NEWS_PER_SOURCE", "50"))

    if is_atom:
        ns_map  = {"a": atom_ns}
        entries = root.findall("a:entry", ns_map)

        def _title(e: ET.Element) -> str:
            return _extract_text(e.find("a:title", ns_map))

        def _url(e: ET.Element) -> str:
            lnk = e.find("a:link[@rel='alternate']", ns_map) or e.find("a:link", ns_map)
            return (lnk.get("href") or "") if lnk is not None else ""

        def _desc(e: ET.Element) -> str:
            return _extract_text(e.find("a:summary", ns_map)) or _extract_text(e.find("a:content", ns_map))

        def _pub(e: ET.Element) -> str:
            raw = _extract_text(e.find("a:published", ns_map)) or _extract_text(e.find("a:updated", ns_map))
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                return dt.strftime("%H:%M UTC")
            except Exception:
                return ""
    else:
        entries = root.findall(".//item")

        def _title(e: ET.Element) -> str:  # type: ignore[misc]
            return _extract_text(e.find("title"))

        def _url(e: ET.Element) -> str:  # type: ignore[misc]
            return _extract_text(e.find("link")) or _extract_text(e.find("guid"))

        def _desc(e: ET.Element) -> str:  # type: ignore[misc]
            return _extract_text(e.find("description"))

        def _pub(e: ET.Element) -> str:  # type: ignore[misc]
            return _parse_pub_date(_extract_text(e.find("pubDate")))

    results = []
    for entry in entries[:limit]:
        title = _title(entry)
        url   = _url(entry)
        desc  = _desc(entry)
        pub   = _pub(entry)

        if not title or not url:
            continue

        summary = re.sub(r"<[^>]+>", "", desc)[:160].strip() or None

        if source["filter"] and not re.search(source["filter"], title.lower()):
            continue

        results.append({
            "id":       _stable_id(url),
            "title":    title,
            "source":   source["name"],
            "time":     pub,
            "category": _infer_category(title, source["category"]),
            "region":   _infer_region(title),
            "summary":  summary,
            "url":      url,
        })

    return results


async def fetch_news_from_rss() -> Optional[List[Dict[str, Any]]]:
    """Tüm kaynaklardan paralel çek, birleştir, tarihe göre sırala."""
    timeout    = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    connector  = aiohttp.TCPConnector(ssl=False)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            batches = await asyncio.gather(
                *[_fetch_rss(session, src) for src in _SOURCES],
                return_exceptions=True,
            )
    except Exception as e:
        logger.error("RSS session hatası: %s", e)
        return None

    all_items: List[Dict[str, Any]] = []
    for batch in batches:
        if isinstance(batch, list):
            all_items.extend(batch)

    if not all_items:
        return None

    # Duplicate URL temizle
    seen: set = set()
    unique = []
    for item in all_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    logger.info("RSS: %d kaynak → %d haber çekildi", len(_SOURCES), len(unique))
    return unique


# ── NewsAPI.org entegrasyonu ──────────────────────────────────────────────────

_NEWSAPI_QUERY = (
    "(airstrike OR warship OR missile OR troops OR blockade OR "
    "military operation OR naval exercise OR drone strike OR "
    "nuclear warhead OR arms deal OR ceasefire OR invasion OR "
    "NATO forces OR air force OR fighter jet OR submarine OR "
    "sanctions regime OR geopolitical OR artillery OR "
    "Pentagon OR defense ministry OR strategic bomber)"
)

_NEWSAPI_SOURCES = (
    "bbc-news,reuters,associated-press,the-washington-post,"
    "al-jazeera-english,the-guardian-uk,defense-news,abc-news,"
    "cnn,bloomberg,time,newsweek"
)


async def fetch_news_from_newsapi() -> Optional[List[Dict[str, Any]]]:
    """NewsAPI.org /v2/everything endpoint — NEWSAPI_KEY gerekli."""
    api_key = os.getenv("NEWSAPI_KEY", "")   # her çağrıda taze oku
    if not api_key:
        return None

    params = {
        "q":          _NEWSAPI_QUERY,
        "language":   "en",
        "sortBy":     "publishedAt",
        "pageSize":   int(os.getenv("NEWS_PER_SOURCE", "50")),
        "apiKey":     api_key,
    }
    # Belirli kaynaklar varsa ekle (q ile birlikte kullanılamıyor — ikisinden biri)
    # NewsAPI kısıtı: sources + q birlikte kullanılırsa hata verir
    # Bu yüzden sadece q kullanıyoruz, sources filtresi kaldırıldı.

    timeout   = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    connector = aiohttp.TCPConnector(ssl=False)
    url       = "https://newsapi.org/v2/everything"

    _newsapi_headers = {"Accept-Encoding": "gzip, deflate"}

    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as s:
            async with s.get(url, params=params, headers=_newsapi_headers) as resp:
                if resp.status == 401:
                    logger.error("NewsAPI: geçersiz API key")
                    return None
                if resp.status == 429:
                    logger.warning("NewsAPI: rate limit aşıldı")
                    return None
                if resp.status != 200:
                    logger.warning("NewsAPI HTTP %s", resp.status)
                    return None
                data = await resp.json(content_type=None)
    except Exception as e:
        logger.error("NewsAPI bağlantı hatası: %s", e)
        return None

    if data.get("status") != "ok":
        logger.warning("NewsAPI hata: %s", data.get("message", "bilinmiyor"))
        return None

    articles = data.get("articles") or []
    results  = []

    for art in articles:
        title = (art.get("title") or "").strip()
        url_  = (art.get("url")   or "").strip()
        desc  = (art.get("description") or art.get("content") or "").strip()
        pub   = art.get("publishedAt", "")
        src   = (art.get("source") or {}).get("name", "NewsAPI")

        if not title or not url_ or title == "[Removed]":
            continue

        # ISO tarih → HH:MM UTC
        try:
            dt   = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc)
            time_ = dt.strftime("%H:%M UTC")
        except Exception:
            time_ = ""

        summary = re.sub(r"<[^>]+>", "", desc)[:160].strip() or None

        results.append({
            "id":       _stable_id(url_),
            "title":    title,
            "source":   src,
            "time":     time_,
            "category": _infer_category(title, None),
            "region":   _infer_region(title),
            "summary":  summary,
            "url":      url_,
        })

    logger.info("NewsAPI: %d makale çekildi", len(results))
    return results if results else None


# ── Modül düzeyinde store ─────────────────────────────────────────────────────

_store:    List[Dict[str, Any]] = []
_store_ts: float = 0.0
_fetch_lock = asyncio.Lock()


async def _do_fetch() -> None:
    global _store, _store_ts
    async with _fetch_lock:
        if _store and (time.time() - _store_ts) < 30:
            return

        # NewsAPI + RSS paralel çek, birleştir
        newsapi_result, rss_result = await asyncio.gather(
            fetch_news_from_newsapi(),
            fetch_news_from_rss(),
            return_exceptions=True,
        )

        combined: List[Dict[str, Any]] = []
        if isinstance(newsapi_result, list) and newsapi_result:
            combined.extend(newsapi_result)
        if isinstance(rss_result, list) and rss_result:
            combined.extend(rss_result)

        # URL bazlı duplicate temizle
        seen: set = set()
        news = []
        for item in combined:
            if item.get("url") not in seen:
                seen.add(item["url"])
                news.append(item)

        if news:
            _store    = news
            _store_ts = time.time()
            na = len(newsapi_result) if isinstance(newsapi_result, list) else 0
            rs = len(rss_result)     if isinstance(rss_result, list)     else 0
            logger.info("OSINT store güncellendi: %d haber (NewsAPI=%d RSS=%d)", len(news), na, rs)


async def _background_refresh() -> None:
    try:
        await _do_fetch()
    except Exception as e:
        logger.error("OSINT arka plan yenileme hatası: %s", e)


async def get_news(fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """scalable_api.api_news() tarafından çağrılır."""
    now   = time.time()
    stale = (now - _store_ts) > FETCH_INTERVAL

    if _store:
        if stale and not _fetch_lock.locked():
            asyncio.ensure_future(_background_refresh())
        return list(_store)

    if not _fetch_lock.locked():
        asyncio.ensure_future(_background_refresh())
    return list(fallback)


async def force_refresh() -> int:
    """Manuel yenileme — 30 saniyelik guard'ı atlar, yeni haber sayısını döner."""
    global _store, _store_ts
    async with _fetch_lock:
        na, rs = await asyncio.gather(fetch_news_from_newsapi(), fetch_news_from_rss(), return_exceptions=True)
        combined = []
        for batch in (na, rs):
            if isinstance(batch, list): combined.extend(batch)
        seen: set = set()
        news = [i for i in combined if not (i["url"] in seen or seen.add(i["url"]))]  # type: ignore
        if news:
            _store    = news
            _store_ts = time.time()
            logger.info("Manuel yenileme: %d haber", len(news))
            return len(news)
    return len(_store)


async def run_background_task(cache=None) -> None:
    """FastAPI lifespan içinde asyncio.create_task() ile çağrılır."""
    while True:
        try:
            await _do_fetch()
        except Exception as e:
            logger.error("OSINT arka plan görev hatası: %s", e)
        wait = 30 if not _store else FETCH_INTERVAL
        await asyncio.sleep(wait)


# ── Bağımsız test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    async def _once():
        news = await fetch_news_from_rss()
        if news:
            print(json.dumps(news[:3], ensure_ascii=False, indent=2))
            print(f"\nToplam: {len(news)} haber")
        else:
            print("Haber çekilemedi.")

    asyncio.run(_once())
