#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/webperf_recap.py
----------------------
Génère un fichier Markdown de recap interne WebPerf à partir du Google Sheets.
Compare le mois N au mois N-1. Signale les baisses de scores et métriques hors seuil.

Usage:
    python tools/webperf_recap.py            # mois courant vs mois précédent
    python tools/webperf_recap.py 2026-02    # février 2026 vs janvier 2026

Output:
    output/webperf/YYYY-MM/recap_MM-YYYY.md
"""

import sys
import os
import datetime
import unicodedata
import gspread
from google.oauth2.service_account import Credentials


# ── Configuration ───────────────────────────────────────────────────────────────
SPREADSHEET_ID   = "1D7IYLK2GQ77L8o-mXJzFzFqxgM0m7DLH0cxtw8khtn8"
CREDENTIALS_FILE = "tools/credentials/service_account.json"
OUTPUT_BASE      = "output/webperf"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Feuilles GSC Core Web Vitals
GSC_DSK_SHEET     = "URLS Statut DSK"
GSC_MOB_SHEET     = "URLS Statut MOB"
GSC_HEADER_ROW    = 4   # row avec les mois (1-based)
GSC_LENTES_ROW    = 5
GSC_AMELIORER_ROW = 6
GSC_RAPIDE_ROW    = 7

# Pages AB Croisière — métriques complètes
AB_SHEETS = ["HP", "MSC", "COSTA", "SL", "FP", "LP navire"]
AB_SHEET_LABELS = {
    "HP":       "HP — abcroisiere.com",
    "MSC":      "SL MSC",
    "COSTA":    "SL Costa",
    "SL":       "SL Méditerranée",
    "FP":       "FP",
    "LP navire":"LP Navire",
}
AB_SHEET_URLS = {
    "HP":       "https://www.abcroisiere.com/",
    "MSC":      "https://www.abcroisiere.com/fr/croisieres/croisiere-msc-croisieres/compagnie,13/",
    "COSTA":    "https://www.abcroisiere.com/fr/croisieres/croisiere-costa-croisieres/compagnie,7/",
    "SL":       "https://www.abcroisiere.com/fr/croisieres/croisiere-mediterranee/destination,53,0/",
    "FP":       "https://www.abcroisiere.com/croisiere-italie-malte-espagne-1553162.html",
    "LP navire":"https://www.abcroisiere.com/fr/bateau-croisiere/costa-toscana/navire,1420/",
}

# Concurrents — scores uniquement (ordre = lignes dans la feuille HP concurrent)
CONCURRENT_SITES = [
    ("abcroisiere.com",  0),
    ("croisierenet.com", 1),
    ("croisieres.fr",    2),
    ("croisieres.com",   3),
]

# Layout Sheets (1-based)
DSK_HEADER_ROW = 3
DSK_ROWS = {"score": 4, "fcp": 5, "lcp": 6, "cls": 7, "si": 9, "tbt": 11}
MOB_HEADER_ROW = 13
MOB_ROWS = {"score": 14, "fcp": 15, "lcp": 16, "cls": 17, "si": 19, "tbt": 21}
HP_CONC_DSK_HEADER_ROW = 4
HP_CONC_MOB_HEADER_ROW = 10
HP_CONC_DSK_DATA_START = 5   # 1-based, 4 lignes de données
HP_CONC_MOB_DATA_START = 11

# Seuils d'alerte
THRESHOLDS = {
    "score_drop_alert": -10,   # pts → alerte rouge
    "score_drop_warn":   -5,   # pts → avertissement
    "score_rise_notable": +5,  # pts → progression notable
    "cls_max":    0.1,
    "tbt_dsk_max": 300,        # ms
    "tbt_mob_max": 600,        # ms
    "lcp_dsk_max": 2.5,        # s
    "lcp_mob_max": 4.0,        # s
    "fcp_dsk_max": 1.8,        # s
    "fcp_mob_max": 3.0,        # s
}

METRIC_LABELS = {
    "score": "Score",
    "fcp":   "FCP",
    "lcp":   "LCP",
    "cls":   "CLS",
    "si":    "Speed Index",
    "tbt":   "TBT",
}

METRIC_UNITS = {
    "score": "",
    "fcp":   "s",
    "lcp":   "s",
    "cls":   "",
    "si":    "s",
    "tbt":   "ms",
}

MONTH_FR = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin",
            "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTH_FR_LONG = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                 "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

MONTH_NAMES = {
    "janv": 1, "jan": 1, "janvier": 1, "january": 1,
    "fevr": 2, "fev": 2, "fevrier": 2, "february": 2, "feb": 2,
    "mars": 3, "march": 3, "mar": 3,
    "avr": 4, "avril": 4, "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juin": 6, "june": 6, "jun": 6,
    "juil": 7, "juillet": 7, "july": 7, "jul": 7,
    "aout": 8, "august": 8, "aug": 8,
    "sept": 9, "sep": 9, "septembre": 9, "september": 9,
    "oct": 10, "octobre": 10, "october": 10,
    "nov": 11, "novembre": 11, "november": 11,
    "dec": 12, "decembre": 12, "december": 12,
}


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _strip_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def parse_month_key(cell_str):
    """Retourne (year, month) ou None."""
    if not cell_str:
        return None
    clean = _strip_accents(str(cell_str).lower()).replace('.', '').replace(',', '').strip()
    if '-' in clean:
        parts = clean.split('-')
        if len(parts) == 2:
            m_str, y_str = parts[0].strip(), parts[1].strip()
            m_num = MONTH_NAMES.get(m_str)
            try:
                y_raw = int(y_str)
                y_num = 2000 + y_raw if y_raw < 100 else y_raw
                if m_num:
                    return (y_num, m_num)
            except ValueError:
                pass
    parts = clean.split()
    if len(parts) == 2:
        for m_str, y_str in [(parts[0], parts[1]), (parts[1], parts[0])]:
            m_num = MONTH_NAMES.get(m_str)
            try:
                y_num = int(y_str)
                if m_num:
                    return (y_num, m_num)
            except ValueError:
                continue
    return None


def find_col(row_values, year, month):
    """Retourne l'index 0-based de la colonne pour year/month, -1 si non trouvé."""
    for i, cell in enumerate(row_values):
        if parse_month_key(cell) == (year, month):
            return i
    return -1


def safe_float(val):
    if val is None or str(val).strip() in ('', 'None'):
        return None
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return None


def fmt_val(metric, value):
    """Formate une valeur selon la métrique."""
    if value is None:
        return "—"
    unit = METRIC_UNITS.get(metric, "")
    if metric == "score":
        return str(int(round(value)))
    if metric == "tbt":
        return f"{int(value)}{unit}"
    if metric == "cls":
        return str(round(value, 3))
    return f"{value}{unit}"


def score_badge(s):
    """Retourne le score avec emoji couleur."""
    if s is None:
        return "—"
    v = int(round(s))
    if v >= 90:
        return f"🟢 {v}"
    elif v >= 50:
        return f"🟡 {v}"
    else:
        return f"🔴 {v}"


def delta_str(n1, n, is_score=False):
    """Retourne la chaîne de delta avec emoji."""
    if n1 is None or n is None:
        return "—"
    if is_score:
        d = int(round(n - n1))
        if d >= THRESHOLDS["score_rise_notable"]:
            return f"+{d} ✅"
        elif d <= THRESHOLDS["score_drop_alert"]:
            return f"{d} 🔴"
        elif d <= THRESHOLDS["score_drop_warn"]:
            return f"{d} ⚠️"
        elif d > 0:
            return f"+{d}"
        elif d == 0:
            return "="
        else:
            return str(d)
    else:
        d = round(n - n1, 3)
        if d == 0:
            return "="
        # TBT est en ms (entiers) → pas de décimales
        if abs(d) >= 1 and d == int(d):
            return f"{int(d):+d}"
        return f"{d:+.3g}"


def is_metric_alert(metric, value, device):
    """Retourne True si la valeur dépasse le seuil d'alerte."""
    if value is None:
        return False
    t = THRESHOLDS
    if metric == "cls":
        return value > t["cls_max"]
    if metric == "tbt":
        return value > (t["tbt_dsk_max"] if device == "dsk" else t["tbt_mob_max"])
    if metric == "lcp":
        return value > (t["lcp_dsk_max"] if device == "dsk" else t["lcp_mob_max"])
    if metric == "fcp":
        return value > (t["fcp_dsk_max"] if device == "dsk" else t["fcp_mob_max"])
    return False


def threshold_label(metric, device):
    t = THRESHOLDS
    if metric == "cls":
        return f"≤ {t['cls_max']}"
    if metric == "tbt":
        v = t["tbt_dsk_max"] if device == "dsk" else t["tbt_mob_max"]
        return f"≤ {v}ms"
    if metric == "lcp":
        v = t["lcp_dsk_max"] if device == "dsk" else t["lcp_mob_max"]
        return f"≤ {v}s"
    if metric == "fcp":
        v = t["fcp_dsk_max"] if device == "dsk" else t["fcp_mob_max"]
        return f"≤ {v}s"
    return ""


# ── Lecture Sheets ───────────────────────────────────────────────────────────────

def read_gsc_cwv_sheet(ws, year_n, month_n, year_n1, month_n1):
    """
    Lit les données GSC Core Web Vitals (URLS Statut DSK ou MOB).
    Retourne {n: {lentes, ameliorer, rapide}, n1: {lentes, ameliorer, rapide}}
    """
    values = ws.get_all_values()

    def get_row(idx_1based):
        idx = idx_1based - 1
        return values[idx] if idx < len(values) else []

    header = get_row(GSC_HEADER_ROW)
    col_n  = find_col(header, year_n,  month_n)
    col_n1 = find_col(header, year_n1, month_n1)

    def _get(row_1based, col):
        if col < 0:
            return None
        row = get_row(row_1based)
        return safe_float(row[col] if col < len(row) else None)

    return {
        "n": {
            "lentes":    _get(GSC_LENTES_ROW,    col_n),
            "ameliorer": _get(GSC_AMELIORER_ROW, col_n),
            "rapide":    _get(GSC_RAPIDE_ROW,    col_n),
        },
        "n1": {
            "lentes":    _get(GSC_LENTES_ROW,    col_n1),
            "ameliorer": _get(GSC_AMELIORER_ROW, col_n1),
            "rapide":    _get(GSC_RAPIDE_ROW,    col_n1),
        },
        "col_found": {"n": col_n >= 0, "n1": col_n1 >= 0},
    }


def read_ab_sheet(ws, year_n, month_n, year_n1, month_n1):
    """
    Lit les métriques DSK + MOB pour N et N-1.
    Retourne {dsk: {n: {metric: val}, n1: {metric: val}}, mob: {...}}
    """
    values = ws.get_all_values()

    def get_row(idx_1based):
        idx = idx_1based - 1
        return values[idx] if idx < len(values) else []

    dsk_header = get_row(DSK_HEADER_ROW)
    mob_header = get_row(MOB_HEADER_ROW)

    col_n_dsk  = find_col(dsk_header, year_n,  month_n)
    col_n1_dsk = find_col(dsk_header, year_n1, month_n1)
    col_n_mob  = find_col(mob_header, year_n,  month_n)
    col_n1_mob = find_col(mob_header, year_n1, month_n1)

    result = {
        "dsk": {"n": {}, "n1": {}},
        "mob": {"n": {}, "n1": {}},
        "col_found": {
            "dsk_n": col_n_dsk >= 0,
            "dsk_n1": col_n1_dsk >= 0,
            "mob_n": col_n_mob >= 0,
            "mob_n1": col_n1_mob >= 0,
        }
    }

    for metric, row_1based in DSK_ROWS.items():
        row = get_row(row_1based)
        if col_n_dsk >= 0:
            result["dsk"]["n"][metric] = safe_float(row[col_n_dsk] if col_n_dsk < len(row) else None)
        if col_n1_dsk >= 0:
            result["dsk"]["n1"][metric] = safe_float(row[col_n1_dsk] if col_n1_dsk < len(row) else None)

    for metric, row_1based in MOB_ROWS.items():
        row = get_row(row_1based)
        if col_n_mob >= 0:
            result["mob"]["n"][metric] = safe_float(row[col_n_mob] if col_n_mob < len(row) else None)
        if col_n1_mob >= 0:
            result["mob"]["n1"][metric] = safe_float(row[col_n1_mob] if col_n1_mob < len(row) else None)

    return result


def read_concurrent_sheet(ws, year_n, month_n, year_n1, month_n1):
    """
    Lit les scores HP concurrent pour N et N-1.
    Retourne liste de {site, dsk_n, dsk_n1, mob_n, mob_n1}
    """
    values = ws.get_all_values()

    def get_row(idx_1based):
        idx = idx_1based - 1
        return values[idx] if idx < len(values) else []

    dsk_header = get_row(HP_CONC_DSK_HEADER_ROW)
    mob_header = get_row(HP_CONC_MOB_HEADER_ROW)

    col_n_dsk  = find_col(dsk_header, year_n,  month_n)
    col_n1_dsk = find_col(dsk_header, year_n1, month_n1)
    col_n_mob  = find_col(mob_header, year_n,  month_n)
    col_n1_mob = find_col(mob_header, year_n1, month_n1)

    results = []
    for site_name, site_idx in CONCURRENT_SITES:
        dsk_row = get_row(HP_CONC_DSK_DATA_START + site_idx)
        mob_row = get_row(HP_CONC_MOB_DATA_START + site_idx)

        def _get(row, col):
            return safe_float(row[col] if col >= 0 and col < len(row) else None)

        results.append({
            "site":   site_name,
            "dsk_n":  _get(dsk_row, col_n_dsk),
            "dsk_n1": _get(dsk_row, col_n1_dsk),
            "mob_n":  _get(mob_row, col_n_mob),
            "mob_n1": _get(mob_row, col_n1_mob),
        })

    return results


# ── Génération du Markdown ───────────────────────────────────────────────────────

def generate_recap(data_by_sheet, concurrent_data, gsc_dsk, gsc_mob, year_n, month_n, year_n1, month_n1):
    label_n  = f"{MONTH_FR[month_n]} {str(year_n)[2:]}"
    label_n1 = f"{MONTH_FR[month_n1]} {str(year_n1)[2:]}"
    today    = datetime.date.today().strftime("%d/%m/%Y")

    lines = []

    # ── En-tête ─────────────────────────────────────────────────────────────────
    lines += [
        f"# WebPerf Recap — {MONTH_FR_LONG[month_n]} {year_n}",
        "",
        f"> Usage interne · Généré le {today} · Source : Google Sheets PSI",
        f"> Comparaison **{label_n1}** → **{label_n}**",
        "",
        "---",
        "",
    ]

    # ── Section 0 : GSC Core Web Vitals ──────────────────────────────────────────
    lines += [
        "## 0. GSC Core Web Vitals — Vue macro site",
        "",
        f"| | Lentes | À améliorer | Rapides |",
        "|---|:---:|:---:|:---:|",
    ]

    def _cwv_cell(val_n, val_n1=None):
        """Formate une cellule CWV : valeur + delta vs N-1 si dispo."""
        if val_n is None:
            return "—"
        s = str(int(val_n))
        if val_n1 is not None:
            d = int(val_n) - int(val_n1)
            if d > 0:
                s += f" *(+{d})*"
            elif d < 0:
                s += f" *({d})*"
        return s

    def _cwv_row_md(label, data_n, data_n1=None):
        """Génère une ligne MD pour une ligne CWV. data_n1=None → pas de delta (ligne baseline)."""
        if data_n is None:
            return f"| {label} | — | — | — |"
        lentes    = _cwv_cell(data_n.get("lentes"),    data_n1.get("lentes")    if data_n1 else None)
        ameliorer = _cwv_cell(data_n.get("ameliorer"), data_n1.get("ameliorer") if data_n1 else None)
        rapide    = _cwv_cell(data_n.get("rapide"),    data_n1.get("rapide")    if data_n1 else None)
        return f"| {label} | {lentes} | {ameliorer} | {rapide} |"

    dsk_n  = gsc_dsk["n"]  if gsc_dsk else None
    dsk_n1 = gsc_dsk["n1"] if gsc_dsk else None
    mob_n  = gsc_mob["n"]  if gsc_mob else None
    mob_n1 = gsc_mob["n1"] if gsc_mob else None

    lines.append(_cwv_row_md(f"Desktop {label_n1}", dsk_n1))          # baseline, pas de delta
    lines.append(_cwv_row_md(f"Desktop {label_n}",  dsk_n,  dsk_n1))  # N avec delta vs N-1
    lines.append(_cwv_row_md(f"Mobile {label_n1}",  mob_n1))
    lines.append(_cwv_row_md(f"Mobile {label_n}",   mob_n,  mob_n1))
    lines += ["", "---", ""]

    # ── Section 1 : Vue d'ensemble scores ────────────────────────────────────────
    lines += [
        "## 1. Vue d'ensemble — Scores PSI",
        "",
        f"| Page | DSK {label_n1} | DSK {label_n} | Δ DSK | MOB {label_n1} | MOB {label_n} | Δ MOB |",
        "|------|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for sheet_name in AB_SHEETS:
        d = data_by_sheet.get(sheet_name)
        label = AB_SHEET_LABELS[sheet_name]
        if not d:
            lines.append(f"| {label} | — | — | — | — | — | — |")
            continue
        dsk_n1 = d["dsk"]["n1"].get("score")
        dsk_n  = d["dsk"]["n"].get("score")
        mob_n1 = d["mob"]["n1"].get("score")
        mob_n  = d["mob"]["n"].get("score")
        lines.append(
            f"| {label} "
            f"| {score_badge(dsk_n1)} | {score_badge(dsk_n)} | {delta_str(dsk_n1, dsk_n, True)} "
            f"| {score_badge(mob_n1)} | {score_badge(mob_n)} | {delta_str(mob_n1, mob_n, True)} |"
        )

    lines += ["", "---", ""]

    # ── Section 2 : Alertes ──────────────────────────────────────────────────────
    lines += ["## 2. Alertes", ""]

    score_alerts  = []   # drops >= 10pts
    score_warns   = []   # drops 5-9pts
    score_goods   = []   # rises >= 5pts
    metric_alerts = []   # métriques hors seuil (nouvelles uniquement)
    mcp_targets   = []   # pages à investiguer

    for sheet_name in AB_SHEETS:
        d = data_by_sheet.get(sheet_name)
        if not d:
            continue
        label = AB_SHEET_LABELS[sheet_name]
        url   = AB_SHEET_URLS[sheet_name]

        for device in ["dsk", "mob"]:
            dev = "Desktop" if device == "dsk" else "Mobile"
            n1  = d[device]["n1"]
            n   = d[device]["n"]

            # Score
            s_n1 = n1.get("score")
            s_n  = n.get("score")
            if s_n1 is not None and s_n is not None:
                delta = int(round(s_n - s_n1))
                if delta <= THRESHOLDS["score_drop_alert"]:
                    score_alerts.append(f"**{label} {dev}** : {int(s_n1)} → {int(s_n)} ({delta:+d} pts)")
                    mcp_targets.append((label, dev, url, [f"score {delta:+d}pts"]))
                elif delta <= THRESHOLDS["score_drop_warn"]:
                    score_warns.append(f"**{label} {dev}** : {int(s_n1)} → {int(s_n)} ({delta:+d} pts)")
                elif delta >= THRESHOLDS["score_rise_notable"]:
                    score_goods.append(f"**{label} {dev}** : {int(s_n1)} → {int(s_n)} ({delta:+d} pts)")

            # Métriques hors seuil — signaler seulement si c'est nouveau ce mois
            mcp_reasons = []
            for metric in ["cls", "tbt", "lcp", "fcp"]:
                val_n  = n.get(metric)
                val_n1 = n1.get(metric)
                if val_n is None:
                    continue
                now_alert  = is_metric_alert(metric, val_n, device)
                prev_alert = is_metric_alert(metric, val_n1, device) if val_n1 is not None else False
                if now_alert:
                    new_flag = " *(nouveau)*" if not prev_alert else ""
                    prev_str = f" (était {fmt_val(metric, val_n1)})" if val_n1 is not None else ""
                    metric_alerts.append(
                        f"**{label} {dev}** — {METRIC_LABELS[metric]} : "
                        f"`{fmt_val(metric, val_n)}`{prev_str} · seuil {threshold_label(metric, device)}{new_flag}"
                    )
                    if not prev_alert:
                        mcp_reasons.append(f"{METRIC_LABELS[metric]} hors seuil")

            # Enrichir mcp_targets avec les raisons métriques
            if mcp_reasons:
                existing = next((t for t in mcp_targets if t[0] == label and t[1] == dev), None)
                if existing:
                    existing[3].extend(mcp_reasons)
                else:
                    mcp_targets.append((label, dev, url, mcp_reasons))

    if score_alerts:
        lines.append("### 🔴 Baisses significatives (≥ 10 pts)")
        lines += [f"- {a}" for a in score_alerts]
        lines.append("")
    if score_warns:
        lines.append("### ⚠️ Baisses modérées (5–9 pts)")
        lines += [f"- {w}" for w in score_warns]
        lines.append("")
    if metric_alerts:
        lines.append("### 🔴 Métriques hors seuil")
        lines += [f"- {m}" for m in metric_alerts]
        lines.append("")
    if score_goods:
        lines.append("### ✅ Progressions notables (≥ 5 pts)")
        lines += [f"- {g}" for g in score_goods]
        lines.append("")
    if not score_alerts and not score_warns and not metric_alerts:
        lines += ["*Aucune alerte ce mois-ci. ✅*", ""]

    lines += ["---", ""]

    # ── Section 3 : Détail métriques par page ────────────────────────────────────
    lines += ["## 3. Détail métriques — Pages AB Croisière", ""]

    for sheet_name in AB_SHEETS:
        d = data_by_sheet.get(sheet_name)
        if not d:
            continue
        label = AB_SHEET_LABELS[sheet_name]
        lines += [
            f"### {label}",
            "",
            f"| Métrique | Seuil | {label_n1} DSK | {label_n} DSK | Δ DSK | {label_n1} MOB | {label_n} MOB | Δ MOB |",
            "|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]

        for metric in ["score", "fcp", "lcp", "cls", "tbt", "si"]:
            v_dsk_n1 = d["dsk"]["n1"].get(metric)
            v_dsk_n  = d["dsk"]["n"].get(metric)
            v_mob_n1 = d["mob"]["n1"].get(metric)
            v_mob_n  = d["mob"]["n"].get(metric)

            is_score = (metric == "score")
            d_dsk = delta_str(v_dsk_n1, v_dsk_n, is_score)
            d_mob = delta_str(v_mob_n1, v_mob_n, is_score)

            # Emoji alerte sur la valeur N courante
            def annotate(m, v, dev):
                if v is None:
                    return "—"
                base = fmt_val(m, v)
                if is_metric_alert(m, v, dev):
                    return f"{base} 🔴"
                return base

            seuil = threshold_label(metric, "dsk") or "—"

            lines.append(
                f"| {METRIC_LABELS[metric]} | {seuil} "
                f"| {fmt_val(metric, v_dsk_n1)} | {annotate(metric, v_dsk_n, 'dsk')} | {d_dsk} "
                f"| {fmt_val(metric, v_mob_n1)} | {annotate(metric, v_mob_n, 'mob')} | {d_mob} |"
            )

        lines.append("")

    lines += ["---", ""]

    # ── Section 4 : Concurrents ──────────────────────────────────────────────────
    lines += [
        "## 4. Concurrents — Scores HP",
        "",
        f"| Site | DSK {label_n1} | DSK {label_n} | Δ DSK | MOB {label_n1} | MOB {label_n} | Δ MOB |",
        "|------|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for c in concurrent_data:
        site = c["site"]
        ab_flag = " 🏠" if site == "abcroisiere.com" else ""
        lines.append(
            f"| {site}{ab_flag} "
            f"| {score_badge(c['dsk_n1'])} | {score_badge(c['dsk_n'])} | {delta_str(c['dsk_n1'], c['dsk_n'], True)} "
            f"| {score_badge(c['mob_n1'])} | {score_badge(c['mob_n'])} | {delta_str(c['mob_n1'], c['mob_n'], True)} |"
        )

    lines += ["", "---", ""]

    # ── Section 5 : Pages à investiguer ──────────────────────────────────────────
    lines += ["## 5. Pages à investiguer avec MCP Chrome DevTools", ""]

    if mcp_targets:
        lines.append("Dis-moi d'investiguer ces pages et je lance l'audit :")
        lines.append("")
        for label, dev, url, reasons in mcp_targets:
            lines.append(f"- **{label} {dev}** → {', '.join(reasons)}")
            lines.append(f"  `{url}`")
    else:
        lines.append("*Aucune page ne nécessite d'investigation approfondie ce mois-ci. ✅*")

    lines.append("")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        year_month = sys.argv[1]
    else:
        year_month = datetime.datetime.now().strftime("%Y-%m")

    try:
        target_dt = datetime.datetime.strptime(year_month, "%Y-%m")
    except ValueError:
        print(f"Format invalide : '{year_month}'. Utiliser YYYY-MM, ex: 2026-02")
        sys.exit(1)

    year_n  = target_dt.year
    month_n = target_dt.month

    # Mois précédent
    prev_dt  = (target_dt.replace(day=1) - datetime.timedelta(days=1))
    year_n1  = prev_dt.year
    month_n1 = prev_dt.month

    label_n  = f"{MONTH_FR_LONG[month_n]} {year_n}"
    label_n1 = f"{MONTH_FR_LONG[month_n1]} {year_n1}"

    print(f"WebPerf Recap — {label_n} vs {label_n1}")
    print(f"Spreadsheet : {SPREADSHEET_ID}")
    print()

    # Connexion Sheets
    print("Connexion Google Sheets...")
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc    = gspread.authorize(creds)
        sh    = gc.open_by_key(SPREADSHEET_ID)
        print(f"Connecté : '{sh.title}'\n")
    except Exception as e:
        print(f"ERREUR connexion : {e}")
        sys.exit(1)

    # Lecture feuilles AB
    data_by_sheet = {}
    for sheet_name in AB_SHEETS:
        try:
            ws = sh.worksheet(sheet_name)
            data_by_sheet[sheet_name] = read_ab_sheet(ws, year_n, month_n, year_n1, month_n1)
            cf = data_by_sheet[sheet_name]["col_found"]
            status = f"DSK N={'OK' if cf['dsk_n'] else '?'}  DSK N-1={'OK' if cf['dsk_n1'] else '?'}  MOB N={'OK' if cf['mob_n'] else '?'}  MOB N-1={'OK' if cf['mob_n1'] else '?'}"
            print(f"  {sheet_name:<12} {status}")
        except Exception as e:
            print(f"  {sheet_name:<12} ERREUR : {e}")
            data_by_sheet[sheet_name] = None

    # Lecture concurrents
    try:
        ws_conc = sh.worksheet("HP concurrent")
        concurrent_data = read_concurrent_sheet(ws_conc, year_n, month_n, year_n1, month_n1)
        print(f"  HP concurrent OK")
    except Exception as e:
        print(f"  HP concurrent ERREUR : {e}")
        concurrent_data = []

    # Lecture GSC Core Web Vitals
    gsc_dsk, gsc_mob = None, None
    for sheet_name, var_name in [(GSC_DSK_SHEET, "dsk"), (GSC_MOB_SHEET, "mob")]:
        try:
            ws_gsc = sh.worksheet(sheet_name)
            data   = read_gsc_cwv_sheet(ws_gsc, year_n, month_n, year_n1, month_n1)
            cf     = data["col_found"]
            status = f"N={'OK' if cf['n'] else '?'}  N-1={'OK' if cf['n1'] else '?'}"
            print(f"  {sheet_name:<22} {status}")
            if var_name == "dsk":
                gsc_dsk = data
            else:
                gsc_mob = data
        except Exception as e:
            print(f"  {sheet_name:<22} ERREUR : {e}")

    print()

    # Génération du markdown
    md = generate_recap(data_by_sheet, concurrent_data, gsc_dsk, gsc_mob, year_n, month_n, year_n1, month_n1)

    # Écriture — un dossier par mois : output/webperf/YYYY-MM/
    month_dir = os.path.join(OUTPUT_BASE, target_dt.strftime("%Y-%m"))
    os.makedirs(month_dir, exist_ok=True)
    out_path = os.path.join(month_dir, f"recap_{target_dt.strftime('%m-%Y')}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Recap généré : {out_path}")
    print()

    # Résumé terminal — alertes uniquement
    in_alerts = False
    alert_lines = []
    for line in md.split("\n"):
        if line.startswith("## 2."):
            in_alerts = True
        elif line.startswith("## 3."):
            break
        elif in_alerts and line.strip():
            alert_lines.append(line)

    if alert_lines:
        print("=" * 60)
        print("ALERTES & AVERTISSEMENTS")
        print("=" * 60)
        for l in alert_lines:
            print(l.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
