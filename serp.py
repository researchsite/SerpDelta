import os
import json
import time
import hashlib
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from serpapi import GoogleSearch

CACHE_DIR = pathlib.Path(__file__).parent / "serp_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_ttl_seconds() -> float:
    try:
        return float(os.getenv("SERP_CACHE_TTL_HOURS", "24")) * 3600
    except ValueError:
        return 86400.0


def _cache_path(query: str) -> pathlib.Path:
    key = hashlib.md5(query.strip().lower().encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def is_disk_cached(query: str) -> bool:
    path = _cache_path(query)
    if not path.exists():
        return False
    return (time.time() - path.stat().st_mtime) <= _cache_ttl_seconds()


def _load_from_cache(query: str) -> dict | None:
    if not is_disk_cached(query):
        return None
    with _cache_path(query).open(encoding="utf-8") as f:
        return json.load(f)


def _save_to_cache(query: str, data: dict) -> None:
    with _cache_path(query).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _fetch_search(query: str, key: str) -> dict:
    result = GoogleSearch({
        "q": query, "api_key": key, "num": 5, "hl": "en", "gl": "us",
    }).get_dict()

    snippets = [
        {"title": r.get("title",""), "snippet": r.get("snippet",""),
         "link": r.get("link",""), "date": r.get("date","")}
        for r in result.get("organic_results", [])[:5]
    ]
    paa = [i.get("question","") for i in result.get("related_questions",[])[:4]]
    kg  = result.get("knowledge_graph", {})
    knowledge_graph = {
        "title": kg.get("title",""), "type": kg.get("type",""),
        "description": kg.get("description",""),
    } if kg else {}

    return {"snippets": snippets, "paa": paa, "knowledge_graph": knowledge_graph}


def _fetch_news(query: str, key: str) -> list:
    result = GoogleSearch({
        "q": query, "api_key": key, "tbm": "nws", "num": 4,
    }).get_dict()
    return [
        {"title": r.get("title",""), "source": r.get("source",""),
         "date": r.get("date",""), "link": r.get("link",""),
         "snippet": r.get("snippet","")}
        for r in result.get("news_results", [])[:4]
    ]


def get_live_context(query: str, serpapi_key: str = "") -> dict:
    """Fetch live web context. Disk-cached when available. Search + News run in parallel."""
    cached = _load_from_cache(query)
    if cached is not None:
        return cached

    key = serpapi_key or os.getenv("SERPAPI_KEY")

    # Run both SerpApi calls in parallel — cuts total time roughly in half
    with ThreadPoolExecutor(max_workers=2) as pool:
        search_future = pool.submit(_fetch_search, query, key)
        news_future   = pool.submit(_fetch_news,   query, key)
        search_data   = search_future.result()
        headlines     = news_future.result()

    data = {
        "snippets":        search_data["snippets"],
        "paa":             search_data["paa"],
        "headlines":       headlines,
        "knowledge_graph": search_data["knowledge_graph"],
    }
    _save_to_cache(query, data)
    return data
