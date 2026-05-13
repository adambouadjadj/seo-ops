"""Décision d'ajout ou non d'une FAQ dans le destination content.

Spec complète dans reference/faq_decision_tree.md.
"""

import re

_INTERROGATIFS = re.compile(
    r"\b(comment|quand|quelle?s?|o[uù]|pourquoi|combien)\b",
    re.IGNORECASE,
)

_PAA_THRESHOLD = 3  # >= 3 PAA → signal 1


def _paa_count(serp: dict, textguru: dict) -> int:
    """Fusionne et déduplique les PAA de DataForSEO et Textguru."""
    questions: set[str] = set()

    # DataForSEO PAA
    for q in serp.get("paa", {}).get("questions", []):
        text = q.get("question", "").strip()
        if text:
            questions.add(text.lower())

    # Textguru PAA (complément)
    for q in textguru.get("paa", []):
        text = (q if isinstance(q, str) else q.get("question", "")).strip()
        if text:
            questions.add(text.lower())

    return len(questions)


def _has_featured_snippet_question(serp: dict) -> bool:
    """Featured snippet de type question/réponse (= pas tableau, présent)."""
    fs = serp.get("featured_snippet", {})
    return fs.get("present", False) and not fs.get("has_table", False)


def _guide_count_top10(serp: dict) -> int:
    return sum(
        1 for r in serp.get("organic_results", [])
        if r.get("category") == "informationnel"
        and (r.get("rank_group") or 99) <= 10
    )


def _keyword_is_interrogatif(textguru: dict) -> bool:
    keyword = textguru.get("query", "")
    return bool(_INTERROGATIFS.search(keyword))


def _collect_paa_questions(serp: dict, textguru: dict) -> list[dict]:
    """Fusionne PAA DataForSEO + Textguru, dédupliqués."""
    seen: set[str] = set()
    questions = []

    for q in serp.get("paa", {}).get("questions", []):
        text = q.get("question", "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            questions.append(q)

    for q in textguru.get("paa", []):
        text = (q if isinstance(q, str) else q.get("question", "")).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            questions.append({"question": text})

    return questions


def decide_faq(serp: dict, textguru: dict) -> dict:
    """Décide si une FAQ doit être ajoutée, et retourne les questions PAA disponibles.

    Retourne add_faq (bool), signals détectés, et les questions PAA fusionnées.
    """
    total_paa   = _paa_count(serp, textguru)
    fs_question = _has_featured_snippet_question(serp)
    guide_count = _guide_count_top10(serp)
    interrogatif = _keyword_is_interrogatif(textguru)

    signal_1 = total_paa >= _PAA_THRESHOLD
    signal_2 = fs_question
    signal_3 = guide_count >= 2
    signal_4 = interrogatif

    add_faq = signal_1 or signal_2 or signal_3 or signal_4

    signals = {
        "paa_count":             total_paa,
        "signal_1_paa":          signal_1,
        "signal_2_featured_snippet": signal_2,
        "signal_3_guides_top10": signal_3,
        "signal_4_interrogatif": signal_4,
        "guide_count_top10":     guide_count,
    }

    return {
        "add_faq":         add_faq,
        "signals":         signals,
        "paa_questions":   _collect_paa_questions(serp, textguru),
        "triggered_by":    [
            k for k, v in {
                "paa": signal_1,
                "featured_snippet": signal_2,
                "guides_informationnels": signal_3,
                "keyword_interrogatif": signal_4,
            }.items() if v
        ],
    }
