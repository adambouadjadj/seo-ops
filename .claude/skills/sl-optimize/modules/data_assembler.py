"""Assemblage du dict final data_assembled.json.

Étape 7 du skill : compile fetched + diagnostics + textguru + serp
+ pattern + faq + brief en un seul dict pivot pour la génération.
"""

import json
import re
from pathlib import Path

# ── Personas (reference/authors.md) ───────────────────────────────────────────

_PERSONAS = [
    {
        "name":   "Élodie – Spécialiste Méditerranée",
        "keywords": [
            "mediterrane", "iles-grecques", "grece", "baleares", "croatie",
            "adriatique", "italie", "espagne", "turquie", "canaries",
            "madere", "sicile", "corse", "tunisie", "maroc", "mer-rouge",
        ],
    },
    {
        "name":   "Marc – Expert Caraïbes & Amériques",
        "keywords": [
            "caraibes", "antilles", "bahamas", "cuba", "dominicaine",
            "miami", "amerique", "polynesie", "monde", "floride",
        ],
    },
    {
        "name":   "Claire – Spécialiste Europe du Nord & Fjords",
        "keywords": [
            "nord", "fjords", "baltique", "islande", "spitzberg",
            "groenland", "britanniques", "irlande", "ecosse",
            "scandinavie", "norvege",
        ],
    },
    {
        "name":   "Thomas – Expert Compagnies & Thématiques",
        "keywords": [],  # fallback pour type=compagnie
    },
]

_FALLBACK_PERSONA = "L'équipe ABCroisière"


def _resolve_persona(sl_type: str, slug: str, keyword: str) -> str:
    # Toutes les SL compagnies → Thomas
    if sl_type == "compagnie":
        return "Thomas – Expert Compagnies & Thématiques"

    # Pour les destinations, matcher sur le slug / keyword
    text = (slug + " " + keyword).lower()

    for persona in _PERSONAS:
        if not persona["keywords"]:
            continue
        if any(kw in text for kw in persona["keywords"]):
            return persona["name"]

    # Thématiques détectées par mots-clés transversaux
    thematiques = [
        "inclus", "derniere-minute", "famille", "luxe", "fluviale",
        "tout-compris", "budget", "senior", "solo",
    ]
    if any(t in text for t in thematiques):
        return "Thomas – Expert Compagnies & Thématiques"

    return _FALLBACK_PERSONA


# ── Résolution catalogue (schema ou brief) ────────────────────────────────────

def _resolve_catalogue(fetched: dict, brief: dict | None) -> dict:
    """Résout les valeurs catalogue (offerCount + lowPrice) avec priorité brief > schema."""
    schema_product = fetched.get("schema", {}).get("product", {})

    if brief is not None:
        offer_count = brief.get("nombre_de_croisieres") or schema_product.get("offer_count")
        low_price   = brief.get("prix_plancher")       or schema_product.get("low_price")
        source      = "brief"
    else:
        offer_count = schema_product.get("offer_count")
        low_price   = schema_product.get("low_price")
        source      = "schema"

    return {
        "offer_count": offer_count,
        "low_price":   low_price,
        "currency":    schema_product.get("currency", "EUR"),
        "source":      source,
    }


# ── Chargement catalogue URLs (pour la génération) ────────────────────────────

def _load_catalogue_urls(catalogue_path: Path) -> dict:
    """Charge le catalogue d'URLs pour les maillages internes."""
    if not catalogue_path or not catalogue_path.exists():
        return {}
    try:
        return json.loads(catalogue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ── Fonction principale ────────────────────────────────────────────────────────

def assemble(
    url:            str,
    slug:           str,
    sl_type:        str,
    mode_variables: str,
    fetched:        dict,
    diagnostics:    dict,
    textguru:       dict,
    serp:           dict,
    pattern_result: dict,
    faq:            dict,
    brief:          dict | None,
    catalogue_path: Path,
) -> dict:
    """Compile toutes les données collectées en un seul dict pivot.

    Ce dict est persisté dans data_assembled.json et sert de base
    pour la génération de contenu par Claude Code (étape 8).
    """
    keyword = textguru.get("query", "")
    persona = _resolve_persona(sl_type, slug, keyword)
    catalogue = _resolve_catalogue(fetched, brief)

    # Extraire les champs du fetched nécessaires à la génération
    current_content = {
        "h1":                      fetched.get("h1", ""),
        "title":                   fetched.get("title", ""),
        "meta_description":        fetched.get("meta_description", ""),
        "top_content_html":        fetched.get("top_content_html", ""),
        "top_content_p_count":     fetched.get("top_content_paragraphs_count", 0),
        "destination_content_html":      fetched.get("destination_content_html", ""),
        "destination_content_h3_count":  fetched.get("destination_content_h3_count", 0),
        "internal_links_existing": fetched.get("internal_links_existing", []),
        "author_signature":        fetched.get("author_signature"),
    }

    schema_enriched = {
        "product":                   fetched.get("schema", {}).get("product", {}),
        "breadcrumb":                fetched.get("schema", {}).get("breadcrumb", []),
        "events_count":              fetched.get("schema", {}).get("events_count", 0),
        "ports_depart":              fetched.get("schema", {}).get("ports_depart", []),
        "destinations_mentionnees":  fetched.get("schema", {}).get("destinations_mentionnees", []),
    }

    # Résumé diagnostics (pas les anomalies complètes pour alléger le JSON)
    diagnostics_summary = {
        "anomalies_count":      diagnostics.get("anomalies_count", {}),
        "check_5bis_triggered": diagnostics.get("check_5bis_triggered", False),
        "check_5bis_details":   diagnostics.get("check_5bis_details"),
        "anomalies":            diagnostics.get("anomalies", []),
    }

    return {
        "url":            url,
        "slug":           slug,
        "type":           sl_type,
        "pattern":        pattern_result.get("pattern_chosen"),
        "persona":        persona,
        "mode_variables": mode_variables,
        "fetched_at":     fetched.get("fetched_at", ""),

        # Données catalogue (offerCount + lowPrice) — source: schema ou brief
        "catalogue": catalogue,

        # Contenu actuel de la SL (à analyser + conserver les liens)
        "current_content": current_content,

        # Schema JSON-LD extrait
        "schema": schema_enriched,

        # Diagnostics
        "diagnostics": diagnostics_summary,

        # Brief catalogue si fourni (override manuel)
        "brief": brief,

        # Brief sémantique Textguru
        "textguru": {
            "guide_id": textguru.get("guide_id"),
            "query":    textguru.get("query"),
            "keywords": textguru.get("keywords", {}),
            "entities": textguru.get("entities", []),
            "targets":  textguru.get("targets", {}),
            "paa":      textguru.get("paa", []),
        },

        # Analyse SERP DataForSEO
        "serp": {
            "keyword":             serp.get("keyword"),
            "check_url":          serp.get("check_url"),
            "concurrents_directs": serp.get("concurrents_directs", []),
            "concurrents_count":   serp.get("concurrents_count", {}),
            "paa":                 serp.get("paa", {}),
            "featured_snippet":    serp.get("featured_snippet", {}),
            "ai_overview":         serp.get("ai_overview", {}),
            "related_searches":    serp.get("related_searches", []),
            "competitors_with_faq": serp.get("competitors_with_faq", []),
            "item_types":          serp.get("item_types", []),
            "error":               serp.get("error"),
        },

        # Décision pattern
        "pattern_result": {
            "pattern_chosen": pattern_result.get("pattern_chosen"),
            "scores":         pattern_result.get("scores", {}),
            "signals":        pattern_result.get("signals", {}),
            "override_used":  pattern_result.get("override_used", False),
            "fallback_used":  pattern_result.get("fallback_used", False),
        },

        # Décision FAQ
        "faq": {
            "add_faq":       faq.get("add_faq", False),
            "signals":       faq.get("signals", {}),
            "paa_questions": faq.get("paa_questions", []),
            "triggered_by":  faq.get("triggered_by", []),
        },

        # Chemin catalogue URLs (pour la génération des liens internes)
        "catalogue_urls_path": str(catalogue_path) if catalogue_path else None,
    }
