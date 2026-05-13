"""Fetch d'une SL ABCroisière et parsing HTML + JSON-LD.

Spec complète dans reference/extraction_selectors.md.
Cache HTML 24h dans cache/content/{md5(url)}.json.
"""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT    = 15
_CACHE_TTL  = 86400  # 24h en secondes


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{_cache_key(url)}.json"


def _load_cache(cache_dir: Path, url: str) -> dict | None:
    path = _cache_path(cache_dir, url)
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


def _save_cache(cache_dir: Path, url: str, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = time.time()
    _cache_path(cache_dir, url).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Fetch HTTP ─────────────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    resp = requests.get(
        url,
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} sur {url}")
    return resp.text


# ── Parsing JSON-LD ────────────────────────────────────────────────────────────

def _parse_jsonld_blocks(soup: BeautifulSoup) -> list[dict]:
    blocks = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            blocks.append(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            pass  # Skip blocs malformés, log dans anomalies
    return blocks


def _find_block(blocks: list[dict], type_name: str) -> dict | None:
    for b in blocks:
        if b.get("@type") == type_name:
            return b
    return None


def _normalize_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(" ", "").replace(" ", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_product(product: dict | None) -> dict:
    if not product:
        return {"offer_count": None, "low_price": None, "currency": None}
    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return {
        "offer_count": _normalize_int(offers.get("offerCount")),
        "low_price":   _normalize_int(offers.get("lowPrice")),
        "currency":    offers.get("priceCurrency"),
    }


def _parse_breadcrumb(breadcrumb: dict | None) -> list[dict]:
    if not breadcrumb:
        return []
    items = breadcrumb.get("itemListElement", [])
    result = []
    for item in items:
        nested = item.get("item", item)
        result.append({
            "position": item.get("position"),
            "name":     item.get("name") or nested.get("name", ""),
            "url":      nested.get("@id") or nested.get("url", ""),
        })
    return result


def _parse_events(blocks: list[dict]) -> tuple[int, list[str], list[str]]:
    """Extrait les ports de départ et destinations depuis les Events."""
    events = [b for b in blocks if b.get("@type") == "Event"]
    ports: set[str] = set()
    destinations: set[str] = set()

    for ev in events:
        location = ev.get("location", {})
        if isinstance(location, dict):
            addr = location.get("address", {})
            city = addr.get("addressLocality", "").strip()
            if city:
                ports.add(city)
        name = ev.get("name", "")
        for dest in re.split(r"[,/]", name):
            dest = dest.strip()
            if dest and len(dest) > 2:
                destinations.add(dest)

    return len(events), sorted(ports), sorted(destinations)


# ── Parsing HTML contenu ───────────────────────────────────────────────────────

def _extract_internal_links(html_fragment: str) -> list[dict]:
    """Extrait les liens internes relatifs d'un fragment HTML."""
    if not html_fragment:
        return []
    soup = BeautifulSoup(html_fragment, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            links.append({"href": href, "text": a.get_text(strip=True)})
    return links


def _get_inner_html(tag) -> str:
    if tag is None:
        return ""
    return tag.decode_contents()


def _detect_author_signature(destination_html: str) -> str | None:
    """Détecte la signature auteur dans le destination content."""
    if not destination_html:
        return None
    soup = BeautifulSoup(destination_html, "html.parser")
    for p in soup.find_all("p"):
        for span in p.find_all("span"):
            style = span.get("style", "")
            if "sprite.png" in style:
                # Le texte est dans le second span
                spans = p.find_all("span")
                if len(spans) >= 2:
                    return spans[-1].get_text(strip=True)
    return None


# ── Détection anomalies à l'extraction ────────────────────────────────────────

def _detect_extraction_anomalies(
    top_html: str,
    dest_html: str,
    h1: str,
    jsonld_blocks: list[dict],
) -> list[dict]:
    anomalies = []

    if not h1:
        anomalies.append({
            "check_id": "extraction_h1_missing",
            "severity": "HIGH",
            "code":     "h1_missing",
            "description": "H1 absent ou vide",
        })

    if not top_html:
        anomalies.append({
            "check_id": "extraction_top_content_missing",
            "severity": "MEDIUM",
            "code":     "top_content_missing",
            "description": "Container top content (.line-clamp-text) introuvable",
        })

    if not dest_html:
        anomalies.append({
            "check_id": "extraction_destination_content_missing",
            "severity": "MEDIUM",
            "code":     "destination_content_missing",
            "description": "Container destination content (.kv-blocSEO) introuvable",
        })

    # Détecter les variables CMS non injectées
    full_html = top_html + dest_html
    cms_vars = re.findall(r"\$\{[^}]+\}", full_html)
    for var in set(cms_vars):
        anomalies.append({
            "check_id": "extraction_cms_var_not_injected",
            "severity": "HIGH",
            "code":     "cms_variable_not_injected",
            "description": f"Variable CMS non injectée : {var}",
        })

    return anomalies


# ── Fonction principale ────────────────────────────────────────────────────────

def fetch_page(url: str, cache_dir: Path) -> dict:
    """Fetch une SL et retourne un dict structuré prêt pour diagnostics_runner.

    Cache 24h. Le cache est bypassé si inexistant ou expiré.
    """
    cached = _load_cache(cache_dir, url)
    if cached:
        print(f"         (cache HTML — age < 24h)")
        cached.pop("_cached_at", None)
        return cached

    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # ── Métadonnées ────────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "").strip() if meta_tag else ""

    h1_tag = soup.select_one("h1.kv-products-search-list-headTitle")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    # ── Top content ────────────────────────────────────────────────────────────
    top_container = soup.select_one(
        "div.kv-products-search-list-headSubtitle div.line-clamp-text"
    )
    top_html = _get_inner_html(top_container)
    top_p_count = len(BeautifulSoup(top_html, "html.parser").find_all("p")) if top_html else 0

    # ── Destination content ────────────────────────────────────────────────────
    dest_container = soup.select_one("div.kv-blocSEO-wrapper div.kv-blocSEO")
    dest_html = _get_inner_html(dest_container)
    dest_h3_count = len(BeautifulSoup(dest_html, "html.parser").find_all("h3")) if dest_html else 0

    # ── Liens internes existants (à préserver) ─────────────────────────────────
    all_existing_links = (
        _extract_internal_links(top_html)
        + _extract_internal_links(dest_html)
    )
    # Dédupliquer par href
    seen_hrefs: set[str] = set()
    internal_links_existing = []
    for link in all_existing_links:
        if link["href"] not in seen_hrefs:
            seen_hrefs.add(link["href"])
            internal_links_existing.append(link)

    # ── Signature auteur ───────────────────────────────────────────────────────
    author_signature = _detect_author_signature(dest_html)

    # ── JSON-LD ────────────────────────────────────────────────────────────────
    jsonld_blocks = _parse_jsonld_blocks(soup)
    product_block    = _find_block(jsonld_blocks, "Product")
    breadcrumb_block = _find_block(jsonld_blocks, "BreadcrumbList")
    events_count, ports_depart, destinations = _parse_events(jsonld_blocks)

    # ── Anomalies à l'extraction ───────────────────────────────────────────────
    anomalies = _detect_extraction_anomalies(top_html, dest_html, h1, jsonld_blocks)

    result = {
        "url":         url,
        "fetched_at":  datetime.now(timezone.utc).isoformat(),
        "title":       title,
        "meta_description": meta_description,
        "h1":          h1,
        "top_content_html":             top_html,
        "top_content_paragraphs_count": top_p_count,
        "destination_content_html":             dest_html,
        "destination_content_h3_count": dest_h3_count,
        "author_signature":    author_signature,
        "internal_links_existing": internal_links_existing,
        "schema": {
            "product":   _parse_product(product_block),
            "breadcrumb": _parse_breadcrumb(breadcrumb_block),
            "events_count":              events_count,
            "ports_depart":              ports_depart,
            "destinations_mentionnees":  destinations,
        },
        "anomalies_detected": anomalies,
    }

    _save_cache(cache_dir, url, result)
    return result
