"""Parsing des briefs catalogue manuels.

Format attendu : Markdown avec sections ## Nom.
Spec complète dans reference/brief_catalogue_format.md.
"""

import re
from pathlib import Path


_NUMERIC_KEYS = {
    "Prix plancher",
    "Prix plafond",
    "Nombre de croisières",
    "Nombre de navires",
}

_LIST_KEYS = {
    "Compagnies top content",
    "Compagnies complètes",
    "Ports de départ FR",
    "Ports de départ internationaux",
    "Escales incontournables",
    "Navires phares",
    "Liste complète des navires",
    "Destinations couvertes",
    "Formules disponibles",
    "Durées disponibles",
}

_REQUIRED_KEYS = {"Prix plancher", "Nombre de croisières"}


def normalize_key(key: str) -> str:
    """'Prix plancher' -> 'prix_plancher'"""
    key = key.lower()
    key = key.replace(" ", "_")
    for src, dst in [("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"),
                     ("â", "a"), ("î", "i"), ("ô", "o"), ("û", "u"),
                     ("ç", "c"), ("ï", "i")]:
        key = key.replace(src, dst)
    return key


def _parse_value(key: str, raw: str):
    if key in _NUMERIC_KEYS:
        cleaned = re.sub(r"[\s ,]", "", raw)
        m = re.search(r"\d+", cleaned)
        return int(m.group()) if m else None

    if key in _LIST_KEYS:
        lines = raw.splitlines()
        bullet_lines = [ln.lstrip("-* ").strip() for ln in lines
                        if ln.strip().startswith(("-", "*", "+"))]
        if bullet_lines:
            return [item for item in bullet_lines if item]
        # Séparé par virgules (éventuellement sur plusieurs lignes)
        flat = " ".join(lines)
        return [item.strip() for item in flat.split(",") if item.strip()]

    return raw.strip()


def parse_brief(path: Path) -> dict:
    """Parse un brief catalogue Markdown et retourne un dict normalisé.

    Lève ValueError si les sections obligatoires manquent.
    """
    content = path.read_text(encoding="utf-8")

    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip()
            current_lines = []
        elif line.startswith("#"):
            # Titre # ou commentaire, ignorer
            continue
        else:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    missing = _REQUIRED_KEYS - sections.keys()
    if missing:
        raise ValueError(
            f"Brief incomplet — sections obligatoires manquantes : {missing}\n"
            f"Template disponible dans reference/brief_catalogue_format.md"
        )

    return {
        normalize_key(k): _parse_value(k, v)
        for k, v in sections.items()
    }
