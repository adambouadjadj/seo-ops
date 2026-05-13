"""Step 9b — Validator GEO.

Valide les signaux de qualité GEO (LLM-readiness) sur le contenu généré.
Non-bloquant : score informatif uniquement, aucun échec ne stoppe la génération.

Interface :
    from modules.validator_geo import validate_geo
    result = validate_geo(
        title="...",
        meta="...",
        top_html="...",
        dest_html="...",
        data_assembled=assembled,
    )
    # result = {"score": int, "total": int, "results": [...]}
"""

import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup


# ── Utilitaires ────────────────────────────────────────────────────────────────

def _result(check: str, passed: bool, detail: str = "") -> dict:
    return {"check": check, "passed": passed, "detail": detail}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w{3,}\b", text))


def _is_in_faq_microdata(el) -> bool:
    for parent in el.parents:
        itemtype = parent.get("itemtype", "")
        if "FAQPage" in itemtype or "Question" in itemtype:
            return True
    return False


def _get_entities(data_assembled: dict) -> list[str]:
    """Retourne la liste des entités normalisées depuis Textguru + schema."""
    raw: list[str] = []
    raw += data_assembled.get("textguru", {}).get("entities", [])
    raw += data_assembled.get("schema", {}).get("ports_depart", [])
    raw += data_assembled.get("schema", {}).get("destinations_mentionnees", [])
    return [_normalize(e) for e in raw if e and len(e) > 3]


# ── Signal 1 : Entrée top content sur entité forte ────────────────────────────

def _signal_top_opening(top_html: str, data_assembled: dict) -> dict:
    check = "Top content : entrée sur entité forte"
    soup  = BeautifulSoup(top_html, "html.parser")
    first_p = soup.find("p")

    if not first_p:
        return _result(check, False, "Aucun <p> dans le top content")

    text = first_p.get_text(strip=True)
    if not text:
        return _result(check, False, "Premier <p> vide")

    # Accroche molle interdite sans entité forte
    soft_starts = r"^(La |Le |Les |Un |Une |Des |En |Au |Aux )"
    hollow = r"^(La .{0,30}vous attend|Laissez|Évadez|Plongez dans|Bienvenue)"

    if re.match(hollow, text, re.IGNORECASE):
        return _result(check, False, f"Accroche molle : '{text[:60]}'")

    # OK si commence par chiffre
    if text[0].isdigit():
        return _result(check, True, f"Entrée chiffre : {text[:50]}")

    # OK si "Partez/Découvrez + entité forte" (verbe d'action + nom propre immédiat)
    action_pattern = r"^(Partez|Découvrez|Explorez|Choisissez)\s+(en\s+)?[A-ZÀÂÉÈÊËÎÏÔÙÛÜ]"
    if re.match(action_pattern, text):
        return _result(check, True, f"Verbe + entité : {text[:50]}")

    # OK si commence par entité nommée (majuscule = nom propre probable)
    if text[0].isupper() and not re.match(soft_starts, text):
        return _result(check, True, f"Entrée entité : {text[:50]}")

    return _result(check, False, f"Ouverture sans entité forte : '{text[:60]}'")


# ── Signal 2 : Densité entités dans le top content ───────────────────────────

def _signal_entity_density(top_html: str, data_assembled: dict) -> dict:
    check    = "Entités nommées denses dans le top (~1/6-8 mots)"
    entities = _get_entities(data_assembled)

    if not entities:
        return _result(check, True, "Pas d'entités Textguru — check sauté")

    text      = _strip_tags(top_html)
    text_norm = _normalize(text)
    words     = _word_count(text)

    if words == 0:
        return _result(check, False, "Top content vide")

    # Compte les entités présentes (dédupliquées)
    found = sum(1 for e in set(entities) if e in text_norm)

    ratio = found / words if words else 0
    # Cible : ≥ 1 entité pour 8 mots (ratio ≥ 0.125)
    ok    = ratio >= 0.125

    return _result(
        check,
        ok,
        f"{found} entités / {words} mots (ratio {ratio:.2f}, cible ≥ 0.12)",
    )


# ── Signal 3 : Chiffres concrets dans le dest content ────────────────────────

def _signal_concrete_figures(dest_html: str) -> dict:
    check = "Chiffres concrets dans le dest (prix, durées, dates)"
    text  = _strip_tags(dest_html)

    # Prix : "89€", "dès 89 €"
    prices   = re.findall(r"\d[\d\s]*€", text)
    # Durées : "7 jours", "14 nuits", "10h"
    durations = re.findall(r"\d+\s*(?:jour|nuit|heure|h\b)", text, re.IGNORECASE)
    # Années : 202x
    years    = re.findall(r"\b202[3-9]\b", text)
    # Nombres significatifs (≥ 2 chiffres, pas des années)
    counts   = re.findall(r"\b(?!202[0-9])\d{2,}\b", text)

    total_signals = len(set(prices)) + len(set(durations)) + len(set(years)) + len(set(counts[:10]))
    ok = total_signals >= 3

    detail_parts = []
    if prices:
        detail_parts.append(f"{len(set(prices))} prix")
    if durations:
        detail_parts.append(f"{len(set(durations))} durées")
    if years:
        detail_parts.append(f"{len(set(years))} années")
    if counts:
        detail_parts.append(f"{min(len(set(counts)), 10)} chiffres")

    return _result(
        check,
        ok,
        ", ".join(detail_parts) if detail_parts else "Aucun chiffre détecté",
    )


# ── Signal 4 : H3 en questions (Pattern B principalement) ────────────────────

def _signal_h3_questions(dest_html: str, data_assembled: dict) -> dict:
    pattern = data_assembled.get("pattern", "A")
    check   = f"H3 en questions naturelles (Pattern {pattern})"
    soup    = BeautifulSoup(dest_html, "html.parser")

    editorial_h3s = [h3 for h3 in soup.find_all("h3") if not _is_in_faq_microdata(h3)]
    if not editorial_h3s:
        return _result(check, True, "Pas de H3 éditoriaux")

    h3_questions = [h3 for h3 in editorial_h3s if "?" in h3.get_text()]
    ratio = len(h3_questions) / len(editorial_h3s)

    # Pattern B : au moins 40% des H3 en questions recommandé
    # Pattern A/C : optionnel, tout ratio est OK
    if pattern == "B":
        ok = ratio >= 0.40
        return _result(
            check,
            ok,
            f"{len(h3_questions)}/{len(editorial_h3s)} H3 en question (ratio {ratio:.0%}, cible ≥40% Pattern B)",
        )

    # Pattern A ou C : informatif seulement
    return _result(
        check,
        True,
        f"{len(h3_questions)}/{len(editorial_h3s)} H3 en question (Pattern {pattern} — non contraint)",
    )


# ── Signal 5 : FAQ microdata si faq.add_faq: true ────────────────────────────

def _signal_faq_microdata(dest_html: str, data_assembled: dict) -> dict:
    check    = "FAQ microdata présente si faq.add_faq: true"
    add_faq  = data_assembled.get("faq", {}).get("add_faq", False)

    if not add_faq:
        return _result(check, True, "faq.add_faq = false — FAQ non attendue")

    has_faq = "schema.org/FAQPage" in dest_html or "FAQPage" in dest_html
    if has_faq:
        q_count = len(re.findall(r'itemtype=["\']https://schema\.org/Question["\']', dest_html))
        return _result(check, True, f"FAQPage présente ({q_count} questions)")

    return _result(check, False, "faq.add_faq = true mais FAQPage microdata absente du dest content")


# ── Signal 6 : Signature auteur (double-check) ───────────────────────────────

def _signal_author_signature(dest_html: str, data_assembled: dict) -> dict:
    check   = "Signature auteur présente (EEAT)"
    persona = data_assembled.get("persona", "")

    if "sprite.png" in dest_html:
        return _result(check, True, persona or "Signature détectée")
    return _result(check, False, "Signature auteur (sprite.png) absente")


# ── Signal 7 : Entity echoing en début de paragraphe ─────────────────────────

def _signal_entity_echoing(dest_html: str) -> dict:
    check = "Entity echoing naturel en début de §"
    soup  = BeautifulSoup(dest_html, "html.parser")

    editorial_h3s = [h3 for h3 in soup.find_all("h3") if not _is_in_faq_microdata(h3)]
    if not editorial_h3s:
        return _result(check, True, "Pas de H3 éditoriaux — check sauté")

    echoing_count = 0
    checked = 0

    for h3 in editorial_h3s:
        h3_words = set(_normalize(h3.get_text()).split())
        h3_significant = {w for w in h3_words if len(w) > 4}
        if not h3_significant:
            continue

        # Cherche le premier <p> frère suivant ce H3
        next_p = None
        for sib in h3.next_siblings:
            if hasattr(sib, "name") and sib.name == "p":
                next_p = sib
                break
            if hasattr(sib, "name") and sib.name in ("h2", "h3"):
                break

        if not next_p:
            continue

        p_text = _normalize(next_p.get_text(strip=True))
        first_words = set(p_text.split()[:6])

        # Echoing si ≥1 mot significatif du H3 dans les 6 premiers mots du <p>
        if h3_significant & first_words:
            echoing_count += 1
        checked += 1

    if checked == 0:
        return _result(check, True, "Pas de paires H3/<p> détectées")

    ratio = echoing_count / checked
    ok    = ratio >= 0.5

    return _result(
        check,
        ok,
        f"{echoing_count}/{checked} sections avec entity echoing (ratio {ratio:.0%})",
    )


# ── Fonction principale ────────────────────────────────────────────────────────

def validate_geo(
    title: str,
    meta: str,
    top_html: str,
    dest_html: str,
    data_assembled: dict,
) -> dict:
    """Valide les signaux GEO de qualité sur le contenu généré.

    Non-bloquant : un score faible génère des warnings dans bilan_geo.md
    mais ne stoppe jamais la génération.

    Returns:
        {
            "score":   int,    # signaux passés
            "total":   int,    # signaux total
            "results": list[{"check": str, "passed": bool, "detail": str}]
        }
    """
    results: list[dict] = []

    results.append(_signal_top_opening(top_html, data_assembled))
    results.append(_signal_entity_density(top_html, data_assembled))
    results.append(_signal_concrete_figures(dest_html))
    results.append(_signal_h3_questions(dest_html, data_assembled))
    results.append(_signal_faq_microdata(dest_html, data_assembled))
    results.append(_signal_author_signature(dest_html, data_assembled))
    results.append(_signal_entity_echoing(dest_html))

    score = sum(1 for r in results if r["passed"])
    total = len(results)

    return {
        "score":   score,
        "total":   total,
        "results": results,
    }
