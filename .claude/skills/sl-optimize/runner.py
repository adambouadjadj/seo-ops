#!/usr/bin/env python3
"""Entry point CLI pour le skill /sl-optimize — ABCroisière.

Usage :
    python runner.py --url <URL> --type <destination|compagnie> [options]

Voir SKILL.md pour la liste complète des flags et le workflow.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

# ── Chemins projet ─────────────────────────────────────────────────────────────
SKILL_DIR    = Path(__file__).parent.resolve()
PROJECT_ROOT = SKILL_DIR.parents[2]           # seo-ops/
ENV_PATH     = PROJECT_ROOT / "tools" / ".env"
ENV_ROOT     = PROJECT_ROOT / ".env"           # .env racine (YTG_API, Flask config)
CATALOGUE    = PROJECT_ROOT / "output" / "url_catalogue" / "catalogue_urls_latest.json"

# ── Chargement .env ────────────────────────────────────────────────────────────

def _load_env(path: Path) -> None:
    if not path.exists():
        sys.exit(f"[ERREUR] .env introuvable : {path}")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# ── Utilitaires URL ────────────────────────────────────────────────────────────

_ACCENT_MAP: dict[str, str] = {
    "iles":            "îles",
    "mediterranee":    "Méditerranée",
    "caraibes":        "Caraïbes",
    "antilles":        "Antilles",
    "europe":          "Europe",
    "amerique":        "Amérique",
    "asie":            "Asie",
    "emirats":         "Émirats",
    "cote":            "Côte",
    "moyen":           "Moyen",
    "baltique":        "Baltique",
    "islande":         "Islande",
    "pacifique":       "Pacifique",
    "derniere":        "dernière",
}


def resolve_slug(url: str) -> str:
    """Extrait le slug de l'URL pour nommer le dossier output.

    /fr/croisieres/croisiere-costa-croisieres/compagnie,7/
    -> croisiere-costa-croisieres
    """
    path = url.rstrip("/").split("?")[0]
    parts = [p for p in path.split("/") if p]
    for i, part in enumerate(parts):
        if part == "croisieres" and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-2] if len(parts) >= 2 else parts[-1]


def deduce_keyword(url: str) -> str:
    """Déduit le keyword Textguru depuis le slug URL.

    croisiere-costa-croisieres -> croisière Costa Croisières
    croisiere-iles-grecques    -> croisière îles grecques
    """
    slug = resolve_slug(url)
    slug = re.sub(r"^croisiere-", "", slug)
    slug = re.sub(r"-p\d+$", "", slug)

    words = slug.split("-")
    reaccented = [_ACCENT_MAP.get(w, w) for w in words]
    return "croisière " + " ".join(reaccented)

# ── Import des modules ─────────────────────────────────────────────────────────

def _import_modules():
    """Importe tous les modules du skill.

    Donne un message explicite si un module n'est pas encore implémenté.
    """
    sys.path.insert(0, str(SKILL_DIR))
    missing = []
    modules = {}

    # Modules steps 1-7 uniquement.
    # validator_seo, validator_geo, output_formatter sont des modules
    # post-génération appelés par Claude Code après avoir produit le contenu,
    # pas par le runner.
    module_map = {
        "fetch_page":      ("modules.content_fetcher",    "fetch_page"),
        "run_diagnostics": ("modules.diagnostics_runner", "run_diagnostics"),
        "fetch_textguru":  ("modules.textguru_client",    "fetch_textguru"),
        "fetch_serp":      ("modules.serp_analyzer",      "fetch_serp"),
        "select_pattern":  ("modules.pattern_selector",   "select_pattern"),
        "decide_faq":      ("modules.faq_decision",       "decide_faq"),
        "assemble":        ("modules.data_assembler",     "assemble"),
    }

    for func_name, (mod_path, func) in module_map.items():
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            modules[func_name] = getattr(mod, func)
        except (ImportError, AttributeError):
            missing.append(f"  {mod_path}.{func}")

    if missing:
        sys.exit(
            "[ERREUR] Modules manquants (pas encore implémentés) :\n"
            + "\n".join(missing)
            + "\nLancer l'étape correspondante avant de continuer."
        )

    return modules

# ── Chargement brief ───────────────────────────────────────────────────────────

def _load_brief(brief_arg: str | None) -> dict | None:
    if brief_arg is None:
        return None
    path = Path(brief_arg)
    if not path.is_absolute():
        path = SKILL_DIR / path
    if not path.exists():
        sys.exit(f"[ERREUR] Brief introuvable : {path}")
    from modules.brief_parser import parse_brief
    return parse_brief(path)

# ── Affichage résumé final ─────────────────────────────────────────────────────

def _print_summary(assembled: dict, output_dir: Path) -> None:
    print()
    print("=" * 60)
    print(" DONNEES ASSEMBLEES — PRET POUR GENERATION")
    print("=" * 60)
    print(f"  URL        : {assembled['url']}")
    print(f"  Type       : {assembled['type']}")
    print(f"  Pattern    : {assembled['pattern']}")
    print(f"  Persona    : {assembled['persona']}")
    print(f"  FAQ        : {'OUI' if assembled['faq']['add_faq'] else 'NON'}")
    print(f"  offerCount : {assembled['catalogue']['offer_count']}")
    print(f"  lowPrice   : {assembled['catalogue']['low_price']} EUR")
    print(f"  Source     : {assembled['catalogue']['source']}")

    anomalies = assembled["diagnostics"]["anomalies_count"]
    print(f"  Anomalies  : HIGH={anomalies.get('HIGH', 0)} "
          f"MEDIUM={anomalies.get('MEDIUM', 0)} "
          f"LOW={anomalies.get('LOW', 0)}")

    print()
    print(f"  Fichier JSON : {output_dir / 'data_assembled.json'}")
    print()
    suggestions = assembled.get("link_suggestions", {})
    gaps = suggestions.get("gaps_count", 0)

    print("PROCHAINE ETAPE : Claude Code genere le contenu inline")
    print("  -> Lire data_assembled.json")
    print("  -> Consulter reference/sl_anatomy.md + examples/ pour le pattern choisi")
    print("  -> Generer : title, meta, top content, destination content")
    if assembled["faq"]["add_faq"]:
        print("  -> FAQ microdata H3 (reference/faq_decision_tree.md)")
    print("  -> Signature auteur (reference/authors.md)")
    if gaps > 0:
        print(f"  -> Maillage : {gaps} opportunites dans link_suggestions.new_opportunities")
        print("     Linker chaque URL si l'entite est naturellement presente (jamais force)")
    print("=" * 60)

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimisation des Selective Landings ABCroisiere",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url",              required=True,
                        help="URL complete de la SL cible")
    parser.add_argument("--type",             required=True,
                        choices=["destination", "compagnie"],
                        help="Type de SL")
    parser.add_argument("--brief",            default=None,
                        help="Path vers brief catalogue manuel (.md)")
    parser.add_argument("--textguru-keyword", default=None,
                        help="Override keyword Textguru (défaut: déduit de l'URL)")
    parser.add_argument("--pattern",          choices=["A", "B", "C"], default=None,
                        help="Forcer un pattern A/B/C (bypass scoring auto)")
    parser.add_argument("--dry-run",          action="store_true",
                        help="Data collection uniquement, sans generation")
    parser.add_argument("--refresh-textguru", action="store_true",
                        help="Invalide le cache Textguru")
    parser.add_argument("--refresh-serp",     action="store_true",
                        help="Invalide le cache DataForSEO")
    parser.add_argument("--mode-variables",   choices=["hardcoded", "dynamic"],
                        default="hardcoded",
                        help="Mode injection variables CMS (defaut: hardcoded)")

    args = parser.parse_args()

    # ── Setup ──────────────────────────────────────────────────────────────────
    _load_env(ENV_PATH)
    if ENV_ROOT.exists():
        _load_env(ENV_ROOT)  # .env racine : YTG_API, Flask config

    slug    = resolve_slug(args.url)
    keyword = args.textguru_keyword or deduce_keyword(args.url)

    output_dir = SKILL_DIR / "output" / str(date.today()) / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    brief = _load_brief(args.brief)

    print(f"[sl-optimize] URL         : {args.url}")
    print(f"[sl-optimize] Type        : {args.type}")
    print(f"[sl-optimize] Keyword     : {keyword}")
    print(f"[sl-optimize] Slug output : {slug}")
    print(f"[sl-optimize] Pattern     : {args.pattern or 'scoring auto'}")
    print(f"[sl-optimize] Mode vars   : {args.mode_variables}")
    print(f"[sl-optimize] Dry-run     : {args.dry_run}")
    if brief:
        print(f"[sl-optimize] Brief       : {args.brief}")
    print(f"[sl-optimize] Output dir  : {output_dir}")
    print()

    mods = _import_modules()

    # ── Étape 1 : Fetch + parse HTML ──────────────────────────────────────────
    print("[1/7] Fetch HTML + JSON-LD ...")
    fetched = mods["fetch_page"](
        url=args.url,
        cache_dir=SKILL_DIR / "cache" / "content",
    )

    # ── Étape 2 : Diagnostics ─────────────────────────────────────────────────
    print("[2/7] Diagnostics ...")
    diagnostics = mods["run_diagnostics"](fetched, sl_type=args.type, brief=brief)

    # Arrêt si check 5 bis déclenché sans brief
    if diagnostics["check_5bis_triggered"] and brief is None:
        print()
        print("[WARNING] Schema AggregateOffer suspect sur cette SL :")
        d = diagnostics["check_5bis_details"]
        print(f"  offerCount : {d['offer_count']}")
        print(f"  lowPrice   : {d['low_price']}")
        print(f"  Raison     : {d['reason']}")
        print()
        print("Le skill ne peut pas continuer sans valeurs fiables.")
        print("Fournis un brief catalogue :")
        print(f"  /sl-optimize --url {args.url} --type {args.type} --brief briefs/{slug}.md")
        print("Template : reference/brief_catalogue_format.md")
        sys.exit(1)

    # Arrêt si AggregateOffer absent sans brief
    if fetched["schema"]["product"]["offer_count"] is None and brief is None:
        print()
        print("[ERREUR] AggregateOffer absent dans le JSON-LD.")
        print("Fournis un brief catalogue :")
        print(f"  /sl-optimize --url {args.url} --type {args.type} --brief briefs/{slug}.md")
        sys.exit(1)

    # ── Étape 3 : Textguru ────────────────────────────────────────────────────
    print("[3/7] Textguru API ...")
    textguru = mods["fetch_textguru"](
        keyword=keyword,
        cache_dir=SKILL_DIR / "cache" / "textguru",
        refresh=args.refresh_textguru,
    )

    # ── Étape 4 : DataForSEO SERP ─────────────────────────────────────────────
    print("[4/7] DataForSEO SERP ...")
    serp = mods["fetch_serp"](
        keyword=keyword,
        cache_dir=SKILL_DIR / "cache" / "dataforseo",
        refresh=args.refresh_serp,
    )

    # ── Étape 5 : Pattern selector ────────────────────────────────────────────
    print("[5/7] Pattern selector ...")
    _offer_count = (
        (brief or {}).get("nombre_de_croisieres")
        or fetched["schema"]["product"].get("offer_count")
    )
    _low_price = (
        (brief or {}).get("prix_plancher")
        or fetched["schema"]["product"].get("low_price")
    )
    pattern_result = mods["select_pattern"](
        serp=serp,
        textguru=textguru,
        force_pattern=args.pattern,
        offer_count=_offer_count,
        low_price=_low_price,
    )
    scores = pattern_result["scores"]
    print(f"       -> Pattern {pattern_result['pattern_chosen']} "
          f"(A:{scores['A']} B:{scores['B']} C:{scores['C']}"
          f"{' [override]' if pattern_result.get('override_used') else ''})")

    # ── Étape 6 : FAQ decision ────────────────────────────────────────────────
    print("[6/7] FAQ decision ...")
    faq = mods["decide_faq"](serp=serp, textguru=textguru)
    paa_count = faq["signals"].get("paa_count", 0)
    print(f"       -> FAQ : {'OUI' if faq['add_faq'] else 'NON'} "
          f"({paa_count} PAA detectes)")

    # ── Étape 7 : Data assembler ──────────────────────────────────────────────
    print("[7/7] Data assembler ...")
    assembled = mods["assemble"](
        url=args.url,
        slug=slug,
        sl_type=args.type,
        mode_variables=args.mode_variables,
        fetched=fetched,
        diagnostics=diagnostics,
        textguru=textguru,
        serp=serp,
        pattern_result=pattern_result,
        faq=faq,
        brief=brief,
        catalogue_path=CATALOGUE,
    )

    assembled_path = output_dir / "data_assembled.json"
    with open(assembled_path, "w", encoding="utf-8") as f:
        json.dump(assembled, f, ensure_ascii=False, indent=2)

    # ── Étape 7bis : Link resolver ────────────────────────────────────────────
    print("[7bis] Link resolver ...")
    from modules.link_resolver import resolve_links
    catalogue_data = json.loads(CATALOGUE.read_text(encoding="utf-8")) if CATALOGUE.exists() else {}
    link_suggestions = resolve_links(assembled, catalogue_data)
    assembled["link_suggestions"] = link_suggestions
    gaps = link_suggestions.get("gaps_count", 0)
    total_scored = link_suggestions.get("total_scored", 0)
    print(f"       -> {gaps} nouvelles opportunités | {total_scored} scorées / "
          f"{link_suggestions.get('catalogue_total', 0)} catalogue")
    with open(assembled_path, "w", encoding="utf-8") as f:
        json.dump(assembled, f, ensure_ascii=False, indent=2)

    # ── Dry-run : stop ici ────────────────────────────────────────────────────
    if args.dry_run:
        print()
        print("[sl-optimize] Dry-run termine. Donnees assemblees.")
        anomalies = diagnostics["anomalies_count"]
        print(f"  Pattern    : {pattern_result['pattern_chosen']}")
        print(f"  FAQ        : {'OUI' if faq['add_faq'] else 'NON'}")
        print(f"  Anomalies  : HIGH={anomalies.get('HIGH',0)} "
              f"MEDIUM={anomalies.get('MEDIUM',0)} "
              f"LOW={anomalies.get('LOW',0)}")
        print(f"  JSON       : {assembled_path}")
        return

    # ── Résumé et instructions pour Claude Code ───────────────────────────────
    _print_summary(assembled, output_dir)


if __name__ == "__main__":
    main()
