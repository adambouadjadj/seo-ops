"""Step 9a — Validator SEO.

Valide les règles dures SEO sur le contenu généré.
Appelé par Claude Code inline après la génération (étape 8).

Un résultat "passed": False est bloquant — Claude Code doit corriger et relancer (1 retry max).

Interface :
    from modules.validator_seo import validate_seo
    result = validate_seo(
        title="...",
        meta="...",
        top_html="...",
        dest_html="...",
        data_assembled=assembled,
    )
    # result = {"passed": bool, "score": int, "total": int, "results": [...]}
"""

import re
import unicodedata
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

_BRAND_CONSTRAINTS_DIR = Path(__file__).parent.parent / "reference" / "brand_constraints"


# ── Chargement brand constraints (même logique que diagnostics_runner) ─────────

def _load_brand_constraints() -> dict[str, list[str]]:
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


# ── Utilitaires ────────────────────────────────────────────────────────────────

def _result(check: str, passed: bool, detail: str = "") -> dict:
    return {"check": check, "passed": passed, "detail": detail}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _extract_price(text: str) -> int | None:
    m = re.search(r"(\d[\d\s ]*)\s*€", text)
    if not m:
        return None
    try:
        return int(re.sub(r"[\s ]", "", m.group(1)))
    except ValueError:
        return None


def _extract_volume(text: str) -> int | None:
    m = re.search(r"(\d[\d\s ]+)\s+croisi[eè]re", text, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(re.sub(r"[\s ]", "", m.group(1)))
    except ValueError:
        return None


def _normalize_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(" ", "").replace("\xa0", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _count_internal_links(soup: BeautifulSoup) -> int:
    return sum(1 for a in soup.find_all("a", href=True) if a["href"].startswith("/"))


def _has_emoji(text: str) -> bool:
    # € excluded — currency symbol expected in meta/title
    return bool(re.search(r"[☀☛→✓✗★©®™£¥°•·…«»]|[\U0001F300-\U0001FFFF]", text))


def _is_in_faq_microdata(el) -> bool:
    for parent in el.parents:
        itemtype = parent.get("itemtype", "")
        if "FAQPage" in itemtype or "Question" in itemtype:
            return True
    return False


# ── Check 1 : Longueur title ──────────────────────────────────────────────────

def _check_title_length(title: str) -> dict:
    n = len(title)
    if 50 <= n <= 60:
        return _result("Title : 50-60 chars", True, f"{n} chars")
    return _result("Title : 50-60 chars", False, f"{n} chars — hors fourchette 50-60")


# ── Check 2 : Longueur meta ───────────────────────────────────────────────────

def _check_meta_length(meta: str) -> dict:
    n = len(meta)
    if 150 <= n <= 160:
        return _result("Meta : 150-160 chars", True, f"{n} chars")
    return _result("Meta : 150-160 chars", False, f"{n} chars — hors fourchette 150-160")


# ── Check 3 : Ouverture meta ──────────────────────────────────────────────────

def _check_meta_opening(meta: str) -> dict:
    check = "Meta : commence par chiffre ou entité forte"
    if not meta:
        return _result(check, False, "Meta vide")
    forbidden_starts = r"^(Partez|Découvrez|Explorez|Embarquez|Profitez|Laissez|Évadez|Plongez)"
    if re.match(forbidden_starts, meta, re.IGNORECASE):
        return _result(check, False, f"Accroche molle interdite : '{meta.split()[0]}'")
    if meta[0].isdigit():
        return _result(check, True, f"Entrée chiffre")
    if meta[0].isupper():
        return _result(check, True, "Entrée entité forte")
    return _result(check, False, f"Début suspect : '{meta[:30]}'")


# ── Check 4 : Pas d'emoji dans la meta ───────────────────────────────────────

def _check_meta_no_emoji(meta: str) -> dict:
    check = "Meta : sans emoji ni décoratif HTML"
    if not _has_emoji(meta):
        return _result(check, True)
    for ch in meta:
        if _has_emoji(ch):
            return _result(check, False, f"Caractère interdit : '{ch}'")
    return _result(check, False, "Emoji ou caractère décoratif détecté")


# ── Check 5 : Cohérence prix et volume ────────────────────────────────────────

def _check_prices_consistent(title: str, meta: str, data_assembled: dict) -> list[dict]:
    results = []
    ref_price  = _normalize_int(data_assembled.get("catalogue", {}).get("low_price"))
    ref_volume = _normalize_int(data_assembled.get("catalogue", {}).get("offer_count"))

    title_price = _extract_price(title)
    meta_price  = _extract_price(meta)
    meta_volume = _extract_volume(meta)

    if title_price is not None and ref_price is not None:
        ok = title_price == ref_price
        results.append(_result(
            "Prix title == catalogue.low_price",
            ok,
            f"{title_price}€ {'==' if ok else f'≠ référence {ref_price}€'}",
        ))

    if meta_price is not None and ref_price is not None:
        ok = meta_price == ref_price
        results.append(_result(
            "Prix meta == catalogue.low_price",
            ok,
            f"{meta_price}€ {'==' if ok else f'≠ référence {ref_price}€'}",
        ))

    if meta_volume is not None and ref_volume is not None:
        ok = meta_volume == ref_volume
        results.append(_result(
            "Volume meta == catalogue.offer_count",
            ok,
            f"{meta_volume} {'==' if ok else f'≠ référence {ref_volume}'}",
        ))

    return results


# ── Check 6 : Année dans le title ─────────────────────────────────────────────

def _check_title_year(title: str) -> dict:
    check = "Année dans le title (courante ou +1)"
    current = date.today().year
    pattern = rf"\b{current}\b|\b{current}-{current+1}\b|\b{current+1}\b"
    if re.search(pattern, title):
        m = re.search(r"\b20\d{2}(?:-20\d{2})?\b", title)
        return _result(check, True, m.group(0) if m else "")
    old = re.search(r"\b(20\d{2})\b", title)
    if old and int(old.group(1)) < current:
        return _result(check, False, f"Année obsolète : {old.group(1)}")
    return _result(check, False, "Aucune année valide trouvée dans le title")


# ── Check 7 : H1 valide ───────────────────────────────────────────────────────

def _check_h1(data_assembled: dict) -> dict:
    check = "H1 présent + keyword + accents"
    h1      = data_assembled.get("current_content", {}).get("h1", "")
    keyword = data_assembled.get("textguru", {}).get("query", "")

    if not h1:
        return _result(check, False, "H1 absent ou vide (sélecteur CSS à vérifier)")

    # Accent : "Croisieres" sans accent = anomalie
    if re.search(r"\bCroisieres\b", h1, re.IGNORECASE) and "croisières" not in h1.lower():
        return _result(check, False, f"H1 sans accent : '{h1}'")

    # Keyword : au moins un mot significatif du keyword dans le H1
    kw_words = [w for w in keyword.lower().split() if len(w) > 3]
    h1_norm  = _normalize(h1)
    if kw_words and not any(_normalize(w) in h1_norm for w in kw_words):
        return _result(check, False, f"Keyword '{keyword}' non représenté dans H1 '{h1}'")

    return _result(check, True, f'"{h1}"')


# ── Check 8 : Structure top content ──────────────────────────────────────────

def _check_top_structure(top_html: str) -> list[dict]:
    results = []
    soup = BeautifulSoup(top_html, "html.parser")

    p_count  = len(soup.find_all("p"))
    h3_count = len(soup.find_all(["h2", "h3", "h4"]))
    list_count = len(soup.find_all(["ul", "ol", "li"]))

    ok = 1 <= p_count <= 3 and h3_count == 0 and list_count == 0
    results.append(_result(
        "Top : 1-3 <p>, pas de titres, pas de listes",
        ok,
        f"{p_count} <p>"
        + (f", {h3_count} titre(s) interdit(s)" if h3_count else "")
        + (f", {list_count} balise(s) liste" if list_count else ""),
    ))

    link_count = _count_internal_links(soup)
    results.append(_result(
        "Top : >= 5 liens internes",
        link_count >= 5,
        f"{link_count} lien(s)",
    ))

    return results


# ── Check 9 : Keyword en <b> dans le top content ──────────────────────────────

def _check_top_bold_keyword(top_html: str, data_assembled: dict) -> dict:
    check   = "Top : mot-clé en <b> 1-2x"
    keyword = data_assembled.get("textguru", {}).get("query", "")
    if not keyword:
        return _result(check, True, "Keyword non disponible")

    soup = BeautifulSoup(top_html, "html.parser")
    bold_texts = [_normalize(b.get_text(strip=True)) for b in soup.find_all("b")]

    # Mots distinctifs du keyword : > 4 chars, sauf "croisiere" qui est générique
    kw_distinctive = [
        _normalize(w) for w in keyword.split()
        if len(w) > 4 and _normalize(w) not in ("croisiere", "croisieres", "croisiere")
    ]
    # Fallback si le keyword ne contient que des mots génériques
    if not kw_distinctive:
        kw_distinctive = [_normalize(w) for w in keyword.split() if len(w) > 3]
    if not kw_distinctive:
        return _result(check, True, "Keyword trop court pour vérification")

    # Un <b> matche si au moins 1 mot distinctif du keyword y apparaît
    matches = sum(
        1 for bt in bold_texts
        if any(w in bt for w in kw_distinctive)
    )

    if 1 <= matches <= 2:
        return _result(check, True, f"{matches}x")
    if matches == 0:
        return _result(check, False, f"Aucun <b> contenant le keyword '{keyword}'")
    return _result(check, False, f"{matches}x en <b> — max 2 dans le top content")


# ── Check 10 : Structure destination content ──────────────────────────────────

def _check_dest_structure(dest_html: str) -> list[dict]:
    results = []
    soup = BeautifulSoup(dest_html, "html.parser")

    h2_count = len(soup.find_all("h2"))

    # H3 éditoriaux : hors FAQPage microdata
    editorial_h3s = [h3 for h3 in soup.find_all("h3") if not _is_in_faq_microdata(h3)]
    h3_count = len(editorial_h3s)

    ok = h2_count >= 1 and 2 <= h3_count <= 5
    results.append(_result(
        "Dest : H2 parent + 2-5 H3 éditoriaux",
        ok,
        f"{h2_count} H2, {h3_count} H3 éditoriaux",
    ))

    link_count = _count_internal_links(soup)
    results.append(_result(
        "Dest : >= 10 liens internes",
        link_count >= 10,
        f"{link_count} lien(s)",
    ))

    return results


# ── Check 11 : Liens en relatif ───────────────────────────────────────────────

def _check_relative_links(top_html: str, dest_html: str) -> dict:
    check = "Tous les liens en relatif /fr/..."
    soup  = BeautifulSoup(top_html + dest_html, "html.parser")
    absolute_internal = [
        a["href"] for a in soup.find_all("a", href=True)
        if re.match(r"https?://(?:www\.)?abcroisiere\.com", a["href"], re.I)
    ]
    if not absolute_internal:
        return _result(check, True)
    return _result(
        check, False,
        f"{len(absolute_internal)} lien(s) en absolu — ex: {absolute_internal[0]}",
    )


# ── Check 12 : Balises interdites ─────────────────────────────────────────────

def _check_forbidden_tags(dest_html: str) -> dict:
    check = "Pas de <strong>, <em>, <h4>, <h1> hors microdata"
    soup  = BeautifulSoup(dest_html, "html.parser")
    violations = []
    for tag_name in ("strong", "em", "h1", "h4"):
        for el in soup.find_all(tag_name):
            if not _is_in_faq_microdata(el):
                violations.append(f"<{tag_name}> '{el.get_text(strip=True)[:40]}'")

    if not violations:
        return _result(check, True)
    return _result(check, False, " | ".join(violations[:3]))


# ── Check 13 : Pas de CSS inline ─────────────────────────────────────────────

def _check_no_inline_style(dest_html: str) -> dict:
    check = "Pas de CSS inline (sauf signature auteur)"
    soup  = BeautifulSoup(dest_html, "html.parser")
    violations = []

    for el in soup.find_all(style=True):
        style = el.get("style", "")
        # Signature auteur : span avec sprite.png ou son conteneur <p>
        if "sprite.png" in style:
            continue
        parent = el.parent
        if parent and any(
            "sprite.png" in (s.get("style") or "")
            for s in parent.find_all(style=True)
        ):
            continue
        violations.append(f"<{el.name}> style='{style[:50]}'")

    if not violations:
        return _result(check, True)
    return _result(check, False, " | ".join(violations[:3]))


# ── Check 14 : Contraintes marque ────────────────────────────────────────────

def _check_brand_constraints(title: str, meta: str, top_html: str, dest_html: str) -> list[dict]:
    if not _BRAND_CONSTRAINTS:
        return []

    results = []
    full_text = " ".join([
        title, meta,
        _strip_tags(top_html),
        _strip_tags(dest_html),
    ]).lower()

    for brand, forbidden_terms in _BRAND_CONSTRAINTS.items():
        brand_lower = brand.lower()
        brand_positions = [
            m.start()
            for m in re.finditer(r"\b" + re.escape(brand_lower) + r"\b", full_text)
        ]
        if not brand_positions:
            continue

        violations: list[str] = []
        seen_terms: set[str]  = set()

        for term in forbidden_terms:
            if term in seen_terms:
                continue
            for pos in brand_positions:
                win_start = max(0, pos - 80)
                win_end   = min(len(full_text), pos + 80)
                if term in full_text[win_start:win_end]:
                    seen_terms.add(term)
                    ctx = full_text[win_start:win_end].strip()[:80]
                    violations.append(f"'{term}' : ...{ctx}...")
                    break

        if violations:
            for v in violations:
                results.append(_result(f"Contrainte marque {brand}", False, v))
        else:
            results.append(_result(f"Contrainte marque {brand}", True))

    return results


# ── Check 15 : Signature auteur ───────────────────────────────────────────────

def _check_author_signature(dest_html: str) -> dict:
    check = "Signature auteur présente en fin de dest"
    if "sprite.png" in dest_html:
        return _result(check, True)
    return _result(check, False, "Signature auteur (sprite.png) absente du destination content")


# ── Check 16 : Liens existants préservés ──────────────────────────────────────

def _check_existing_links_preserved(top_html: str, dest_html: str, data_assembled: dict) -> dict:
    check    = "Liens existants préservés"
    existing = data_assembled.get("current_content", {}).get("internal_links_existing", [])

    if not existing:
        return _result(check, True, "Aucun lien existant à préserver")

    full_html = top_html + dest_html
    missing   = [
        lnk.get("href", "") for lnk in existing
        if lnk.get("href") and lnk["href"] not in full_html
    ]

    if not missing:
        return _result(check, True, f"{len(existing)}/{len(existing)} préservés")
    return _result(
        check, False,
        f"{len(missing)} lien(s) manquant(s) : {', '.join(missing[:3])}",
    )


# ── Fonction principale ────────────────────────────────────────────────────────

def validate_seo(
    title: str,
    meta: str,
    top_html: str,
    dest_html: str,
    data_assembled: dict,
) -> dict:
    """Valide les règles SEO dures sur le contenu généré.

    Returns:
        {
            "passed":  bool,   # False = correction obligatoire (1 retry max)
            "score":   int,    # checks passés
            "total":   int,    # checks total
            "results": list[{"check": str, "passed": bool, "detail": str}]
        }
    """
    results: list[dict] = []

    results.append(_check_title_length(title))
    results.append(_check_meta_length(meta))
    results.append(_check_meta_opening(meta))
    results.append(_check_meta_no_emoji(meta))
    results.extend(_check_prices_consistent(title, meta, data_assembled))
    results.append(_check_title_year(title))
    results.append(_check_h1(data_assembled))
    results.extend(_check_top_structure(top_html))
    results.append(_check_top_bold_keyword(top_html, data_assembled))
    results.extend(_check_dest_structure(dest_html))
    results.append(_check_relative_links(top_html, dest_html))
    results.append(_check_forbidden_tags(dest_html))
    results.append(_check_no_inline_style(dest_html))
    results.extend(_check_brand_constraints(title, meta, top_html, dest_html))
    results.append(_check_author_signature(dest_html))
    results.append(_check_existing_links_preserved(top_html, dest_html, data_assembled))

    score  = sum(1 for r in results if r["passed"])
    total  = len(results)
    passed = score == total

    return {
        "passed":  passed,
        "score":   score,
        "total":   total,
        "results": results,
    }
