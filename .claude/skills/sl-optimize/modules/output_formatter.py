"""Step 10 — Output formatter.

Écrit tous les fichiers de sortie dans output_dir après la génération de contenu.
Appelé par Claude Code inline après les étapes 8-9.

Usage :
    from modules.output_formatter import write_outputs
    write_outputs(
        output_dir=Path("output/2026-05-13/croisiere-msc-croisieres"),
        title="...",
        meta="...",
        top_html="...",
        dest_html="...",
        data_assembled=assembled,       # dict chargé depuis data_assembled.json
        seo_results=None,               # dict validator_seo ou None
        geo_results=None,               # dict validator_geo ou None
    )
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ── Utilitaires ────────────────────────────────────────────────────────────────

def _count_links(html: str) -> int:
    return len(re.findall(r"<a\s+[^>]*href\s*=", html, re.IGNORECASE))


def _extract_year(text: str) -> str | None:
    m = re.search(r"202[5-9](?:-202[6-9])?", text)
    return m.group(0) if m else None


def _has_emoji(text: str) -> bool:
    # € est exclu — caractère de prix attendu dans les titles/metas
    return bool(re.search(r"[☀☛→✓✗★©®™£¥°•·…«»]|[\U0001F300-\U0001FFFF]", text))


# ── Fichier 1 : title_meta.txt ─────────────────────────────────────────────────

def _write_title_meta(output_dir: Path, title: str, meta: str, data_assembled: dict) -> None:
    low_price   = data_assembled.get("catalogue", {}).get("low_price")
    offer_count = data_assembled.get("catalogue", {}).get("offer_count")

    title_len = len(title)
    meta_len  = len(meta)

    title_notes = [f"{title_len} chars"]
    if low_price:
        title_notes.append(f"prix {low_price}€")
    year = _extract_year(title)
    if year:
        title_notes.append(year)
    if _has_emoji(title):
        title_notes.append("⚠ emoji détecté")

    meta_notes = [f"{meta_len} chars"]
    if meta and meta[0].isdigit():
        meta_notes.append("entrée chiffre ✓")
    elif meta:
        first_word = meta.split()[0] if meta.split() else ""
        meta_notes.append(f"entrée: {first_word}")
    if offer_count:
        meta_notes.append(f"{offer_count} offres")
    if _has_emoji(meta):
        meta_notes.append("⚠ emoji détecté")

    lines = [
        f"TITLE ({' — '.join(title_notes)})",
        title,
        "",
        f"META ({' — '.join(meta_notes)})",
        meta,
    ]
    (output_dir / "title_meta.txt").write_text("\n".join(lines), encoding="utf-8")


# ── Fichiers 2-4 : HTML ────────────────────────────────────────────────────────

def _write_html_files(output_dir: Path, top_html: str, dest_html: str) -> None:
    (output_dir / "top_content.html").write_text(top_html, encoding="utf-8")
    (output_dir / "destination_content.html").write_text(dest_html, encoding="utf-8")
    (output_dir / "full_cms_ready.html").write_text(
        top_html + "\n\n" + dest_html, encoding="utf-8"
    )


# ── Fichier 5 : diagnostic_report.md ──────────────────────────────────────────

def _write_diagnostic_report(output_dir: Path, data_assembled: dict) -> None:
    slug      = data_assembled.get("slug", output_dir.name)
    date_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    diag      = data_assembled.get("diagnostics", {})
    anomalies = diag.get("anomalies", [])
    counts    = diag.get("anomalies_count", {})

    lines = [
        f"# Diagnostic report — {slug} — {date_str}",
        "",
        f"HIGH: {counts.get('HIGH', 0)} | MEDIUM: {counts.get('MEDIUM', 0)} | LOW: {counts.get('LOW', 0)}",
        "",
    ]

    if not anomalies:
        lines.append("Aucune anomalie détectée.")
    else:
        lines += ["| Sévérité | Code | Description | Fix suggéré |", "|---|---|---|---|"]
        for a in anomalies:
            sev         = a.get("severity", "")
            code        = a.get("code", "")
            description = a.get("description", "").replace("|", "\\|")
            fix         = a.get("suggested_fix", "").replace("|", "\\|")
            lines.append(f"| {sev} | `{code}` | {description} | {fix} |")

    (output_dir / "diagnostic_report.md").write_text("\n".join(lines), encoding="utf-8")


# ── Fichier 6 : maillage_manquant.md ──────────────────────────────────────────

def _write_maillage_manquant(output_dir: Path, data_assembled: dict) -> None:
    slug         = data_assembled.get("slug", output_dir.name)
    date_str     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suggestions  = data_assembled.get("link_suggestions", {})
    opportunities = suggestions.get("new_opportunities", [])

    lines = [
        f"# Maillage manquant — {slug} — {date_str}",
        "",
        f"{len(opportunities)} URLs du catalogue non liées sur cette SL.",
        "",
    ]

    if not opportunities:
        lines.append("Aucune opportunité identifiée.")
    else:
        lines += ["| Score | Catégorie | Label | URL |", "|---|---|---|---|"]
        for opp in opportunities[:30]:
            score    = opp.get("score", 0)
            category = opp.get("category", "")
            label    = opp.get("label", "").replace("|", "\\|")
            href     = opp.get("href", "")
            lines.append(f"| {score} | {category} | {label} | `{href}` |")

        if len(opportunities) > 30:
            lines.append(f"\n_{len(opportunities) - 30} autres opportunités non affichées._")

    (output_dir / "maillage_manquant.md").write_text("\n".join(lines), encoding="utf-8")


# ── Fichier 7 : bilan_seo.md ──────────────────────────────────────────────────

def _write_bilan_seo(output_dir: Path, seo_results: dict | None, slug: str) -> None:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if seo_results is None:
        content = (
            f"# Bilan SEO — {slug} — {date_str}\n\n"
            "_validator_seo non encore implémenté — validation manuelle._\n"
        )
        (output_dir / "bilan_seo.md").write_text(content, encoding="utf-8")
        return

    passed  = seo_results.get("passed", False)
    score   = seo_results.get("score", 0)
    total   = seo_results.get("total", 0)
    results = seo_results.get("results", [])
    status  = "✅ PASS" if passed else "❌ FAIL"

    lines = [
        f"# Bilan SEO — {slug} — {date_str}",
        "",
        f"## Résultat global : {status} ({score}/{total})",
        "",
        "| Check | Statut | Détail |",
        "|---|---|---|",
    ]
    for r in results:
        icon   = "✅" if r.get("passed") else "❌"
        check  = r.get("check", "").replace("|", "\\|")
        detail = r.get("detail", "").replace("|", "\\|")
        lines.append(f"| {check} | {icon} | {detail} |")

    (output_dir / "bilan_seo.md").write_text("\n".join(lines), encoding="utf-8")


# ── Fichier 8 : bilan_geo.md ──────────────────────────────────────────────────

def _write_bilan_geo(output_dir: Path, geo_results: dict | None, slug: str) -> None:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if geo_results is None:
        content = (
            f"# Bilan GEO — {slug} — {date_str}\n\n"
            "_validator_geo non encore implémenté — validation manuelle._\n"
        )
        (output_dir / "bilan_geo.md").write_text(content, encoding="utf-8")
        return

    score   = geo_results.get("score", 0)
    total   = geo_results.get("total", 0)
    results = geo_results.get("results", [])

    lines = [
        f"# Bilan GEO — {slug} — {date_str}",
        "",
        f"## Score : {score}/{total}",
        "",
        "| Signal | Statut | Détail |",
        "|---|---|---|",
    ]
    for r in results:
        icon   = "✅" if r.get("passed") else "⚠️"
        check  = r.get("check", "").replace("|", "\\|")
        detail = r.get("detail", "").replace("|", "\\|")
        lines.append(f"| {check} | {icon} | {detail} |")

    (output_dir / "bilan_geo.md").write_text("\n".join(lines), encoding="utf-8")


# ── Fichier 9 : metadata.json ─────────────────────────────────────────────────

def _write_metadata(
    output_dir: Path,
    title: str,
    meta: str,
    top_html: str,
    dest_html: str,
    data_assembled: dict,
    seo_results: dict | None,
    geo_results: dict | None,
) -> None:
    pr   = data_assembled.get("pattern_result", {})
    faq  = data_assembled.get("faq", {})
    diag = data_assembled.get("diagnostics", {})
    ls   = data_assembled.get("link_suggestions", {})

    metadata: dict = {
        "url":              data_assembled.get("url"),
        "slug":             data_assembled.get("slug"),
        "type":             data_assembled.get("type"),
        "pattern_chosen":   pr.get("pattern_chosen"),
        "pattern_scores":   pr.get("scores", {}),
        "pattern_signals":  pr.get("signals", {}),
        "override_used":    pr.get("override_used", False),
        "fallback_used":    pr.get("fallback_used", False),
        "persona":          data_assembled.get("persona"),
        "faq_added":        faq.get("add_faq", False),
        "faq_signals":      faq.get("signals", {}),
        "mode_variables":   data_assembled.get("mode_variables"),
        "textguru_guide_id":    data_assembled.get("textguru", {}).get("guide_id"),
        "dataforseo_cost_usd":  data_assembled.get("serp", {}).get("cost_usd"),
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "anomalies_count":  diag.get("anomalies_count", {}),
        "title_len":        len(title),
        "meta_len":         len(meta),
        "links_top_content":    _count_links(top_html),
        "links_dest_content":   _count_links(dest_html),
        "existing_links_count": len(
            data_assembled.get("current_content", {}).get("internal_links_existing", [])
        ),
        "new_link_opportunities_total": ls.get("gaps_count", 0),
    }

    if seo_results is not None:
        metadata["seo_validation"] = "PASS" if seo_results.get("passed") else "FAIL"
        metadata["seo_score"]      = f"{seo_results.get('score', 0)}/{seo_results.get('total', 0)}"

    if geo_results is not None:
        metadata["geo_score"] = f"{geo_results.get('score', 0)}/{geo_results.get('total', 0)}"

    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Fonction principale ────────────────────────────────────────────────────────

def write_outputs(
    output_dir: Path,
    title: str,
    meta: str,
    top_html: str,
    dest_html: str,
    data_assembled: dict,
    seo_results: dict | None = None,
    geo_results: dict | None = None,
) -> None:
    """Écrit tous les fichiers de sortie dans output_dir.

    Args:
        output_dir     : répertoire de sortie (créé si absent)
        title          : title généré
        meta           : meta description générée
        top_html       : HTML top content (sans div wrapper)
        dest_html      : HTML destination content (sans div wrapper, inclut FAQ + signature)
        data_assembled : dict chargé depuis data_assembled.json
        seo_results    : dict retourné par validator_seo.validate_seo() — None si pas encore implémenté
        geo_results    : dict retourné par validator_geo.validate_geo() — None si pas encore implémenté
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = data_assembled.get("slug", output_dir.name)

    _write_title_meta(output_dir, title, meta, data_assembled)
    _write_html_files(output_dir, top_html, dest_html)
    _write_diagnostic_report(output_dir, data_assembled)
    _write_maillage_manquant(output_dir, data_assembled)
    _write_bilan_seo(output_dir, seo_results, slug)
    _write_bilan_geo(output_dir, geo_results, slug)
    _write_metadata(output_dir, title, meta, top_html, dest_html, data_assembled, seo_results, geo_results)

    # Résumé console
    opp_count = data_assembled.get("link_suggestions", {}).get("gaps_count", 0)
    anom      = data_assembled.get("diagnostics", {}).get("anomalies_count", {})
    seo_status = (
        "PASS" if (seo_results or {}).get("passed")
        else "non validé" if seo_results is None
        else "FAIL"
    )
    geo_status = (
        f"score {geo_results.get('score')}/{geo_results.get('total')}"
        if geo_results else "non validé"
    )

    print(f"[output_formatter] {output_dir}")
    print(f"  title_meta.txt            {len(title)} / {len(meta)} chars")
    print(f"  top_content.html          {_count_links(top_html)} liens")
    print(f"  destination_content.html  {_count_links(dest_html)} liens")
    print(f"  full_cms_ready.html")
    print(f"  diagnostic_report.md      {anom}")
    print(f"  maillage_manquant.md      {opp_count} opportunités")
    print(f"  bilan_seo.md              {seo_status}")
    print(f"  bilan_geo.md              {geo_status}")
    print(f"  metadata.json")
