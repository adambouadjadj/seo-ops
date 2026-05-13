"""Step 7bis — Link Resolver.

Score chaque URL du catalogue par pertinence sémantique vis-à-vis de la SL
en cours, et retourne `link_suggestions` à injecter dans data_assembled.json.

Signaux de scoring (cumulatifs) :
  +3 par entité Textguru matchée
  +2 par port de départ matché
  +2 par destination mentionnée matchée
  +1 par related search matchée
  +3 boost type-catégorie (navires/combos compagnie si sl_type=compagnie,
                            combos_dest_mois si sl_type=destination)
"""

import html
import re
import unicodedata
from typing import Any


# ── Normalisation ──────────────────────────────────────────────────────────────

_PREFIX_RE = re.compile(
    r"^(croisi[eè]re?s?\s+|croisiere\s+|croisi\xe8re\s+|croisières\s+)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Lowercase + strip accents + strip préfixes croisière courants."""
    text = html.unescape(text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().strip()
    text = _PREFIX_RE.sub("", text)
    return text


def _slug_from_href(href: str) -> str:
    """Extrait la partie slug lisible d'un href catalogue.

    /fr/croisieres/croisiere-iles-grecques/destination,53,50/
    -> croisiere-iles-grecques

    /fr/bateau-croisiere/costa-fascinosa/navire,541/
    -> costa-fascinosa
    """
    parts = [p for p in href.rstrip("/").split("/") if p]
    for part in reversed(parts):
        if "," not in part:
            return part
    return parts[-1] if parts else ""


# ── Extraction des tokens de signal depuis assembled ──────────────────────────

def _signal_tokens(assembled: dict) -> dict[str, list[str]]:
    """Retourne les tokens normalisés par type de signal."""
    entities = [_normalize(e) for e in assembled.get("textguru", {}).get("entities", [])]

    ports_raw = assembled.get("schema", {}).get("ports_depart", [])
    ports = [_normalize(p) for p in ports_raw]

    dests_raw = assembled.get("schema", {}).get("destinations_mentionnees", [])
    dests = [_normalize(d) for d in dests_raw]

    related_raw = assembled.get("serp", {}).get("related_searches", [])
    related = [_normalize(r) for r in related_raw]

    return {
        "entities": entities,
        "ports": ports,
        "destinations": dests,
        "related": related,
    }


def _self_path(assembled: dict) -> str:
    """Retourne le chemin URL de la SL elle-même (pour l'exclure des suggestions)."""
    url = assembled.get("url", "")
    if not url:
        return ""
    # Garde uniquement le path : https://www.abcroisiere.com/fr/... -> /fr/...
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.path.rstrip("/") + "/"


def _existing_hrefs(assembled: dict) -> set[str]:
    links = assembled.get("current_content", {}).get("internal_links_existing", [])
    return {lnk.get("href", "") for lnk in links}


# ── Scoring d'une URL individuelle ────────────────────────────────────────────

def _score_url(
    label: str,
    href: str,
    category: str,
    signals: dict[str, list[str]],
    sl_type: str,
    sl_slug_norm: str,
) -> tuple[int, list[str]]:
    """Retourne (score, reasons) pour une URL du catalogue."""
    label_n = _normalize(label)
    slug_n  = _normalize(_slug_from_href(href).replace("-", " "))

    score   = 0
    reasons: list[str] = []

    def _matches(token: str, targets: list[str]) -> bool:
        """True si token apparaît dans au moins un des targets normalisés."""
        return any(token in t or t in token for t in targets)

    # +3 par entité Textguru
    for ent in signals["entities"]:
        if not ent:
            continue
        if ent in label_n or ent in slug_n:
            score += 3
            reasons.append(f"entity: {ent}")

    # +2 par port de départ
    for port in signals["ports"]:
        if not port:
            continue
        if port in label_n or port in slug_n:
            score += 2
            reasons.append(f"port: {port}")

    # +2 par destination mentionnée
    for dest in signals["destinations"]:
        if not dest:
            continue
        if dest in label_n or dest in slug_n:
            score += 2
            reasons.append(f"dest: {dest}")

    # +1 par related search
    for rel in signals["related"]:
        if not rel:
            continue
        if rel in label_n or label_n in rel or rel in slug_n:
            score += 1
            reasons.append(f"related: {rel[:40]}")

    # +3 boost type-catégorie
    if sl_type == "compagnie":
        # Extrait le nom de la compagnie depuis le slug de la SL
        # ex: "croisiere-costa-croisieres" -> "costa"
        if category == "navires" and sl_slug_norm in label_n:
            score += 3
            reasons.append("boost compagnie: navire")
        if category == "combos_compagnie_destination" and sl_slug_norm in label_n:
            score += 3
            reasons.append("boost compagnie: combo_dest")

    elif sl_type == "destination":
        # Boost combos_dest_mois dont le slug contient un token de la SL
        if category == "combos_dest_mois":
            slug_tokens = [t for t in sl_slug_norm.split() if len(t) > 3]
            for tok in slug_tokens:
                if tok in label_n or tok in slug_n:
                    score += 3
                    reasons.append(f"boost destination: {tok}")
                    break

    return score, reasons


# ── Fonction principale ────────────────────────────────────────────────────────

def resolve_links(assembled: dict, catalogue: dict) -> dict[str, Any]:
    """Score toutes les URLs du catalogue et retourne link_suggestions.

    Args:
        assembled : dict produit par Step 7 (data_assembler.assemble)
        catalogue : dict chargé depuis catalogue_urls_latest.json

    Returns:
        {
          "new_opportunities": [...],   # score > 0, absent de la page
          "already_linked":   [...],   # score > 0, déjà présent sur la page
          "gaps_count":       int,
          "total_scored":     int,
          "catalogue_total":  int,
        }
    """
    if not catalogue:
        return {
            "new_opportunities": [],
            "already_linked":    [],
            "gaps_count":        0,
            "total_scored":      0,
            "catalogue_total":   0,
        }

    sl_type     = assembled.get("type", "destination")
    sl_slug     = assembled.get("slug", "")
    sl_slug_n   = _normalize(sl_slug.replace("-", " "))

    signals     = _signal_tokens(assembled)
    existing    = _existing_hrefs(assembled)
    self_path   = _self_path(assembled)

    # Catégories à scorer (exclure _meta)
    skip_cats   = {"_meta"}

    new_opportunities: list[dict] = []
    already_linked:    list[dict] = []
    catalogue_total = 0

    for category, entries in catalogue.items():
        if category in skip_cats or not isinstance(entries, dict):
            continue

        for label, href in entries.items():
            catalogue_total += 1
            score, reasons = _score_url(
                label=label,
                href=href,
                category=category,
                signals=signals,
                sl_type=sl_type,
                sl_slug_norm=sl_slug_n,
            )

            if score == 0:
                continue

            entry = {
                "category": category,
                "label":    label,
                "href":     href,
                "score":    score,
                "reasons":  reasons,
            }

            # Exclure l'URL de la SL elle-même
            if href == self_path:
                continue

            if href in existing:
                already_linked.append(entry)
            else:
                new_opportunities.append(entry)

    # Tri score desc
    new_opportunities.sort(key=lambda x: x["score"], reverse=True)
    already_linked.sort(key=lambda x: x["score"], reverse=True)

    return {
        "new_opportunities": new_opportunities,
        "already_linked":    already_linked,
        "gaps_count":        len(new_opportunities),
        "total_scored":      len(new_opportunities) + len(already_linked),
        "catalogue_total":   catalogue_total,
    }
