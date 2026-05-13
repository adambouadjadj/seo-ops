"""
tools/sl_opportunity_scanner.py
--------------------------------
Scanner d'opportunités SEO pour les Selective Landings (SL) ABCroisière.

Analyse 90 jours de données GSC sur les pages /fr/croisieres/croisiere-* et
produit un rapport markdown + CSV priorisé pour le workflow /sl-optimize.

Usage :
    python tools/sl_opportunity_scanner.py [--days 90] [--out output/]
"""

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Imports ────────────────────────────────────────────────────────────────────
_TOOLS = Path(__file__).parent
sys.path.insert(0, str(_TOOLS))
from gsc_client import search_analytics, EXPECTED_CTR  # noqa: E402

# ── Config ─────────────────────────────────────────────────────────────────────
SL_PREFIX   = "/fr/croisieres/croisiere-"
DEFAULT_DAYS = 90
DEFAULT_OUT  = Path(__file__).parent.parent / "output" / "sl_scanner"

# Seuils
QW_POS_MIN    = 4    # position >= 4 → hors top 3
QW_POS_MAX    = 30   # position <= 30 → récupérable
QW_IMPR_MIN   = 50   # impressions min pour quick win
CTR_GAP_RATIO = 0.5  # CTR < 50% du CTR attendu
CTR_GAP_IMPR  = 30   # impressions min pour signal CTR gap
NO_CLICKS_CTR = 0.5  # CTR% seuil "pas de clics"
NO_CLICKS_IMPR = 100  # impressions min


# ── Catalogue SLs ──────────────────────────────────────────────────────────────

def _load_catalogue_slugs() -> set[str]:
    """Charge les slugs SL depuis catalogue_builder output si disponible."""
    catalogue_path = Path(__file__).parent.parent / "output" / "catalogue_sl.json"
    if not catalogue_path.exists():
        return set()
    import json
    data = json.loads(catalogue_path.read_text(encoding="utf-8"))
    slugs = set()
    for entry in (data if isinstance(data, list) else data.values()):
        if isinstance(entry, dict) and entry.get("url"):
            from urllib.parse import urlparse
            slugs.add(urlparse(entry["url"]).path)
    return slugs


# ── Scoring opportunité ────────────────────────────────────────────────────────

def _opportunity_score(row: dict) -> int:
    """Score composite pour prioriser les SLs à optimiser.

    Critères (max ~10) :
    - Position 4-10 + bonnes impressions → quick win probable (+4)
    - Position 11-20 + impressions → potentiel (+2)
    - CTR gap (< 50% attendu) → title/meta à retravailler (+3)
    - Impressions élevées sans clics → contenu plat (+2)
    """
    score = 0
    pos  = row["position"]
    impr = row["impressions"]
    ctr  = row["ctr"]

    if 4 <= pos <= 10 and impr >= QW_IMPR_MIN:
        score += 4
    elif 11 <= pos <= 20 and impr >= QW_IMPR_MIN:
        score += 2

    pos_int = round(pos)
    expected = EXPECTED_CTR.get(pos_int)
    if expected and impr >= CTR_GAP_IMPR and ctr < expected * CTR_GAP_RATIO:
        score += 3

    if ctr < NO_CLICKS_CTR and impr >= NO_CLICKS_IMPR:
        score += 2

    return score


def _opportunity_type(row: dict) -> str:
    """Libellé du type d'opportunité principal."""
    labels = []
    pos  = row["position"]
    impr = row["impressions"]
    ctr  = row["ctr"]

    if 4 <= pos <= 10 and impr >= QW_IMPR_MIN:
        labels.append("quick_win")
    elif 11 <= pos <= 30 and impr >= QW_IMPR_MIN:
        labels.append("potentiel")

    pos_int = round(pos)
    expected = EXPECTED_CTR.get(pos_int)
    if expected and impr >= CTR_GAP_IMPR and ctr < expected * CTR_GAP_RATIO:
        labels.append("ctr_gap")

    if ctr < NO_CLICKS_CTR and impr >= NO_CLICKS_IMPR:
        labels.append("no_clicks")

    return "+".join(labels) if labels else "faible"


# ── Collecte GSC ──────────────────────────────────────────────────────────────

def fetch_sl_pages(days: int) -> list[dict]:
    """Récupère les métriques de toutes les SLs /fr/croisieres/croisiere-*."""
    end   = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")

    print(f"Requête GSC : {start_str} → {end_str} (pages dimension)")
    rows = search_analytics(
        start_str, end_str,
        dimensions=["page"],
        row_limit=2500,
        extra={"dimensionFilterGroups": [{"filters": [{
            "dimension": "page",
            "operator":  "contains",
            "expression": SL_PREFIX,
        }]}]},
    )
    print(f"{len(rows)} pages SL trouvées dans GSC")

    result = []
    for r in rows:
        url  = r["keys"][0]
        path = url.replace("https://www.abcroisiere.com", "").replace("http://www.abcroisiere.com", "")
        result.append({
            "url":       url,
            "path":      path,
            "clicks":    int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr":       round(r.get("ctr", 0) * 100, 2),
            "position":  round(r.get("position", 0), 1),
        })

    return result


def fetch_top_queries_per_page(pages: list[dict], days: int) -> dict[str, list]:
    """Récupère les top 5 requêtes pour les 30 premières SLs (les plus importantes)."""
    end   = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")

    top_pages = [p for p in pages if p["impressions"] >= QW_IMPR_MIN][:30]
    queries_map: dict[str, list] = {}

    for page in top_pages:
        rows = search_analytics(
            start_str, end_str,
            dimensions=["query"],
            row_limit=5,
            extra={"dimensionFilterGroups": [{"filters": [{
                "dimension": "page",
                "operator":  "equals",
                "expression": page["url"],
            }]}]},
        )
        queries_map[page["path"]] = [
            {
                "query":    r["keys"][0],
                "clicks":   int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows
        ]

    return queries_map


# ── Rapport ───────────────────────────────────────────────────────────────────

def build_report(pages: list[dict], queries_map: dict, catalogue_slugs: set, days: int) -> str:
    today = date.today().strftime("%Y-%m-%d")
    end   = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=days + 2)).strftime("%Y-%m-%d")

    lines = [
        f"# SL Opportunity Scanner — {today}",
        f"Période analysée : {start} → {end} ({days} jours)",
        f"Pages SL dans GSC : {len(pages)}",
        "",
    ]

    # Trier par score décroissant
    scored = sorted(pages, key=lambda x: -_opportunity_score(x))

    # ── Section 1 : Quick Wins ─────────────────────────────────────────────────
    quick_wins = [p for p in scored if 4 <= p["position"] <= 10 and p["impressions"] >= QW_IMPR_MIN]
    lines += [
        f"## Quick Wins ({len(quick_wins)} pages — pos 4-10, ≥{QW_IMPR_MIN} impressions)",
        "",
        "| Page | Pos | Impressions | Clics | CTR% | Types |",
        "|------|-----|-------------|-------|------|-------|",
    ]
    for p in quick_wins[:20]:
        path   = p["path"]
        types  = _opportunity_type(p)
        qs     = queries_map.get(path, [])
        q_str  = " / ".join(q["query"] for q in qs[:3])
        lines.append(
            f"| `{path}` | {p['position']} | {p['impressions']} "
            f"| {p['clicks']} | {p['ctr']} | {types} |"
        )
        if q_str:
            lines.append(f"|  | | | | | *{q_str}* |")
    lines.append("")

    # ── Section 2 : CTR Gap ────────────────────────────────────────────────────
    ctr_gap = []
    for p in pages:
        pos_int  = round(p["position"])
        expected = EXPECTED_CTR.get(pos_int)
        if expected and p["impressions"] >= CTR_GAP_IMPR and p["ctr"] < expected * CTR_GAP_RATIO:
            ctr_gap.append({**p, "expected_ctr": expected, "gap": round(expected - p["ctr"], 1)})
    ctr_gap.sort(key=lambda x: (-x["impressions"], x["position"]))

    lines += [
        f"## CTR Gap ({len(ctr_gap)} pages — CTR < 50% du CTR attendu)",
        "",
        "| Page | Pos | CTR% | Attendu% | Écart | Impressions |",
        "|------|-----|------|----------|-------|-------------|",
    ]
    for p in ctr_gap[:20]:
        lines.append(
            f"| `{p['path']}` | {p['position']} | {p['ctr']} "
            f"| {p['expected_ctr']} | -{p['gap']} | {p['impressions']} |"
        )
    lines.append("")

    # ── Section 3 : Potentiel page 2-3 ────────────────────────────────────────
    potentiel = [p for p in scored if 11 <= p["position"] <= 30 and p["impressions"] >= QW_IMPR_MIN]
    lines += [
        f"## Potentiel page 2-3 ({len(potentiel)} pages — pos 11-30, ≥{QW_IMPR_MIN} impressions)",
        "",
        "| Page | Pos | Impressions | Clics | CTR% |",
        "|------|-----|-------------|-------|------|",
    ]
    for p in potentiel[:15]:
        lines.append(
            f"| `{p['path']}` | {p['position']} | {p['impressions']} "
            f"| {p['clicks']} | {p['ctr']} |"
        )
    lines.append("")

    # ── Section 4 : Pages sans clics ──────────────────────────────────────────
    no_clicks = sorted(
        [p for p in pages if p["ctr"] < NO_CLICKS_CTR and p["impressions"] >= NO_CLICKS_IMPR],
        key=lambda x: -x["impressions"],
    )
    lines += [
        f"## Sans clics ({len(no_clicks)} pages — CTR < {NO_CLICKS_CTR}%, ≥{NO_CLICKS_IMPR} impressions)",
        "",
        "| Page | Pos | Impressions | CTR% |",
        "|------|-----|-------------|------|",
    ]
    for p in no_clicks[:15]:
        lines.append(f"| `{p['path']}` | {p['position']} | {p['impressions']} | {p['ctr']} |")
    lines.append("")

    # ── Section 5 : SLs absentes du catalogue ─────────────────────────────────
    if catalogue_slugs:
        gsc_paths  = {p["path"] for p in pages}
        in_gsc_not_cat = gsc_paths - catalogue_slugs
        in_cat_not_gsc = catalogue_slugs - gsc_paths
        lines += [
            "## Couverture catalogue",
            "",
            f"- Pages GSC hors catalogue : **{len(in_gsc_not_cat)}**",
            f"- Pages catalogue sans trafic GSC : **{len(in_cat_not_gsc)}**",
            "",
        ]
        if in_cat_not_gsc:
            lines += [
                "### Catalogue sans trafic (à prioriser pour contenu)",
                "",
            ]
            for path in sorted(in_cat_not_gsc)[:20]:
                lines.append(f"- `{path}`")
            lines.append("")

    # ── Récap priorisé pour /sl-optimize ──────────────────────────────────────
    lines += [
        "## Priorisation recommandée pour /sl-optimize",
        "",
        "| # | Page | Score | Types | Pos | Impressions |",
        "|---|------|-------|-------|-----|-------------|",
    ]
    for i, p in enumerate(scored[:25], 1):
        score = _opportunity_score(p)
        if score == 0:
            break
        types = _opportunity_type(p)
        lines.append(
            f"| {i} | `{p['path']}` | {score} | {types} "
            f"| {p['position']} | {p['impressions']} |"
        )
    lines.append("")

    return "\n".join(lines)


def write_csv(pages: list[dict], path: Path) -> None:
    fields = ["path", "position", "impressions", "clicks", "ctr", "score", "types"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in sorted(pages, key=lambda x: -_opportunity_score(x)):
            w.writerow({
                "path":        p["path"],
                "position":    p["position"],
                "impressions": p["impressions"],
                "clicks":      p["clicks"],
                "ctr":         p["ctr"],
                "score":       _opportunity_score(p),
                "types":       _opportunity_type(p),
            })


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scanner opportunités SL /sl-optimize")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--out",  type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--no-queries", action="store_true",
                        help="Sauter la récupération des top requêtes (plus rapide)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = fetch_sl_pages(args.days)
    if not pages:
        print("Aucune page SL trouvée dans GSC — vérifiez les credentials et le filtre URL.")
        sys.exit(1)

    queries_map: dict = {}
    if not args.no_queries:
        print("Récupération des top requêtes par page (top 30)...")
        queries_map = fetch_top_queries_per_page(pages, args.days)

    catalogue_slugs = _load_catalogue_slugs()
    if catalogue_slugs:
        print(f"Catalogue chargé : {len(catalogue_slugs)} SLs")

    report = build_report(pages, queries_map, catalogue_slugs, args.days)

    today    = date.today().strftime("%Y-%m-%d")
    md_path  = out_dir / f"sl_opportunities_{today}.md"
    csv_path = out_dir / f"sl_opportunities_{today}.csv"

    md_path.write_text(report, encoding="utf-8")
    write_csv(pages, csv_path)

    print(f"\nRapport : {md_path}")
    print(f"CSV     : {csv_path}")

    # Afficher le top 10 dans le terminal
    scored = sorted(pages, key=lambda x: -_opportunity_score(x))
    print(f"\n{'─'*70}")
    print(f"{'TOP 10 SLs à optimiser':^70}")
    print(f"{'─'*70}")
    print(f"{'#':<3} {'Page':<45} {'Score':>5} {'Pos':>5} {'Impr':>6}")
    print(f"{'─'*70}")
    for i, p in enumerate(scored[:10], 1):
        score = _opportunity_score(p)
        if score == 0:
            break
        path = p["path"][:44]
        print(f"{i:<3} {path:<45} {score:>5} {p['position']:>5} {p['impressions']:>6}")
    print(f"{'─'*70}\n")


if __name__ == "__main__":
    main()
