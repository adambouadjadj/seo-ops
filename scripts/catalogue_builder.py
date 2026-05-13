#!/usr/bin/env python3
"""
catalogue_builder.py — Catalogue JSON des URLs internes ABCroisière

Construit un fichier JSON catégorisé à partir du crawl Screaming Frog,
utilisé comme source de vérité pour le maillage interne (/sl-optimize).

Usage:
    python scripts/catalogue_builder.py                    # crawl le plus récent
    python scripts/catalogue_builder.py --crawl 22-04-26  # crawl spécifique
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Chemins ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
CRAWL_BASE   = PROJECT_ROOT / "output" / "crawl_reports"
OUTPUT_DIR   = PROJECT_ROOT / "output" / "url_catalogue"
SITE_ROOT    = "https://www.abcroisiere.com"
SLUG_PREFIX  = "ABCROISIERE_"

# ── Patterns URL par catégorie ─────────────────────────────────────────────────
# Chaque catégorie = liste de regex sur l'URL relative (sans domaine).

PATTERNS: dict[str, list[str]] = {
    "destinations": [
        r"^/fr/croisieres/croisiere-[^/]+/destination,\d+,\d+/$",
    ],
    "compagnies": [
        r"^/fr/croisieres/croisiere-[^/]+/compagnie,\d+/$",
    ],
    "ports_depart": [
        r"^/fr/croisieres/croisiere-depart-[^/]+/ville,[^/]+/$",
    ],
    "navires": [
        r"^/fr/bateau-croisiere/[^/]+/navire,\d+/$",
    ],
    "mois_depart": [
        r"^/croisieres-depart-[^/]+/mois,\d+/$",
    ],
    "thematiques": [
        r"^/fr/croisieres/croisiere-[^/]+/$",           # ex: /fr/croisieres/croisiere-luxe/
        r"^/fr/theme-croisiere/[^/]+/$",                # ex: /fr/theme-croisiere/croisiere-all-inclusive/
        r"^/croisieres-(?!depart-)[a-z][a-z-]+/$",      # ex: /croisieres-vol-inclus/
    ],
    "combos_dest_mois": [
        r"^/croisiere-[^/]+-[^/]+/\d+-\d+-\d+/$",      # ex: /croisiere-mediterranee-janvier/53-0-1/
    ],
    "combos_compagnie_destination": [
        r"^/fr/croisieres/croisiere-[^/]+/[^/]+/compagnie,destination,\d+,\d+,\d+/$",
    ],
}

# Suffixes marketing à retirer du H1 / Title
_MARKETING_RE = re.compile(
    r"\s*[-–|]\s*ab\s*croisiere[s]?(?:\.com)?\s*$",
    re.IGNORECASE,
)

# URLs bruit à exclure (Fasteryze, ressources statiques)
_NOISE_RE = re.compile(r"fstrz|frz-|/static/", re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_latest_crawl() -> Path:
    folders = list(CRAWL_BASE.glob(f"{SLUG_PREFIX}*"))
    if not folders:
        raise FileNotFoundError(f"Aucun dossier crawl dans {CRAWL_BASE}")

    def parse_date(p: Path) -> datetime:
        try:
            return datetime.strptime(p.name.replace(SLUG_PREFIX, ""), "%d-%m-%y")
        except ValueError:
            return datetime.min

    return max(folders, key=parse_date)


def crawl_folder_from_date(date_str: str) -> Path:
    folder = CRAWL_BASE / f"{SLUG_PREFIX}{date_str}"
    if not folder.exists():
        raise FileNotFoundError(f"Dossier crawl introuvable : {folder}")
    return folder


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except Exception:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)


def safe_str(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none") else s


def clean_label(raw: str) -> str:
    if not raw:
        return ""
    label = _MARKETING_RE.sub("", raw.strip())
    return label.strip()


def slug_label(url: str) -> str:
    """Dernier recours : extrait un label lisible depuis le slug URL."""
    segments = [p for p in url.rstrip("/").split("/") if p]
    if not segments:
        return url
    slug = segments[-1]
    # Retirer les identifiants numériques purs
    if re.match(r"^[\d,\-]+$", slug):
        slug = segments[-2] if len(segments) >= 2 else slug
    # Nettoyer préfixes génériques
    slug = re.sub(r"^(croisiere|croisieres|croisiere-depart|navire|theme|bateau-croisiere)-?", "", slug)
    return slug.replace("-", " ").strip().title() or url


def get_label(row: pd.Series, h1_col: str, title_col: str, addr_rel: str) -> str:
    h1    = clean_label(safe_str(row.get(h1_col, "")))
    title = clean_label(safe_str(row.get(title_col, "")))
    return h1 or title or slug_label(addr_rel)


# ── Construction ──────────────────────────────────────────────────────────────

def build_catalogue(df: pd.DataFrame) -> tuple[dict, list, list, int]:
    addr_col     = "Adresse"
    status_col   = "Code HTTP"
    depth_col    = "Crawl profondeur"
    h1_col       = "H1-1"
    title_col    = "Title 1"
    indexable_col = next((c for c in df.columns if "ndexabilit" in c), None)

    rejected: list[tuple[str, str]] = []

    # 1. Status 200
    mask = df[status_col].astype(str) == "200"
    rejected += [("non-200", u) for u in df.loc[~mask, addr_col]]
    df = df[mask].copy()

    # 2. Bruit Fasteryze / statique
    mask = df[addr_col].astype(str).str.contains(_NOISE_RE.pattern, flags=re.IGNORECASE, regex=True, na=False)
    rejected += [("bruit-fstrz", u) for u in df.loc[mask, addr_col]]
    df = df[~mask].copy()

    # 3. Paramètres GET
    mask = df[addr_col].astype(str).str.contains(r"\?", regex=True, na=False)
    rejected += [("query-string", u) for u in df.loc[mask, addr_col]]
    df = df[~mask].copy()

    # 4. Indexabilité (si colonne présente)
    if indexable_col:
        mask = df[indexable_col].astype(str).str.lower() != "indexable"
        rejected += [("non-indexable", u) for u in df.loc[mask, addr_col]]
        df = df[~mask].copy()

    total_filtered = len(df)

    # URL relative + profondeur
    df = df.copy()
    df["_rel"]   = df[addr_col].astype(str).str.replace(SITE_ROOT, "", regex=False)
    df["_depth"] = pd.to_numeric(df[depth_col], errors="coerce").fillna(99).astype(int)

    # ── Application des patterns ──────────────────────────────────────────────
    matched_addrs: set[str] = set()
    catalogue:    dict[str, dict[str, str]] = {}
    duplicates:   list[dict] = []

    for category, patterns in PATTERNS.items():
        cat_mask = pd.Series(False, index=df.index)
        for pat in patterns:
            cat_mask |= df["_rel"].str.match(pat, na=False)

        sub = df[cat_mask].copy()
        matched_addrs.update(sub[addr_col].tolist())

        entries: dict[str, dict] = {}  # label → {url, depth}

        for _, row in sub.iterrows():
            url_rel = str(row["_rel"])
            depth   = int(row["_depth"])
            label   = get_label(row, h1_col, title_col, url_rel)

            if label in entries:
                prev_depth = entries[label]["depth"]
                if depth < prev_depth:
                    duplicates.append({
                        "category": category, "label": label,
                        "kept": url_rel, "dropped": entries[label]["url"],
                        "reason": f"profondeur {depth} < {prev_depth}",
                    })
                    entries[label] = {"url": url_rel, "depth": depth}
                else:
                    duplicates.append({
                        "category": category, "label": label,
                        "kept": entries[label]["url"], "dropped": url_rel,
                        "reason": f"profondeur existante {prev_depth} <= {depth}",
                    })
            else:
                entries[label] = {"url": url_rel, "depth": depth}

        catalogue[category] = {label: v["url"] for label, v in sorted(entries.items())}

    # URLs qui n'ont matché aucun pattern
    unmatched = df[~df[addr_col].isin(matched_addrs)]
    rejected += [("non-matche", u) for u in unmatched[addr_col]]

    return catalogue, duplicates, rejected, total_filtered


# ── Écriture ──────────────────────────────────────────────────────────────────

def write_outputs(
    catalogue: dict,
    duplicates: list,
    rejected: list,
    crawl_folder: Path,
    crawl_date: str,
    total_crawl: int,
    total_filtered: int,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_catalogue = sum(len(v) for v in catalogue.values())
    total_rejected  = total_crawl - total_catalogue

    meta = {
        "source_crawl_date": crawl_date,
        "source_folder":     crawl_folder.name,
        "total_urls_crawl":  total_crawl,
        "total_urls_catalogue": total_catalogue,
        "rejected_urls":     total_rejected,
        "generated_at":      datetime.now().isoformat(timespec="seconds"),
    }
    payload = {**catalogue, "_meta": meta}

    dated_path  = OUTPUT_DIR / f"catalogue_urls_{crawl_date}.json"
    latest_path = OUTPUT_DIR / "catalogue_urls_latest.json"

    for path in (dated_path, latest_path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # ── Log ───────────────────────────────────────────────────────────────────
    log_path = OUTPUT_DIR / f"catalogue_log_{crawl_date}.txt"
    lines: list[str] = []

    lines += [
        f"=== CATALOGUE BUILD LOG — {crawl_date} ===",
        f"Source  : {crawl_folder.name}",
        f"Crawl   : {total_crawl} URLs | Filtrées : {total_filtered} | Catalogue : {total_catalogue} | Rejetées : {total_rejected}",
        "",
        "--- PAR CATÉGORIE ---",
    ]
    for cat, entries in catalogue.items():
        lines.append(f"  {cat} : {len(entries)} URLs")
        for label, url in list(entries.items())[:5]:
            lines.append(f"    [{label}] {url}")

    reasons = Counter(r for r, _ in rejected)
    lines += ["", "--- TOP RAISONS DE REJET ---"]
    for reason, count in reasons.most_common(10):
        lines.append(f"  {reason} : {count}")

    lines += ["", f"--- DOUBLONS ({len(duplicates)}) ---"]
    for d in duplicates:
        lines.append(
            f"  [{d['category']}] \"{d['label']}\" "
            f"kept={d['kept']} dropped={d['dropped']} ({d['reason']})"
        )

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── Console ───────────────────────────────────────────────────────────────
    print(f"\n=== CATALOGUE ABCroisière — {crawl_date} ===")
    print(f"Source : {crawl_folder.name}")
    print(f"Crawl : {total_crawl} | Filtrées : {total_filtered} | Catalogue : {total_catalogue} | Rejetées : {total_rejected}")
    print()
    print("PAR CATÉGORIE :")
    for cat, entries in catalogue.items():
        print(f"  {cat:<40} {len(entries):>4} URLs")
        for label, url in list(entries.items())[:5]:
            print(f"    [{label[:55]}] {url}")
        print()
    print(f"Doublons  : {len(duplicates)}")
    print(f"Top rejets: {dict(reasons.most_common(5))}")
    print()
    print(f"JSON  : {dated_path}")
    print(f"JSON  : {latest_path}")
    print(f"Log   : {log_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Catalogue URLs ABCroisière depuis crawl SF")
    parser.add_argument("--crawl", default=None,
                        help="Date du crawl DD-MM-YY (ex: 22-04-26). Défaut: crawl le plus récent.")
    args = parser.parse_args()

    try:
        crawl_folder = crawl_folder_from_date(args.crawl) if args.crawl else find_latest_crawl()
    except FileNotFoundError as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(1)

    crawl_date = crawl_folder.name.replace(SLUG_PREFIX, "")

    print(f"Chargement {crawl_folder.name} ...")
    df = read_csv(crawl_folder / "interne_tous.csv")
    total_crawl = len(df)
    print(f"  {total_crawl} lignes chargées.")

    catalogue, duplicates, rejected, total_filtered = build_catalogue(df)
    write_outputs(catalogue, duplicates, rejected, crawl_folder, crawl_date, total_crawl, total_filtered)


if __name__ == "__main__":
    main()
