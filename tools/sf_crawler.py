#!/usr/bin/env python3
"""
sf_crawler.py — Screaming Frog CLI : crawl + rapport santé SEO

Usage:
    python tools/sf_crawler.py                                   # abcroisiere.com
    python tools/sf_crawler.py --url https://www.promocroisiere.com
    python tools/sf_crawler.py --url https://www.abcroisiere.com/croisiere-mediterranee/
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

# ── Config ──────────────────────────────────────────────────────────────────

SF_CLI = r"C:\Program Files (x86)\Screaming Frog SEO Spider\ScreamingFrogSEOSpiderCli.exe"
DEFAULT_URL = "https://www.abcroisiere.com"

PROJECT_ROOT = Path(__file__).parent.parent
CRAWL_OUTPUT_BASE = PROJECT_ROOT / "output" / "crawl_reports"

# Tabs SF à exporter (nom onglet:filtre)
EXPORT_TABS = "Internal:All,Response Codes:All,Page Titles:All,H1:All,Images:All"

# Exports groupés
BULK_EXPORTS = "All Inlinks"


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_domain_slug(url: str) -> str:
    """abcroisiere.com → ABCROISIERE"""
    netloc = urlparse(url).netloc.replace("www.", "")
    return netloc.split(".")[0].upper()


def load_csv(folder: Path, filename: str) -> pd.DataFrame:
    """Charge un CSV SF, retourne DataFrame vide si introuvable."""
    path = folder / filename
    if not path.exists():
        # SF peut nommer différemment selon la version — on cherche par pattern
        candidates = list(folder.glob(f"*{filename.replace('_', '*')}*"))
        if candidates:
            path = candidates[0]
            print(f"  [INFO] CSV trouvé sous nom alternatif : {path.name}")
        else:
            print(f"  [WARN] Fichier introuvable : {filename} (dossier : {folder})")
            print(f"         Fichiers disponibles : {[f.name for f in folder.glob('*.csv')]}")
            return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def find_col(df: pd.DataFrame, *patterns: str) -> str | None:
    """Trouve le nom exact d'une colonne par pattern insensible à la casse."""
    for pattern in patterns:
        for col in df.columns:
            if pattern.lower() in col.lower():
                return col
    return None


# ── Crawl ────────────────────────────────────────────────────────────────────

def run_crawl(url: str, output_folder: Path) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)

    cmd = [
        SF_CLI,
        "--headless",
        "--crawl", url,
        "--output-folder", str(output_folder),
        "--export-tabs", EXPORT_TABS,
        "--bulk-export", BULK_EXPORTS,
        "--overwrite",
    ]

    print(f"Crawl : {url}")
    print(f"Output CSVs : {output_folder}\n")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nErreur SF (code retour {result.returncode})")
        sys.exit(1)

    print("\nCrawl termine.")


# ── Rapport Markdown ─────────────────────────────────────────────────────────

def _load_inlinks(folder: Path, filename: str) -> pd.DataFrame:
    """Charge Source, Destination, Type et Texte Alt du fichier inlinks (peut faire ~450 Mo)."""
    path = folder / filename
    if not path.exists():
        print(f"  [WARN] Fichier introuvable : {filename}")
        return pd.DataFrame()
    try:
        sample = pd.read_csv(path, encoding="utf-8-sig", nrows=1)
        cols = sample.columns.tolist()
        src_col  = next((c for c in cols if c.lower() in ("source", "source url") or c.lower().startswith("source")), None)
        dest_col = next((c for c in cols if "destination" in c.lower()), None)
        type_col = next((c for c in cols if c.lower() == "type"), None)
        alt_col  = next((c for c in cols if "alt" in c.lower()), None)
        usecols  = [c for c in [src_col, dest_col, type_col, alt_col] if c]
        if usecols:
            return pd.read_csv(path, encoding="utf-8-sig", usecols=usecols, low_memory=False)
    except Exception:
        pass
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

def generate_md(url: str, output_folder: Path, date_str: str, slug: str) -> Path:
    df_internal = load_csv(output_folder, "interne_tous.csv")
    df_response = load_csv(output_folder, "codes_de_réponse_tous.csv")
    df_titles   = load_csv(output_folder, "title_des_pages_tous.csv")
    df_h1       = load_csv(output_folder, "h1_tous.csv")
    df_images   = load_csv(output_folder, "images_tous.csv")
    # Chargement allégé : source + destination uniquement (fichier ~450 Mo)
    df_inlinks  = _load_inlinks(output_folder, "liens_entrants_tous.csv")

    # Exclure les URLs de bruit : Fasteryze (chemins /fstrz/ et params ?frz-) + ressources statiques
    NOISE_PATTERNS = ["fstrz", "frz-", "/static/"]

    def _is_noise(series: pd.Series) -> pd.Series:
        mask = pd.Series(False, index=series.index)
        for pat in NOISE_PATTERNS:
            mask |= series.astype(str).str.contains(pat, case=False, na=False)
        return mask

    def _drop_noise(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        url_col = find_col(df, "address", "adresse", "source", "destination", "src")
        if url_col:
            return df[~_is_noise(df[url_col])]
        return df

    df_internal = _drop_noise(df_internal)
    df_response = _drop_noise(df_response)
    df_titles   = _drop_noise(df_titles)
    df_h1       = _drop_noise(df_h1)
    df_images   = _drop_noise(df_images)
    if not df_inlinks.empty:
        for col in df_inlinks.columns:
            df_inlinks = df_inlinks[~_is_noise(df_inlinks[col])]

    lines = []
    lines += [
        f"# Rapport de santé SEO — {slug}",
        f"**Site crawlé :** {url}",
        f"**Date :** {date_str}",
        "",
    ]

    # ── 1. Résumé global ────────────────────────────────────────────────────
    lines += ["## 1. Résumé global", ""]

    if not df_internal.empty:
        total = len(df_internal)
        lines.append(f"- **Pages crawlées au total :** {total}")

        status_col = find_col(df_internal, "status code", "code http")
        if status_col:
            for code, count in df_internal[status_col].value_counts().items():
                lines.append(f"  - {code} : {count}")

        indexable_col = find_col(df_internal, "indexability", "indexabilit")
        if indexable_col:
            n_indexable = (df_internal[indexable_col] == "Indexable").sum()
            lines.append(f"- **Pages indexables :** {n_indexable}")
    else:
        lines.append("- Données internal_all.csv non disponibles.")
    lines.append("")

    # ── 2. Erreurs HTTP ─────────────────────────────────────────────────────
    lines += ["## 2. Erreurs & redirections HTTP", ""]

    src = df_response if not df_response.empty else df_internal
    addr_col   = find_col(src, "address", "adresse")
    status_col = find_col(src, "status code", "code http")
    dest_redir_col = find_col(src, "redirect url", "url de redirection", "redirect uri", "destination")

    if not src.empty and status_col:
        status_str = src[status_col].astype(str)
        errors_4xx  = src[status_str.str.startswith("4")]
        errors_5xx  = src[status_str.str.startswith("5")]
        redirects   = src[status_str.str.startswith("3")]

        lines.append(f"- **4xx (erreurs client) :** {len(errors_4xx)}")
        if not errors_4xx.empty and addr_col:
            for _, row in errors_4xx.head(20).iterrows():
                lines.append(f"  - `{row[addr_col]}` → {row[status_col]}")

        lines.append(f"- **5xx (erreurs serveur) :** {len(errors_5xx)}")
        if not errors_5xx.empty and addr_col:
            for _, row in errors_5xx.head(10).iterrows():
                lines.append(f"  - `{row[addr_col]}` → {row[status_col]}")

        lines.append(f"- **3xx (redirections) :** {len(redirects)}")
        if not redirects.empty and addr_col:
            for _, row in redirects.head(20).iterrows():
                dest = f" → `{row[dest_redir_col]}`" if dest_redir_col and pd.notna(row.get(dest_redir_col, None)) else ""
                lines.append(f"  - `{row[addr_col]}`{dest} ({row[status_col]})")
    else:
        lines.append("- Données HTTP non disponibles.")
    lines.append("")

    # ── 3. Balises Title ────────────────────────────────────────────────────
    lines += ["## 3. Balises Title", ""]

    if not df_titles.empty:
        addr_col   = find_col(df_titles, "address", "adresse")
        title_col  = find_col(df_titles, "title 1")
        length_col = find_col(df_titles, "title 1 length", "title length", "longueur du title")

        if title_col:
            missing = df_titles[df_titles[title_col].isna() | (df_titles[title_col].astype(str).str.strip() == "")]
            lines.append(f"- **Titles manquants :** {len(missing)}")
            if not missing.empty and addr_col:
                for _, row in missing.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}`")

            dupes = df_titles[
                df_titles.duplicated(subset=[title_col], keep=False)
                & df_titles[title_col].notna()
                & (df_titles[title_col].astype(str).str.strip() != "")
            ]
            lines.append(f"- **Titles dupliqués :** {len(dupes)}")
            if not dupes.empty:
                for title, group in list(dupes.groupby(title_col))[:5]:
                    lines.append(f"  - `{str(title)[:80]}` ({len(group)} pages)")

        if length_col:
            too_long  = df_titles[pd.to_numeric(df_titles[length_col], errors="coerce") > 60]
            too_short = df_titles[
                (pd.to_numeric(df_titles[length_col], errors="coerce") < 30)
                & (pd.to_numeric(df_titles[length_col], errors="coerce") > 0)
            ]
            lines.append(f"- **Titles > 60 caractères :** {len(too_long)}")
            lines.append(f"- **Titles < 30 caractères :** {len(too_short)}")
    else:
        lines.append("- Données page_titles_all.csv non disponibles.")
    lines.append("")

    # ── 4. Balises H1 ───────────────────────────────────────────────────────
    lines += ["## 4. Balises H1", ""]

    if not df_h1.empty:
        addr_col = find_col(df_h1, "address", "adresse")
        h1_col   = find_col(df_h1, "h1-1")
        h1_2_col = find_col(df_h1, "h1-2")

        if h1_col:
            missing_h1 = df_h1[df_h1[h1_col].isna() | (df_h1[h1_col].astype(str).str.strip() == "")]
            lines.append(f"- **H1 manquants :** {len(missing_h1)}")
            if not missing_h1.empty and addr_col:
                for _, row in missing_h1.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}`")

            dupes_h1 = df_h1[
                df_h1.duplicated(subset=[h1_col], keep=False)
                & df_h1[h1_col].notna()
                & (df_h1[h1_col].astype(str).str.strip() != "")
            ]
            lines.append(f"- **H1 dupliqués :** {len(dupes_h1)}")
            if not dupes_h1.empty:
                for h1, group in list(dupes_h1.groupby(h1_col))[:5]:
                    lines.append(f"  - `{str(h1)[:80]}` ({len(group)} pages)")

        if h1_2_col:
            multi_h1 = df_h1[df_h1[h1_2_col].notna() & (df_h1[h1_2_col].astype(str).str.strip() != "")]
            lines.append(f"- **Pages avec plusieurs H1 :** {len(multi_h1)}")
    else:
        lines.append("- Données h1_all.csv non disponibles.")
    lines.append("")

    # ── 5. Pages sans inlinks internes ──────────────────────────────────────
    lines += ["## 5. Pages sans inlinks internes", ""]

    if not df_inlinks.empty and not df_internal.empty:
        dest_col = find_col(df_inlinks, "destination")
        addr_col = find_col(df_internal, "address", "adresse")

        if dest_col and addr_col:
            linked   = set(df_inlinks[dest_col].dropna().unique())
            all_urls = set(df_internal[addr_col].dropna().unique())
            orphans  = sorted(all_urls - linked)
            lines.append(f"- **Pages sans inlinks :** {len(orphans)}")
            for u in orphans[:20]:
                lines.append(f"  - `{u}`")
            if len(orphans) > 20:
                lines.append(f"  - *(et {len(orphans) - 20} autres...)*")
    else:
        lines.append("- Données inlinks non disponibles.")
    lines.append("")

    # ── 6. Meta Descriptions ────────────────────────────────────────────────
    lines += ["## 6. Meta Descriptions", ""]

    if not df_internal.empty:
        addr_col    = find_col(df_internal, "address", "adresse")
        meta_col    = find_col(df_internal, "meta description 1", "méta description 1", "meta description")
        meta_len_col = find_col(df_internal, "meta description 1 length", "longueur de la meta description", "longueur meta")

        if meta_col:
            missing_meta = df_internal[df_internal[meta_col].isna() | (df_internal[meta_col].astype(str).str.strip() == "")]
            lines.append(f"- **Meta descriptions manquantes :** {len(missing_meta)}")
            if not missing_meta.empty and addr_col:
                for _, row in missing_meta.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}`")

            dupes_meta = df_internal[
                df_internal.duplicated(subset=[meta_col], keep=False)
                & df_internal[meta_col].notna()
                & (df_internal[meta_col].astype(str).str.strip() != "")
            ]
            lines.append(f"- **Meta descriptions dupliquées :** {len(dupes_meta)}")
            if not dupes_meta.empty:
                for meta, group in list(dupes_meta.groupby(meta_col))[:5]:
                    lines.append(f"  - `{str(meta)[:80]}` ({len(group)} pages)")

        if meta_len_col:
            meta_len_num = pd.to_numeric(df_internal[meta_len_col], errors="coerce")
            too_long_meta  = df_internal[meta_len_num > 155]
            too_short_meta = df_internal[(meta_len_num < 70) & (meta_len_num > 0)]
            lines.append(f"- **Meta descriptions > 155 caractères :** {len(too_long_meta)}")
            lines.append(f"- **Meta descriptions < 70 caractères :** {len(too_short_meta)}")
        elif not meta_col:
            lines.append("- Colonnes meta description non trouvées dans les données.")
    else:
        lines.append("- Données internal non disponibles.")
    lines.append("")

    # ── 7. Canoniques ───────────────────────────────────────────────────────
    lines += ["## 7. Canoniques", ""]

    if not df_internal.empty:
        addr_col      = find_col(df_internal, "address", "adresse")
        canonical_col = find_col(df_internal, "canonical link element 1", "élément de lien en version canonique", "canonical")

        if canonical_col and addr_col:
            no_canonical = df_internal[df_internal[canonical_col].isna() | (df_internal[canonical_col].astype(str).str.strip() == "")]
            lines.append(f"- **Pages sans canonical :** {len(no_canonical)}")

            has_canonical = df_internal[df_internal[canonical_col].notna() & (df_internal[canonical_col].astype(str).str.strip() != "")]
            non_self = has_canonical[
                has_canonical[canonical_col].astype(str).str.strip() != has_canonical[addr_col].astype(str).str.strip()
            ]
            lines.append(f"- **Pages avec canonical non-auto-référencé :** {len(non_self)}")
            if not non_self.empty:
                for _, row in non_self.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}` → `{str(row[canonical_col])[:80]}`")
        else:
            lines.append("- Colonne canonical non trouvée dans les données.")
    else:
        lines.append("- Données internal non disponibles.")
    lines.append("")

    # ── 8. Profondeur de crawl ───────────────────────────────────────────────
    lines += ["## 8. Profondeur de crawl", ""]

    if not df_internal.empty:
        addr_col  = find_col(df_internal, "address", "adresse")
        depth_col = find_col(df_internal, "crawl depth", "crawl profondeur", "profondeur")

        if depth_col:
            depth_num = pd.to_numeric(df_internal[depth_col], errors="coerce")
            dist = depth_num.value_counts().sort_index()
            lines.append("- **Distribution par profondeur :**")
            for depth, count in dist.items():
                lines.append(f"  - Niveau {int(depth)} : {count} pages")

            deep_pages = df_internal[depth_num > 5]
            lines.append(f"- **Pages à profondeur > 5 :** {len(deep_pages)}")
            if not deep_pages.empty and addr_col:
                for _, row in deep_pages.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}` (niveau {int(pd.to_numeric(row[depth_col], errors='coerce'))})")
        else:
            lines.append("- Colonne profondeur de crawl non trouvée dans les données.")
    else:
        lines.append("- Données internal non disponibles.")
    lines.append("")

    # ── 9. Pages lentes ─────────────────────────────────────────────────────
    lines += ["## 9. Pages lentes", ""]

    if not df_internal.empty:
        addr_col    = find_col(df_internal, "address", "adresse")
        resp_col    = find_col(df_internal, "response time", "temps de réponse", "temps réponse")

        if resp_col:
            resp_num = pd.to_numeric(df_internal[resp_col], errors="coerce")
            slow = df_internal[resp_num > 2000].copy()
            slow["_resp_num"] = pd.to_numeric(slow[resp_col], errors="coerce")
            slow = slow.sort_values("_resp_num", ascending=False)
            lines.append(f"- **Pages lentes (> 2000 ms) :** {len(slow)}")
            if not slow.empty and addr_col:
                for _, row in slow.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}` — {int(row['_resp_num'])} ms")
        else:
            lines.append("- Colonne temps de réponse non trouvée dans les données.")
    else:
        lines.append("- Données internal non disponibles.")
    lines.append("")

    # ── 10. Quasi-doublons de contenu ────────────────────────────────────────
    lines += ["## 10. Quasi-doublons de contenu", ""]

    if not df_internal.empty:
        addr_col        = find_col(df_internal, "address", "adresse")
        near_dup_col    = find_col(df_internal, "near duplicate", "quasi-doublon le plus proche", "quasi doublon")
        near_dup_cnt_col = find_col(df_internal, "near duplicate count", "nombre de quasi-doublons", "nb quasi")

        if near_dup_col:
            has_dupes = df_internal[df_internal[near_dup_col].notna() & (df_internal[near_dup_col].astype(str).str.strip() != "")]
            lines.append(f"- **Pages ayant au moins 1 quasi-doublon :** {len(has_dupes)}")
            if not has_dupes.empty and addr_col:
                for _, row in has_dupes.head(10).iterrows():
                    lines.append(f"  - `{row[addr_col]}` ≈ `{str(row[near_dup_col])[:80]}`")
        else:
            lines.append("- Colonne quasi-doublons non trouvée dans les données.")
    else:
        lines.append("- Données internal non disponibles.")
    lines.append("")

    # ── 11. Images sans attribut alt ────────────────────────────────────────
    lines += ["## 11. Images sans attribut alt", ""]

    if not df_inlinks.empty:
        type_col    = find_col(df_inlinks, "type")
        alt_col     = find_col(df_inlinks, "texte alt", "alt text", "alt")
        dest_col    = find_col(df_inlinks, "destination")
        src_col_il  = find_col(df_inlinks, "source")

        if type_col and alt_col:
            img_links = df_inlinks[df_inlinks[type_col].astype(str).str.lower() == "image"]
            missing_alt = img_links[img_links[alt_col].isna() | (img_links[alt_col].astype(str).str.strip() == "")]
            lines.append(f"- **Images sans alt :** {len(missing_alt)}")
            if not missing_alt.empty and dest_col:
                for _, row in missing_alt.head(20).iterrows():
                    page = f" (sur `{row[src_col_il]}`)" if src_col_il else ""
                    lines.append(f"  - `{str(row[dest_col])[:100]}`{page}")
                if len(missing_alt) > 20:
                    lines.append(f"  - *(et {len(missing_alt) - 20} autres...)*")
        else:
            lines.append("- Colonnes Type/Alt Text non trouvées dans les données inlinks.")
    else:
        lines.append("- Données inlinks non disponibles.")
    lines.append("")

    # ── 12. Liens internes brisés ────────────────────────────────────────────
    lines += ["## 12. Liens internes brisés", ""]

    if not df_inlinks.empty and not df_internal.empty:
        src_il_col  = find_col(df_inlinks, "source")
        dest_il_col = find_col(df_inlinks, "destination")
        addr_col    = find_col(df_internal, "address", "adresse")
        status_col  = find_col(df_internal, "status code", "code http")

        if src_il_col and dest_il_col and addr_col and status_col:
            # Pages en erreur (4xx / 5xx)
            status_str = df_internal[status_col].astype(str)
            broken_urls = set(
                df_internal[status_str.str.startswith("4") | status_str.str.startswith("5")][addr_col].dropna()
            )
            # Inlinks pointant vers ces pages
            broken_inlinks = df_inlinks[df_inlinks[dest_il_col].isin(broken_urls)]
            lines.append(f"- **Liens internes pointant vers une page en erreur :** {len(broken_inlinks)}")
            if not broken_inlinks.empty:
                # Dédupliquer par (source, destination) pour le top 20
                shown = broken_inlinks.drop_duplicates(subset=[src_il_col, dest_il_col]).head(20)
                for _, row in shown.iterrows():
                    lines.append(f"  - `{row[src_il_col]}` → `{row[dest_il_col]}`")
                if len(broken_inlinks) > 20:
                    lines.append(f"  - *(et {len(broken_inlinks) - 20} autres...)*")
        else:
            missing = []
            if not src_il_col:  missing.append("colonne source inlinks")
            if not dest_il_col: missing.append("colonne destination inlinks")
            lines.append(f"- Données insuffisantes : {', '.join(missing)}.")
    else:
        lines.append("- Données inlinks non disponibles.")
    lines.append("")

    # ── Écriture ─────────────────────────────────────────────────────────────
    md_path = output_folder / f"crawl_{slug}_{date_str}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Rapport .md : {md_path}")
    return md_path


# ── Rapport HTML ─────────────────────────────────────────────────────────────

def md_to_html(md_path: Path) -> Path:
    content = md_path.read_text(encoding="utf-8")
    html_parts = []
    in_header = False
    content_open = False

    for line in content.split("\n"):
        if line.startswith("# "):
            html_parts.append(f'<div class="header"><h1>{line[2:]}</h1>')
            in_header = True
        elif in_header and line.startswith("**Site crawlé :**"):
            value = line.split(":**", 1)[1].strip()
            html_parts.append(f'<p style="margin:6px 0 0;font-size:13px;color:#a8c4e0;">{value}</p>')
        elif in_header and line.startswith("**Date :**"):
            value = line.split(":**", 1)[1].strip()
            html_parts.append(f'<p style="margin:2px 0 0;font-size:13px;color:#a8c4e0;">{value}</p>')
        elif line.startswith("## "):
            if in_header:
                html_parts.append('</div><div class="content">')
                in_header = False
                content_open = True
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("  - "):
            html_parts.append(f'<li class="sub">{_inline(line[4:])}</li>')
        elif line.startswith("- "):
            html_parts.append(f"<li>{_inline(line[2:])}</li>")
        elif line.strip() == "":
            pass
        else:
            html_parts.append(f"<p>{_inline(line)}</p>")

    if content_open:
        html_parts.append("</div>")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: Arial, Helvetica, sans-serif;
      background: #f4f4f4;
      margin: 0; padding: 24px 16px;
      color: #333; line-height: 1.6;
    }}
    .wrapper {{
      max-width: 860px; margin: 0 auto;
      background: #fff;
      border-radius: 4px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,.08);
    }}
    .header {{
      background: #1a3a5c;
      padding: 24px 32px;
    }}
    .header h1 {{
      margin: 0; font-size: 18px; color: #fff; font-weight: bold;
    }}
    .header p {{
      margin: 6px 0 0; font-size: 13px; color: #a8c4e0;
    }}
    .content {{ padding: 8px 32px 32px; }}
    h2 {{
      font-size: 14px; font-weight: bold;
      color: #1a3a5c;
      border-bottom: 2px solid #1a3a5c;
      padding-bottom: 6px;
      margin: 28px 0 10px;
    }}
    ul {{ margin: 4px 0 0 0; padding: 0; list-style: none; }}
    li {{ font-size: 13px; margin: 4px 0; padding: 3px 0; }}
    li.sub {{
      margin-left: 20px; color: #555;
      border-left: 3px solid #dde4ec;
      padding-left: 10px;
    }}
    code {{
      background: #f0f4f8; padding: 1px 5px;
      border-radius: 3px; font-size: 0.85em;
      word-break: break-all; color: #1a3a5c;
    }}
    strong {{ color: #1a3a5c; }}
    br {{ display: none; }}
  </style>
</head>
<body>
<div class="wrapper">
{"".join(html_parts)}
</div>
</body>
</html>"""

    html_path = md_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    print(f"Rapport .html : {html_path}")
    return html_path


def _inline(text: str) -> str:
    """Convertit **bold** et `code` en HTML."""
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)
    return text


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Screaming Frog CLI — rapport santé SEO")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"URL à crawler (défaut : {DEFAULT_URL})",
    )
    args = parser.parse_args()

    url      = args.url.rstrip("/")
    date_str = datetime.now().strftime("%d-%m-%y")
    slug     = get_domain_slug(url)

    # Dossier SF pour les CSVs exportés (isolé par domaine + date)
    csv_folder = CRAWL_OUTPUT_BASE / f"{slug}_{date_str}"

    run_crawl(url, csv_folder)
    md_path = generate_md(url, csv_folder, date_str, slug)
    md_to_html(md_path)

    print(f"\nDone. Rapports : output/crawl_reports/crawl_{slug}_{date_str}.md/.html")


if __name__ == "__main__":
    main()
