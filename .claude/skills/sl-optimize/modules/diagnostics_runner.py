"""Diagnostics automatiques des SL ABCroisière.

10 checks + check 5 bis sur le contenu fetché.
Spec complète dans reference/sl_diagnostics.md.
"""

import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

# ── Constantes ─────────────────────────────────────────────────────────────────

_BRAND_CONSTRAINTS_DIR = Path(__file__).parent.parent / "reference" / "brand_constraints"

_DEFAULT_OFFER_COUNT = 1000
_DEFAULT_LOW_PRICE   = 79


# ── Anomalie factory ───────────────────────────────────────────────────────────

def _anomaly(check_id: str, severity: str, code: str, description: str,
             details: dict | None = None, suggested_fix: str = "") -> dict:
    return {
        "check_id":      check_id,
        "severity":      severity,
        "code":          code,
        "description":   description,
        "details":       details or {},
        "suggested_fix": suggested_fix,
    }


# ── Utilitaires ────────────────────────────────────────────────────────────────

def _extract_price(text: str) -> int | None:
    """Extrait le premier prix en € d'un texte (ex: '159€', 'dès 159 €')."""
    m = re.search(r'(\d[\d\s]*)\s*€', text)
    if not m:
        return None
    try:
        return int(re.sub(r'\s', '', m.group(1)))
    except ValueError:
        return None


def _extract_volume(text: str) -> int | None:
    """Extrait un nombre de croisières (ex: '648 croisières')."""
    m = re.search(r'(\d[\d\s]+)\s+croisi[eè]re', text, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(re.sub(r'\s', '', m.group(1)))
    except ValueError:
        return None


def _normalize_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(" ", "").replace("\xa0", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


# ── Chargement brand constraints ──────────────────────────────────────────────

def _load_brand_constraints() -> dict[str, list[str]]:
    """Charge les contraintes depuis reference/brand_constraints/*.md.

    Retourne {BRAND_UPPER: [termes_interdits_lower]}.
    """
    constraints: dict[str, list[str]] = {}
    if not _BRAND_CONSTRAINTS_DIR.exists():
        return constraints

    for path in _BRAND_CONSTRAINTS_DIR.glob("*.md"):
        brand = path.stem.upper()
        content = path.read_text(encoding="utf-8")

        forbidden: list[str] = []
        in_section = False
        for line in content.splitlines():
            if re.match(r"^##\s+Termes\s+INTERDITS", line):
                in_section = True
                continue
            if in_section:
                if line.startswith("##"):
                    break
                m = re.match(r"^[-*+]\s+(.+)", line.strip())
                if m:
                    for part in re.split(r"\s*/\s*", m.group(1).strip()):
                        part = part.strip().lower()
                        if part:
                            forbidden.append(part)

        if forbidden:
            constraints[brand] = forbidden

    return constraints


_BRAND_CONSTRAINTS: dict[str, list[str]] = _load_brand_constraints()


# ── Check 1 : Cohérence title / meta / schema ──────────────────────────────────

def _check_1_consistency(fetched: dict, brief: dict | None = None) -> list[dict]:
    anomalies = []
    title         = fetched.get("title", "")
    meta          = fetched.get("meta_description", "")
    schema_price  = _normalize_int(fetched["schema"]["product"]["low_price"])
    schema_volume = _normalize_int(fetched["schema"]["product"]["offer_count"])

    # Si un brief est fourni, ses valeurs font autorité sur le schema JSON-LD
    # (le schema peut contenir des valeurs par défaut buggées côté CMS).
    brief_price  = _normalize_int((brief or {}).get("prix_plancher"))
    brief_volume = _normalize_int((brief or {}).get("nombre_de_croisieres"))

    title_price = _extract_price(title)
    meta_price  = _extract_price(meta)
    meta_volume = _extract_volume(meta)

    # Price check : skip si le brief confirme que la meta/title est correcte
    ref_price = brief_price if brief_price is not None else schema_price
    if title_price is not None and ref_price is not None and title_price != ref_price:
        anomalies.append(_anomaly(
            "check_1_consistency", "HIGH", "title_meta_mismatch_price",
            f"Prix dans le title ({title_price}€) != référence ({ref_price}€)",
            {"title_price": title_price, "ref_price": ref_price,
             "source": "brief" if brief_price else "schema"},
            f"Mettre à jour le title pour afficher {ref_price}€",
        ))

    if meta_price is not None and ref_price is not None and meta_price != ref_price:
        anomalies.append(_anomaly(
            "check_1_consistency", "HIGH", "meta_mismatch_price",
            f"Prix dans la meta ({meta_price}€) != référence ({ref_price}€)",
            {"meta_price": meta_price, "ref_price": ref_price,
             "source": "brief" if brief_price else "schema"},
            f"Mettre à jour la meta pour afficher {ref_price}€",
        ))

    # Volume check : idem
    ref_volume = brief_volume if brief_volume is not None else schema_volume
    if meta_volume is not None and ref_volume is not None and meta_volume != ref_volume:
        anomalies.append(_anomaly(
            "check_1_consistency", "HIGH", "meta_mismatch_volume",
            f"Volume dans la meta ({meta_volume}) != référence ({ref_volume})",
            {"meta_volume": meta_volume, "ref_volume": ref_volume,
             "source": "brief" if brief_volume else "schema"},
            f"Mettre à jour la meta pour afficher {ref_volume} croisières",
        ))

    return anomalies


# ── Check 2 : Année obsolète ───────────────────────────────────────────────────

def _check_2_year(fetched: dict) -> list[dict]:
    anomalies = []
    current_year = date.today().year

    for field, label in [("title", "title"), ("meta_description", "meta")]:
        text = fetched.get(field, "")
        if not text:
            continue

        # Ranges "AAAA-BBBB" d'abord pour éviter les doublons
        range_start_years: set[int] = set()
        range_end_years:   set[int] = set()
        for m in re.finditer(r"\b(20\d{2})-(20\d{2})\b", text):
            start, end = int(m.group(1)), int(m.group(2))
            range_start_years.add(start)
            range_end_years.add(end)
            if start < current_year:
                anomalies.append(_anomaly(
                    "check_2_year", "HIGH", "year_range_obsolete",
                    f"Plage d'années obsolète {start}-{end} dans le {label}",
                    {"field": label, "range": f"{start}-{end}", "current_year": current_year},
                    f"Remplacer {start}-{end} par {current_year} ou {current_year}-{current_year+1}",
                ))

        # Années seules (non couvertes par les ranges)
        for y_str in re.findall(r"\b(20\d{2})\b", text):
            y = int(y_str)
            if y in range_start_years or y in range_end_years:
                continue
            if y < current_year:
                anomalies.append(_anomaly(
                    "check_2_year", "HIGH", "year_obsolete",
                    f"Année obsolète {y} dans le {label} (courante : {current_year})",
                    {"field": label, "year_found": y, "current_year": current_year},
                    f"Remplacer {y} par {current_year} ou {current_year}-{current_year+1}",
                ))

    return anomalies


# ── Check 3 : H1 valide ────────────────────────────────────────────────────────

def _check_3_h1(fetched: dict) -> list[dict]:
    anomalies = []
    h1 = fetched.get("h1", "")

    if not h1:
        anomalies.append(_anomaly(
            "check_3_h1", "HIGH", "h1_missing",
            "H1 absent ou vide",
            {},
            "Vérifier le sélecteur CSS h1.kv-products-search-list-headTitle",
        ))
        return anomalies

    # "Croisieres" sans accent
    if re.search(r"[Cc]roisi[eE]res", h1) and "croisières" not in h1.lower():
        anomalies.append(_anomaly(
            "check_3_h1", "MEDIUM", "h1_missing_accent",
            f"H1 sans accent : '{h1}' (attendu : 'Croisières' avec accent)",
            {"h1": h1},
            "Corriger l'encodage/source du H1 dans le CMS",
        ))

    if not h1[0].isupper():
        anomalies.append(_anomaly(
            "check_3_h1", "MEDIUM", "h1_capitalization",
            f"H1 ne commence pas par une majuscule : '{h1}'",
            {"h1": h1},
            "Mettre la première lettre du H1 en majuscule",
        ))

    return anomalies


# ── Check 4 : Breadcrumb schema ────────────────────────────────────────────────

def _check_4_breadcrumb(fetched: dict) -> list[dict]:
    anomalies = []
    items = fetched["schema"].get("breadcrumb", [])

    for item in items:
        url  = item.get("url", "")
        name = item.get("name", "")
        pos  = item.get("position", "?")

        # Sous-domaine obsolète (tout sauf www)
        m = re.search(r"https?://([^/]+)\.abcroisiere\.com", url)
        if m and m.group(1).lower() != "www":
            anomalies.append(_anomaly(
                "check_4_breadcrumb", "HIGH", "breadcrumb_url_obsolete",
                f"Breadcrumb position {pos} : sous-domaine obsolète {url}",
                {"position": pos, "url": url, "subdomain": m.group(1)},
                "Corriger l'URL breadcrumb vers https://www.abcroisiere.com/",
            ))

        # Contraintes marque dans le nom
        name_lower = name.lower()
        for brand, forbidden_terms in _BRAND_CONSTRAINTS.items():
            if brand.lower() not in name_lower:
                continue
            for term in forbidden_terms:
                if term in name_lower:
                    anomalies.append(_anomaly(
                        "check_4_breadcrumb", "HIGH", "breadcrumb_brand_violation",
                        f"Violation {brand} dans breadcrumb position {pos} : '{name}' contient '{term}'",
                        {"position": pos, "name": name, "brand": brand, "forbidden_term": term},
                        f"Supprimer '{term}' du nom breadcrumb",
                    ))

    return anomalies


# ── Check 5 : Variables CMS dans title / meta ──────────────────────────────────
# Le HTML est déjà vérifié par content_fetcher._detect_extraction_anomalies

def _check_5_cms_vars(fetched: dict) -> list[dict]:
    anomalies = []
    for field in ("title", "meta_description"):
        for var in set(re.findall(r"\$\{[^}]+\}", fetched.get(field, ""))):
            anomalies.append(_anomaly(
                "check_5_cms_vars", "HIGH", "cms_variable_not_injected",
                f"Variable CMS non injectée dans {field} : {var}",
                {"field": field, "variable": var},
                f"Corriger l'injection CMS pour {var}",
            ))
    return anomalies


# ── Check 5 bis : Valeurs schema Product suspectes ─────────────────────────────

def _check_5bis_schema_suspect(fetched: dict) -> tuple[list[dict], bool, dict | None]:
    product     = fetched["schema"]["product"]
    offer_count = _normalize_int(product.get("offer_count"))
    low_price   = _normalize_int(product.get("low_price"))

    if offer_count == _DEFAULT_OFFER_COUNT and low_price == _DEFAULT_LOW_PRICE:
        details = {
            "offer_count": offer_count,
            "low_price":   low_price,
            "reason":      f"offerCount={offer_count} + lowPrice={low_price}€ = valeurs génériques par défaut",
        }
        return (
            [_anomaly(
                "check_5bis_schema", "HIGH", "schema_product_default_values",
                f"Schema Product suspect : offerCount={offer_count}, lowPrice={low_price}€",
                details,
                "Fournir un brief catalogue : --brief briefs/<slug>.md",
            )],
            True,
            details,
        )

    return [], False, None


# ── Check 6 : URLs internes absolues ──────────────────────────────────────────

def _check_6_internal_urls(fetched: dict) -> list[dict]:
    anomalies = []
    full_html = (
        fetched.get("top_content_html", "")
        + fetched.get("destination_content_html", "")
    )
    if not full_html:
        return anomalies

    soup = BeautifulSoup(full_html, "html.parser")
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)
        if re.match(r"https?://(?:www\.)?abcroisiere\.com", href, re.IGNORECASE):
            relative = re.sub(r"https?://(?:www\.)?abcroisiere\.com", "", href)
            anomalies.append(_anomaly(
                "check_6_internal_urls", "MEDIUM", "internal_url_absolute",
                f"URL interne en absolu : {href}",
                {"href": href, "text": a.get_text(strip=True)[:50]},
                f"Remplacer par URL relative : {relative}",
            ))

    return anomalies


# ── Check 7 : Longueurs title et meta ─────────────────────────────────────────

def _check_7_lengths(fetched: dict) -> list[dict]:
    anomalies = []
    title = fetched.get("title", "")
    meta  = fetched.get("meta_description", "")

    t = len(title)
    if title:
        if t < 30:
            anomalies.append(_anomaly(
                "check_7_lengths", "LOW", "title_too_short",
                f"Title trop court : {t} caractères (min : 30)",
                {"length": t}, "Enrichir le title pour atteindre 40-60 caractères",
            ))
        elif t > 60:
            anomalies.append(_anomaly(
                "check_7_lengths", "LOW", "title_too_long",
                f"Title trop long : {t} caractères (max : 60, Google tronque)",
                {"length": t}, "Raccourcir le title sous 60 caractères",
            ))

    m = len(meta)
    if meta:
        if m < 120:
            anomalies.append(_anomaly(
                "check_7_lengths", "LOW", "meta_too_short",
                f"Meta trop courte : {m} caractères (min : 120)",
                {"length": m}, "Enrichir la meta pour atteindre 140-160 caractères",
            ))
        elif m > 160:
            anomalies.append(_anomaly(
                "check_7_lengths", "LOW", "meta_too_long",
                f"Meta trop longue : {m} caractères (max : 160, Google tronque)",
                {"length": m}, "Raccourcir la meta sous 160 caractères",
            ))

    return anomalies


# ── Check 8 : Contraintes marque ──────────────────────────────────────────────

def _check_8_brand_constraints(fetched: dict) -> list[dict]:
    if not _BRAND_CONSTRAINTS:
        return []

    anomalies = []
    full_content = " ".join([
        fetched.get("title", ""),
        fetched.get("meta_description", ""),
        fetched.get("h1", ""),
        fetched.get("top_content_html", ""),
        fetched.get("destination_content_html", ""),
    ]).lower()

    for brand, forbidden_terms in _BRAND_CONSTRAINTS.items():
        brand_lower = brand.lower()
        brand_positions = [
            m.start()
            for m in re.finditer(r"\b" + re.escape(brand_lower) + r"\b", full_content)
        ]
        if not brand_positions:
            continue

        seen_violations: set[str] = set()
        for term in forbidden_terms:
            if term in seen_violations:
                continue
            for pos in brand_positions:
                window_start = max(0, pos - 100)
                window_end   = min(len(full_content), pos + 100)
                if term in full_content[window_start:window_end]:
                    seen_violations.add(term)
                    ctx = full_content[window_start:window_end].strip()[:120]
                    anomalies.append(_anomaly(
                        "check_8_brand_constraints", "HIGH", "brand_constraint_violation",
                        f"Violation contrainte {brand} : '{term}' associé à {brand}",
                        {"brand": brand, "forbidden_term": term, "context": ctx},
                        f"Remplacer '{term}' (voir reference/brand_constraints/{brand.lower()}.md)",
                    ))
                    break

    return anomalies


# ── Check 9 : Signature auteur ────────────────────────────────────────────────

def _check_9_signature(fetched: dict) -> list[dict]:
    if fetched.get("author_signature"):
        return []
    return [_anomaly(
        "check_9_signature", "LOW", "author_signature_missing",
        "Signature auteur absente du destination content",
        {},
        "Ajouter une signature auteur en fin de destination content (reference/authors.md)",
    )]


# ── Check 10 : Balisage HTML conforme ─────────────────────────────────────────

def _check_10_html_markup(fetched: dict) -> list[dict]:
    anomalies = []
    dest_html = fetched.get("destination_content_html", "")
    if not dest_html:
        return anomalies

    soup = BeautifulSoup(dest_html, "html.parser")

    for tag_name in ("strong", "em", "h1", "h4"):
        for el in soup.find_all(tag_name)[:3]:
            anomalies.append(_anomaly(
                "check_10_html_markup", "MEDIUM", "forbidden_tag",
                f"Balise interdite <{tag_name}> dans le destination content",
                {"tag": tag_name, "content": el.get_text(strip=True)[:80]},
                f"Supprimer/remplacer <{tag_name}> (reference/sl_anatomy.md)",
            ))

    for el in soup.find_all(style=True):
        style = el.get("style", "")
        if "sprite.png" in style:
            continue  # Signature auteur — span avec sprite, toléré
        # Autres éléments de la signature auteur : <p> et <span> siblings du sprite
        parent = el if el.name == "p" else el.parent
        if parent and any(
            "sprite.png" in (s.get("style", ""))
            for s in parent.find_all(style=True)
        ):
            continue  # Même bloc signature, toléré
        anomalies.append(_anomaly(
            "check_10_html_markup", "MEDIUM", "inline_style",
            f"Style inline sur <{el.name}> : {style[:60]}",
            {"tag": el.name, "style": style},
            "Supprimer le style inline",
        ))

    return anomalies


# ── Fonction principale ────────────────────────────────────────────────────────

def run_diagnostics(fetched: dict, sl_type: str, brief: dict | None = None) -> dict:
    """Exécute les 10 checks + check 5 bis sur une SL fetchée.

    Retourne anomalies, compteurs par sévérité, et flag check_5bis.
    """
    all_anomalies: list[dict] = list(fetched.get("anomalies_detected", []))

    all_anomalies.extend(_check_1_consistency(fetched, brief=brief))
    all_anomalies.extend(_check_2_year(fetched))
    all_anomalies.extend(_check_3_h1(fetched))
    all_anomalies.extend(_check_4_breadcrumb(fetched))
    all_anomalies.extend(_check_5_cms_vars(fetched))

    c5bis_list, c5bis_triggered, c5bis_details = _check_5bis_schema_suspect(fetched)
    all_anomalies.extend(c5bis_list)

    all_anomalies.extend(_check_6_internal_urls(fetched))
    all_anomalies.extend(_check_7_lengths(fetched))
    all_anomalies.extend(_check_8_brand_constraints(fetched))
    all_anomalies.extend(_check_9_signature(fetched))
    all_anomalies.extend(_check_10_html_markup(fetched))

    counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for a in all_anomalies:
        counts[a.get("severity", "LOW")] = counts.get(a.get("severity", "LOW"), 0) + 1

    return {
        "anomalies":            all_anomalies,
        "anomalies_count":      counts,
        "check_5bis_triggered": c5bis_triggered,
        "check_5bis_details":   c5bis_details,
    }
