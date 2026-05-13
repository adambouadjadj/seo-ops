"""Client Textguru API V2 — brief sémantique + PAA + targets SOSEO/DSEO.

Spec complète dans reference/scoring_guidance.md.
Cache 7 jours dans cache/textguru/{md5(keyword)}.json.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

_BASE_URL  = "https://yourtext.guru/api/v2"
_LANG      = "fr_FR"   # format attendu par l'API Textguru V2
_TIMEOUT   = 20
_CACHE_TTL = 7 * 86400  # 7 jours

# Backoff polling guide ready: 10, 30, 60, 120, 300 secondes
_POLL_DELAYS = [10, 30, 60, 120, 300]


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_key(keyword: str) -> str:
    return hashlib.md5(keyword.lower().encode()).hexdigest()


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


# ── Requêtes HTTP ──────────────────────────────────────────────────────────────

def _ytg_api_key() -> str:
    key = os.environ.get("YTG_API", "")
    if not key:
        raise RuntimeError("Variable d'environnement YTG_API absente du .env")
    return key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_ytg_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get(path: str) -> dict:
    resp = requests.get(f"{_BASE_URL}{path}", headers=_headers(), timeout=_TIMEOUT)
    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict) -> dict:
    resp = requests.post(
        f"{_BASE_URL}{path}", headers=_headers(), json=body, timeout=_TIMEOUT
    )
    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


def _check_rate_limit(resp: requests.Response) -> None:
    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) == 0:
        reset_at = resp.headers.get("x-ratelimit-reset", "")
        raise RuntimeError(
            f"Textguru rate limit atteint. Reset : {reset_at}. "
            "Relancer le skill dans quelques minutes."
        )


# ── Gestion du guide ───────────────────────────────────────────────────────────

def _search_guide(keyword: str) -> str | None:
    """Cherche un guide existant par keyword. Retourne l'id ou None."""
    try:
        data = _get(f"/guides?q={requests.utils.quote(keyword)}")
        guides = data if isinstance(data, list) else data.get("guides", data.get("data", []))
        keyword_lower = keyword.lower()
        for g in guides:
            if isinstance(g, dict):
                g_query = g.get("query", g.get("keyword", "")).lower()
                if g_query == keyword_lower:
                    return str(g["id"])
    except Exception:
        pass
    return None


def _create_guide(keyword: str) -> str:
    """Crée un nouveau guide Textguru et retourne son id."""
    data = _post("/guides", {"query": keyword, "lang": _LANG, "type": "google"})
    guide_id = data.get("id") if isinstance(data, dict) else None
    if not guide_id:
        raise RuntimeError(f"Textguru : impossible de créer le guide pour '{keyword}'")
    return str(guide_id)


def _wait_for_ready(guide_id: str) -> dict:
    """Polle jusqu'à ce que le guide soit ready. Retourne la réponse complète."""
    for i, delay in enumerate(_POLL_DELAYS):
        print(f"         Textguru polling ({i+1}/{len(_POLL_DELAYS)}, attente {delay}s...)")
        time.sleep(delay)
        data = _get(f"/guides/{guide_id}")
        inner = data.get("data", data)
        if inner.get("ready") or inner.get("status") == "ready":
            return data  # réponse complète (targets en top-level)

    raise RuntimeError(
        f"Textguru guide {guide_id} pas ready après 5 tentatives (>= 10min). "
        "Réessayer plus tard ou utiliser --brief."
    )


# ── Parsing des données guide ──────────────────────────────────────────────────

def _parse_ngrams(inner: dict) -> dict:
    """Extrait 1grams, 2grams, 3grams depuis le sous-dict data du guide."""
    result: dict[str, list] = {"1grams": [], "2grams": [], "3grams": []}
    for key in ("1grams", "2grams", "3grams"):
        items = inner.get(key, [])
        if isinstance(items, list):
            result[key] = [
                item.get("word", item) if isinstance(item, dict) else item
                for item in items
            ]
    return result


def _parse_entities(inner: dict) -> list[str]:
    items = inner.get("entities", [])
    if not isinstance(items, list):
        return []
    return [
        item.get("entity", item) if isinstance(item, dict) else item
        for item in items
    ]


def _parse_targets(full_response: dict) -> dict:
    """Extrait les targets SOSEO/DSEO depuis le top-level de la réponse API."""
    return {
        "soseo_min": full_response.get("target_SOSEO_min") or full_response.get("target_soseo_min"),
        "soseo_max": full_response.get("target_SOSEO_max") or full_response.get("target_soseo_max"),
        "dseo_min":  full_response.get("target_DSEO_min")  or full_response.get("target_dseo_min"),
        "dseo_max":  full_response.get("target_DSEO_max")  or full_response.get("target_dseo_max"),
    }


def _parse_paa(paa_data) -> list[str]:
    """Normalise la réponse PAA en liste de questions."""
    if not paa_data:
        return []
    items = paa_data if isinstance(paa_data, list) else paa_data.get("paa", paa_data.get("data", []))
    questions = []
    for item in items:
        if isinstance(item, str):
            questions.append(item)
        elif isinstance(item, dict):
            q = item.get("question", item.get("title", item.get("text", "")))
            if q:
                questions.append(q)
    return questions


def _parse_serp(serp_data) -> list[dict]:
    """Normalise la réponse SERP Textguru."""
    if not serp_data:
        return []
    items = serp_data if isinstance(serp_data, list) else serp_data.get("serp", serp_data.get("data", []))
    results = []
    for item in items:
        if isinstance(item, dict):
            results.append({
                "rank":   item.get("rank") or item.get("position"),
                "url":    item.get("url"),
                "title":  item.get("title"),
                "domain": item.get("domain"),
                "words":  item.get("words") or item.get("word_count"),
            })
    return results


# ── Fonction principale ────────────────────────────────────────────────────────

def _fallback(keyword: str, error: str) -> dict:
    """Retourne un dict vide signalant l'indisponibilité Textguru."""
    print(f"         [WARNING] Textguru indisponible : {error}")
    print("         Fallback : pattern selector sur volume seul")
    return {
        "guide_id": None,
        "query":    keyword,
        "lang":     _LANG,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "keywords": {"1grams": [], "2grams": [], "3grams": []},
        "entities": [],
        "targets":  {"soseo_min": None, "soseo_max": None, "dseo_min": None, "dseo_max": None},
        "paa":      [],
        "serp":     [],
        "error":    error,
    }


def fetch_textguru(keyword: str, cache_dir: Path, refresh: bool = False) -> dict:
    """Récupère le brief sémantique Textguru pour un keyword.

    Cache 7j. Si refresh=True, invalide le cache.
    Retourne un dict de fallback en cas d'erreur (non-bloquant).
    """
    if not refresh:
        cached = _load_cache(cache_dir, keyword)
        if cached:
            guide_id = cached.get("guide_id", "?")
            print(f"         (cache Textguru — age < 7j, guide {guide_id})")
            cached.pop("_cached_at", None)
            return cached

    # Vérifier la clé API avant de tenter quoi que ce soit
    try:
        _ytg_api_key()
    except RuntimeError as e:
        return _fallback(keyword, str(e))

    try:
        return _fetch_live(keyword, cache_dir)
    except Exception as e:
        return _fallback(keyword, str(e))


def _fetch_live(keyword: str, cache_dir: Path) -> dict:
    """Fetch réel depuis l'API Textguru."""
    # 1. Chercher ou créer le guide
    guide_id = _search_guide(keyword)
    if guide_id:
        print(f"         Guide Textguru existant : {guide_id}")
        guide_full = _get(f"/guides/{guide_id}")
        inner = guide_full.get("data", guide_full)
        if not (inner.get("ready") or inner.get("status") == "ready"):
            print(f"         Guide {guide_id} pas encore ready, polling...")
            guide_full = _wait_for_ready(guide_id)
            inner = guide_full.get("data", guide_full)
    else:
        print(f"         Création du guide Textguru pour '{keyword}'...")
        guide_id = _create_guide(keyword)
        print(f"         Guide créé : {guide_id}, polling ready...")
        guide_full = _wait_for_ready(guide_id)
        inner = guide_full.get("data", guide_full)

    # 2. Récupérer PAA et SERP
    try:
        paa_raw  = _get(f"/guides/{guide_id}/paa")
    except Exception as e:
        print(f"         [WARNING] PAA Textguru indisponible : {e}")
        paa_raw  = []

    try:
        serp_raw = _get(f"/guides/{guide_id}/serp")
    except Exception as e:
        print(f"         [WARNING] SERP Textguru indisponible : {e}")
        serp_raw = []

    result = {
        "guide_id": guide_id,
        "query":    keyword,
        "lang":     _LANG,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "keywords": _parse_ngrams(inner),        # inner data : 1grams/2grams/3grams
        "entities": _parse_entities(inner),      # inner data : entities
        "targets":  _parse_targets(guide_full),  # top-level : target_SOSEO_*/target_DSEO_*
        "paa":      _parse_paa(paa_raw),
        "serp":     _parse_serp(serp_raw),
    }

    _save_cache(cache_dir, keyword, result)
    return result
