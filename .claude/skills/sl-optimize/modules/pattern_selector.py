"""Sélection automatique du pattern éditorial A/B/C.

Spec complète dans reference/pattern_selector.md.
"""

import re

# Seuils de scoring (reference/pattern_selector.md)
_VOLUME_HIGH   = 5000
_VOLUME_MEDIUM = 1000
_OTA_TOP10_MIN = 5    # >= 5 OTA dans top 10 → signal Pattern A
_PAA_MIN_B     = 3    # >= 3 PAA → signal Pattern B
_PAA_MAX_A     = 2    # <= 2 PAA → signal Pattern A

# Seuils offer_count (proxy volume fiable — pas de plafond API)
_OFFER_COUNT_HIGH   = 400   # >= 400 → volume élevé (Pattern A)
_OFFER_COUNT_MEDIUM = 80    # 80-400 → volume moyen (Pattern B)
# < 80 → volume faible, signal fort Pattern C

_INTERROGATIFS = re.compile(
    r"\b(comment|quand|quelle?s?|o[uù]|pourquoi|combien)\b",
    re.IGNORECASE,
)


# ── Extraction des signaux ─────────────────────────────────────────────────────

def _organic_top10(serp: dict) -> list[dict]:
    """Résultats organiques de rang 1 à 10."""
    return [
        r for r in serp.get("organic_results", [])
        if (r.get("rank_group") or 99) <= 10
    ]


def _ota_count_top10(serp: dict) -> int:
    top10 = _organic_top10(serp)
    return sum(1 for r in top10 if r.get("category") == "ota_direct")


def _guide_count_top10(serp: dict) -> int:
    top10 = _organic_top10(serp)
    return sum(1 for r in top10 if r.get("category") == "informationnel")


def _avg_content_length_top3(serp: dict) -> float | None:
    """Longueur moyenne du contenu des 3 premiers résultats Textguru SERP."""
    serp_data = serp.get("serp", [])
    if not serp_data:
        return None
    top3 = [r for r in serp_data if (r.get("rank") or 99) <= 3 and r.get("words")]
    if not top3:
        return None
    return sum(r["words"] for r in top3) / len(top3)


def _avg_content_length_top10(serp: dict) -> float | None:
    serp_data = serp.get("serp", [])
    if not serp_data:
        return None
    top10 = [r for r in serp_data if (r.get("rank") or 99) <= 10 and r.get("words")]
    if not top10:
        return None
    return sum(r["words"] for r in top10) / len(top10)


def _volume_from_catalogue(offer_count: int | None) -> int | None:
    """Proxy volume depuis l'offer_count catalogue.

    Plus fiable que le nombre de grams Textguru (l'API plafonne à 20 par
    catégorie, ce qui rend tous les keywords >= 60 grams → 6000 par défaut).
    L'offer_count vient du schema JSON-LD ou du brief — pas de plafond.
    """
    if offer_count is None:
        return None
    if offer_count >= _OFFER_COUNT_HIGH:
        return 6000
    if offer_count >= _OFFER_COUNT_MEDIUM:
        return 2500
    return 500


def _keyword_is_interrogatif(keyword: str) -> bool:
    return bool(_INTERROGATIFS.search(keyword))


# ── Algorithme scoring ─────────────────────────────────────────────────────────

def _score_pattern_a(signals: dict) -> int:
    score = 0
    if (signals["volume"] or 0) >= _VOLUME_HIGH:
        score += 1
    if (signals["ota_top10"] or 0) >= _OTA_TOP10_MIN:
        score += 1
    if (signals["avg_top3_words"] or 0) > 1500:
        score += 1
    # Featured snippet absent ou type paragraphe (pas liste/tableau)
    fs = signals.get("featured_snippet", {})
    if not fs.get("present") or not fs.get("has_table"):
        score += 1
    if (signals["paa_count"] or 0) <= _PAA_MAX_A:
        score += 1
    return score


def _score_pattern_b(signals: dict) -> int:
    score = 0
    if (signals["paa_count"] or 0) >= _PAA_MIN_B:
        score += 1
    fs = signals.get("featured_snippet", {})
    if fs.get("present") and fs.get("has_table"):
        score += 1
    if (signals["guide_top10"] or 0) >= 2:
        score += 1
    if signals.get("keyword_interrogatif"):
        score += 1
    v = signals["volume"] or 0
    if _VOLUME_MEDIUM <= v <= 10000:
        score += 1
    return score


def _score_pattern_c(signals: dict) -> int:
    score = 0
    if (signals["volume"] or 0) < _VOLUME_MEDIUM:
        score += 1
    # Signal fort : peu d'offres catalogue = niche / faible volume réel (+2 pour
    # compenser les signaux SERP qui poussent vers A/B même sur les petites SLs)
    if (signals.get("offer_count") or 999) < _OFFER_COUNT_MEDIUM:
        score += 2
    # Compagnie niche dans la tranche B (80-399 offres) avec quasi-absence d'OTAs
    # dans le top 10 → concurrence très faible malgré le nombre d'offres (ex. Cunard)
    if (_OFFER_COUNT_MEDIUM <= (signals.get("offer_count") or 0) < _OFFER_COUNT_HIGH
            and (signals["ota_top10"] or 0) < 2):
        score += 2
    if (signals["avg_top10_words"] or 9999) < 500:
        score += 1
    if (signals["ota_top10"] or 0) < 3:
        score += 1
    paa  = signals.get("paa_count", 0) or 0
    fs   = signals.get("featured_snippet", {})
    if paa == 0 and not fs.get("present"):
        score += 1
    # "Top 10 clairsemé" : peu d'OTA + peu de guides
    if (signals["ota_top10"] or 0) + (signals["guide_top10"] or 0) < 3:
        score += 1
    return score


def _resolve_tie(a: int, b: int, c: int) -> str:
    if a == b >= c:
        return "B"
    if a == c > b:
        return "A"
    if b == c > a:
        return "B"
    return max(zip([a, b, c], ["A", "B", "C"]), key=lambda x: x[0])[1]


# ── Volume fallback ────────────────────────────────────────────────────────────

def _fallback_on_volume(volume: int | None) -> str:
    v = volume or 0
    if v >= _VOLUME_HIGH:
        return "A"
    if v >= _VOLUME_MEDIUM:
        return "B"
    return "C"


# ── Fonction principale ────────────────────────────────────────────────────────

def select_pattern(
    serp: dict,
    textguru: dict,
    force_pattern: str | None = None,
    offer_count: int | None = None,
    low_price: int | None = None,
) -> dict:
    """Choisit le pattern éditorial A/B/C.

    Si force_pattern est fourni, bypasse l'algorithme.
    Retourne un dict avec pattern_chosen, scores, signals, flags.
    """
    keyword = textguru.get("query", "")
    volume  = _volume_from_catalogue(offer_count)

    signals: dict = {
        "volume":              volume,
        "offer_count":         offer_count,
        "low_price":           low_price,
        "ota_top10":           _ota_count_top10(serp),
        "guide_top10":         _guide_count_top10(serp),
        "paa_count":           serp.get("paa", {}).get("count", 0),
        "featured_snippet":    serp.get("featured_snippet", {}),
        "avg_top3_words":      _avg_content_length_top3(textguru.get("serp", []) and {"serp": textguru["serp"]} or serp),
        "avg_top10_words":     _avg_content_length_top10(textguru.get("serp", []) and {"serp": textguru["serp"]} or serp),
        "keyword_interrogatif": _keyword_is_interrogatif(keyword),
    }

    serp_error = bool(serp.get("error"))
    fallback_used = False

    if force_pattern:
        return {
            "pattern_chosen": force_pattern,
            "scores": {"A": 0, "B": 0, "C": 0},
            "signals": signals,
            "override_used": True,
            "fallback_used": False,
        }

    if serp_error:
        fallback_used = True
        chosen = _fallback_on_volume(volume)
        return {
            "pattern_chosen": chosen,
            "scores": {"A": 0, "B": 0, "C": 0},
            "signals": signals,
            "override_used": False,
            "fallback_used": True,
        }

    score_a = _score_pattern_a(signals)
    score_b = _score_pattern_b(signals)
    score_c = _score_pattern_c(signals)

    max_score = max(score_a, score_b, score_c)
    if [score_a, score_b, score_c].count(max_score) > 1:
        chosen = _resolve_tie(score_a, score_b, score_c)
    else:
        chosen = ["A", "B", "C"][[score_a, score_b, score_c].index(max_score)]

    return {
        "pattern_chosen": chosen,
        "scores": {"A": score_a, "B": score_b, "C": score_c},
        "signals": signals,
        "override_used": False,
        "fallback_used": fallback_used,
    }
