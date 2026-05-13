"""Client DataForSEO SERP Google Organic Live Advanced.

Spec complète dans reference/dataforseo_api.md.
Cache 7 jours dans cache/dataforseo/{md5(keyword+params)}.json.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

_ENDPOINT      = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
_LOCATION_CODE = 2250    # France
_LANG          = "fr"
_DEVICE        = "desktop"
_DEPTH         = 20
_TIMEOUT       = 30
_CACHE_TTL     = 7 * 86400  # 7 jours

# Concurrents directs (reference/concurrents_directs.md)
_OTA_DIRECTS = [
    "destockagecroisieres.fr",
    "croisieres.fr",
    "croisieres.com",
    "logitravel.fr",
    "croisierenet.com",
    "centralcruise.com",
    "okcroisiere.fr",
    "voyages.carrefour.fr",
    "croisiland.com",
    "croisiere.promovacances.com",
]

_ARMATEURS: dict[str, str] = {
    "msccroisieres.fr":       "MSC",
    "costacroisieres.fr":     "Costa",
    "royalcaribbean.com":     "Royal Caribbean",
    "celebritycruises.com":   "Celebrity",
    "cunard-france.fr":       "Cunard",
    "croisieurope.com":       "Croisieurope",
    "cfc-croisieres.fr":      "CFC",
    "ponant.com":             "Ponant",
    "rivagesdumonde.fr":      "Rivages du Monde",
    "clubmed.fr":             "Club Med",
}

_GUIDES_INFORMATIONNELS = [
    "tripadvisor", "routard", "lonelyplanet", "linternaute",
    "geo.fr", "evasions.com", "futura-sciences", "magazine",
    "blog", "guide",
]


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_key(keyword: str) -> str:
    raw = f"{keyword.lower()}|{_LOCATION_CODE}|{_LANG}|{_DEVICE}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(cache_dir: Path, keyword: str) -> Path:
    return cache_dir / f"{_cache_key(keyword)}.json"


def _load_cache(cache_dir: Path, keyword: str) -> dict | None:
    path = _cache_path(cache_dir, keyword)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data.get("_cached_at", 0)
        if age > _CACHE_TTL:
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


def _save_cache(cache_dir: Path, keyword: str, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = time.time()
    _cache_path(cache_dir, keyword).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Auth ───────────────────────────────────────────────────────────────────────

def _auth() -> HTTPBasicAuth:
    login    = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    if not login or not password:
        raise RuntimeError(
            "Variables DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD absentes du .env"
        )
    return HTTPBasicAuth(login, password)


# ── Requête API ────────────────────────────────────────────────────────────────

def _call_api(keyword: str) -> dict:
    payload = [{
        "keyword":       keyword,
        "location_code": _LOCATION_CODE,
        "language_code": _LANG,
        "device":        _DEVICE,
        "depth":         _DEPTH,
    }]

    resp = requests.post(
        _ENDPOINT,
        auth=_auth(),
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=_TIMEOUT,
    )

    if resp.status_code == 429:
        print("         [WARNING] DataForSEO rate limit 429, attente 60s...")
        time.sleep(60)
        resp = requests.post(
            _ENDPOINT,
            auth=_auth(),
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=_TIMEOUT,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"DataForSEO HTTP {resp.status_code}")

    data = resp.json()
    if data.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO API {data.get('status_code')}: {data.get('status_message')}"
        )

    tasks = data.get("tasks", [])
    if not tasks:
        raise RuntimeError("DataForSEO : pas de tasks dans la réponse")

    task = tasks[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO task {task.get('status_code')}: {task.get('status_message')}"
        )

    result = task["result"][0]
    cost   = task.get("cost", 0)
    print(f"         DataForSEO cost : ${cost:.4f}")

    return result


# ── Parsing ────────────────────────────────────────────────────────────────────

def _classify_domain(domain: str) -> str:
    d = domain.lower()
    for ota in _OTA_DIRECTS:
        if ota in d:
            return "ota_direct"
    for arm_domain in _ARMATEURS:
        if arm_domain in d:
            return "armateur"
    for guide_kw in _GUIDES_INFORMATIONNELS:
        if guide_kw in d:
            return "informationnel"
    return "autre"


def _parse_organic(items: list[dict]) -> tuple[list[dict], list[dict]]:
    organic_results = []
    for item in items:
        if item.get("type") != "organic":
            continue
        domain   = item.get("domain", "")
        category = _classify_domain(domain)
        organic_results.append({
            "rank_group":          item.get("rank_group"),
            "rank_absolute":       item.get("rank_absolute"),
            "domain":              domain,
            "url":                 item.get("url"),
            "title":               item.get("title"),
            "description":         item.get("description"),
            "website_name":        item.get("website_name"),
            "is_featured_snippet": item.get("is_featured_snippet", False),
            "category":            category,
            "has_faq":             item.get("faq") is not None,
        })

    concurrents_directs = [
        r for r in organic_results
        if r["category"] in ("ota_direct", "armateur")
    ]
    return organic_results, concurrents_directs


def _parse_paa(items: list[dict]) -> dict:
    paa_blocks = [i for i in items if i.get("type") == "people_also_ask"]
    if not paa_blocks:
        return {"present": False, "count": 0, "questions": []}

    elements  = paa_blocks[0].get("items", [])
    questions = []
    for elem in elements:
        expanded    = elem.get("expanded_element", [])
        answer_data = expanded[0] if expanded else {}
        questions.append({
            "question":           elem.get("title", ""),
            "seed_question":      elem.get("seed_question", ""),
            "answer_title":       answer_data.get("title", ""),
            "answer_description": answer_data.get("description", ""),
            "answer_url":         answer_data.get("url", ""),
            "answer_domain":      answer_data.get("domain", ""),
            "has_table":          answer_data.get("table") is not None,
        })

    return {"present": True, "count": len(questions), "questions": questions}


def _parse_featured_snippet(items: list[dict]) -> dict:
    fs_items = [i for i in items if i.get("type") == "featured_snippet"]
    if not fs_items:
        return {"present": False}
    fs = fs_items[0]
    return {
        "present":        True,
        "domain":         fs.get("domain", ""),
        "url":            fs.get("url", ""),
        "title":          fs.get("title", ""),
        "featured_title": fs.get("featured_title", ""),
        "description":    fs.get("description", ""),
        "has_table":      fs.get("table") is not None,
        "has_images":     bool(fs.get("images")),
    }


def _parse_ai_overview(items: list[dict]) -> dict:
    ai_items = [i for i in items if i.get("type") == "ai_overview"]
    if not ai_items:
        return {"present": False}
    ai = ai_items[0]
    references = []
    for component in ai.get("items", []):
        if component.get("type") == "ai_overview_element":
            for ref in component.get("references", []):
                references.append({
                    "source": ref.get("source", ""),
                    "domain": ref.get("domain", ""),
                    "url":    ref.get("url", ""),
                    "title":  ref.get("title", ""),
                })
    return {
        "present":      True,
        "asynchronous": ai.get("asynchronous_ai_overview", False),
        "markdown":     ai.get("markdown", ""),
        "references":   references,
    }


def _parse_related_searches(items: list[dict]) -> list[str]:
    rs_items = [i for i in items if i.get("type") == "related_searches"]
    if not rs_items:
        return []
    raw = rs_items[0].get("items", [])
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            q = item.get("query", item.get("title", ""))
            if q:
                result.append(q)
    return result


def _parse_competitors_with_faq(organic_results: list[dict], items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        if item.get("type") != "organic" or item.get("faq") is None:
            continue
        faq_items = item["faq"].get("items", [])
        result.append({
            "domain":         item.get("domain"),
            "rank":           item.get("rank_group"),
            "faq_count":      len(faq_items),
            "faq_questions":  [q.get("title", "") for q in faq_items],
        })
    return result


def _count_concurrents(organic_results: list[dict]) -> dict:
    counts: dict[str, int] = {"ota_direct": 0, "armateur": 0, "informationnel": 0, "autre": 0}
    for r in organic_results:
        cat = r.get("category", "autre")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# ── Fonction principale ────────────────────────────────────────────────────────

def fetch_serp(keyword: str, cache_dir: Path, refresh: bool = False) -> dict:
    """Récupère et parse la SERP DataForSEO pour un keyword.

    Cache 7j. Si refresh=True, invalide le cache.
    En cas d'erreur API, retourne un dict vide signalant le fallback.
    """
    if not refresh:
        cached = _load_cache(cache_dir, keyword)
        if cached:
            print(f"         (cache DataForSEO — age < 7j)")
            cached.pop("_cached_at", None)
            return cached

    try:
        result = _call_api(keyword)
    except Exception as e:
        print(f"         [WARNING] DataForSEO indisponible : {e}")
        print("         Fallback : pattern selector sur volume Textguru uniquement")
        fallback = {
            "keyword":            keyword,
            "fetched_at":         datetime.now(timezone.utc).isoformat(),
            "error":              str(e),
            "organic_results":    [],
            "concurrents_directs": [],
            "concurrents_count":  {"ota_direct": 0, "armateur": 0, "informationnel": 0, "autre": 0},
            "competitors_with_faq": [],
            "paa":                {"present": False, "count": 0, "questions": []},
            "featured_snippet":   {"present": False},
            "ai_overview":        {"present": False},
            "related_searches":   [],
            "item_types":         [],
        }
        return fallback

    items      = result.get("items", [])
    item_types = result.get("item_types", [])

    organic_results, concurrents_directs = _parse_organic(items)

    parsed = {
        "keyword":             keyword,
        "fetched_at":          datetime.now(timezone.utc).isoformat(),
        "check_url":           result.get("check_url", ""),
        "organic_results":     organic_results,
        "concurrents_directs": concurrents_directs,
        "concurrents_count":   _count_concurrents(organic_results),
        "competitors_with_faq": _parse_competitors_with_faq(organic_results, items),
        "paa":                 _parse_paa(items),
        "featured_snippet":    _parse_featured_snippet(items),
        "ai_overview":         _parse_ai_overview(items),
        "related_searches":    _parse_related_searches(items),
        "item_types":          item_types,
    }

    _save_cache(cache_dir, keyword, parsed)
    return parsed
