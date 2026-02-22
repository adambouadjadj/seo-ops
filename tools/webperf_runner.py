#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/webperf_runner.py
-----------------------
Appelle l'API PageSpeed Insights (DSK + MOB) pour les 9 URLs AB Croisiere
et ecrit les resultats directement dans le Google Sheets de suivi WebPerf.

Usage:
    python tools/webperf_runner.py [YYYY-MM]
    python tools/webperf_runner.py 2026-02
    python tools/webperf_runner.py          # = mois courant
"""

import sys
import os
import time
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials


def _load_env(path="tools/.env"):
    """Charge les variables depuis tools/.env sans dépendance externe."""
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


_ENV = _load_env()

# ── Configuration ──────────────────────────────────────────────────────────────
SPREADSHEET_ID   = "1D7IYLK2GQ77L8o-mXJzFzFqxgM0m7DLH0cxtw8khtn8"
CREDENTIALS_FILE = "tools/credentials/service_account.json"
PSI_ENDPOINT     = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_API_KEY      = _ENV.get("PSI_API_KEY", "")  # défini dans tools/.env

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Feuilles a traiter : nom exact de la feuille Google Sheets → URL a tester
SHEETS_CONFIG = {
    "HP":                "https://www.abcroisiere.com/",
    "HP croisierenet":   "https://www.croisierenet.com/",
    "HP croisieres.fr":  "https://www.croisieres.fr/",
    "HP croisieres.com": "https://www.croisieres.com/",
    "MSC":               "https://www.abcroisiere.com/fr/croisieres/croisiere-msc-croisieres/compagnie,13/",
    "COSTA":             "https://www.abcroisiere.com/fr/croisieres/croisiere-costa-croisieres/compagnie,7/",
    "SL":                "https://www.abcroisiere.com/fr/croisieres/croisiere-mediterranee/destination,53,0/",
    "FP":                "https://www.abcroisiere.com/croisiere-italie-malte-espagne-1553162.html",
    "LP navire":         "https://www.abcroisiere.com/fr/bateau-croisiere/costa-toscana/navire,1420/",
}

# HP concurrent : score global uniquement, structure differente
# URL → (row_DSK, row_MOB)  — header DSK=row4, header MOB=row10
HP_CONCURRENT_ROWS = {
    "https://www.abcroisiere.com/":  (5, 11),
    "https://www.croisierenet.com/": (6, 12),
    "https://www.croisieres.fr/":    (7, 13),
    "https://www.croisieres.com/":   (8, 14),
}
HP_CONCURRENT_DSK_HEADER = 4
HP_CONCURRENT_MOB_HEADER = 10

# Layout des lignes (1-indexe, identique dans chaque feuille)
DSK_HEADER_ROW = 3   # ligne contenant les dates (mois)
DSK_ROWS = {         # metrique → numero de ligne
    "score": 4,
    "fcp":   5,
    "lcp":   6,
    "cls":   7,
    # ligne 8 = FID (deprecie → skip)
    "si":    9,
    # ligne 10 = TTI (deprecie → skip)
    "tbt":  11,
}

MOB_HEADER_ROW = 13
MOB_ROWS = {
    "score": 14,
    "fcp":   15,
    "lcp":   16,
    "cls":   17,
    # ligne 18 = FID (deprecie → skip)
    "si":    19,
    # ligne 20 = TTI (deprecie → skip)
    "tbt":  21,
}

# Noms de mois francais et anglais pour le parsing des headers
MONTH_NAMES = {
    "janv": 1, "jan": 1, "janvier": 1, "january": 1,
    "fevr": 2, "fev": 2, "fevrier": 2, "february": 2, "feb": 2,
    "fevr": 2, "fevr": 2,
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


# ── Detection de la colonne cible ──────────────────────────────────────────────

def _serial_to_date(serial):
    """Convertit un serial date Google Sheets (jours depuis 30/12/1899) en date."""
    epoch = datetime.date(1899, 12, 30)
    return epoch + datetime.timedelta(days=int(serial))


import unicodedata

def _strip_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def cell_matches_month(cell_value, year, month):
    """Retourne True si cell_value represente le mois/annee cible."""
    s = str(cell_value).strip()
    if not s or s in ("None", ""):
        return False

    # Cas 1 : serial date numerique (valeur brute Google Sheets)
    try:
        serial = float(s.replace(",", "."))
        if 1000 < serial < 200000:  # plage raisonnable pour des dates
            d = _serial_to_date(int(serial))
            return d.year == year and d.month == month
    except ValueError:
        pass

    # Cas 2 : formats ISO ou numeriques
    for fmt in ["%Y-%m", "%Y-%m-%d", "%m/%Y", "%m/%y"]:
        try:
            d = datetime.datetime.strptime(s[:10], fmt)
            return d.year == year and d.month == month
        except ValueError:
            pass

    # Normaliser : retirer accents et mettre en minuscules
    clean = _strip_accents(s.lower()).strip()

    # Cas 3 : format Google Sheets "fevr.-26", "janv.-22", "aout-26", "mars-26"
    # Pattern : [mois][-][annee 2 chiffres]
    clean_nodot = clean.replace(".", "").replace(",", "")
    if "-" in clean_nodot:
        parts_dash = clean_nodot.split("-")
        if len(parts_dash) == 2:
            m_str, y_str = parts_dash[0].strip(), parts_dash[1].strip()
            m_num = MONTH_NAMES.get(m_str)
            try:
                y_raw = int(y_str)
                y_num = 2000 + y_raw if y_raw < 100 else y_raw
                if m_num and y_num == year and m_num == month:
                    return True
            except ValueError:
                pass

    # Cas 4 : "janv. 2026", "January 2026", "Jan 2026" (mois + espace + annee)
    parts = clean_nodot.split()
    if len(parts) == 2:
        for m_str, y_str in [(parts[0], parts[1]), (parts[1], parts[0])]:
            m_num = MONTH_NAMES.get(m_str)
            try:
                y_num = int(y_str)
                if m_num and y_num == year and m_num == month:
                    return True
            except ValueError:
                continue

    return False


def find_target_column(row_values, year, month):
    """
    Parcourt row_values et retourne l'index 1-base de la colonne correspondant
    a year/month. Retourne -1 si non trouve.
    """
    for i, cell in enumerate(row_values):
        if cell_matches_month(cell, year, month):
            return i + 1  # gspread est 1-indexe
    return -1


# ── Appel PSI ──────────────────────────────────────────────────────────────────

def call_psi(url, strategy, retries=3):
    """
    Appelle l'API PSI pour une URL et une strategie (DESKTOP ou MOBILE).
    Retourne un dict de metriques ou None en cas d'echec.
    """
    params = {"url": url, "strategy": strategy, "category": "PERFORMANCE"}
    if PSI_API_KEY:
        params["key"] = PSI_API_KEY

    for attempt in range(retries):
        try:
            resp = requests.get(PSI_ENDPOINT, params=params, timeout=60)
            if resp.status_code == 429:
                # Quota epuise → pas de retry, ca ne servira a rien
                print(f"    429 Quota epuise — verifier la cle API ou attendre demain")
                return None
            resp.raise_for_status()
            data = resp.json()

            lr     = data.get("lighthouseResult", {})
            audits = lr.get("audits", {})
            cats   = lr.get("categories", {})

            raw_score = cats.get("performance", {}).get("score")

            def ms_to_s(key):
                v = audits.get(key, {}).get("numericValue")
                return round(v / 1000, 2) if v is not None else None

            def raw_val(key, decimals=3):
                v = audits.get(key, {}).get("numericValue")
                return round(v, decimals) if v is not None else None

            return {
                "score": round(raw_score * 100) if raw_score is not None else None,
                "fcp":   ms_to_s("first-contentful-paint"),
                "lcp":   ms_to_s("largest-contentful-paint"),
                "cls":   raw_val("cumulative-layout-shift", decimals=3),
                "si":    ms_to_s("speed-index"),
                "tbt":   raw_val("total-blocking-time", decimals=0),
            }

        except requests.exceptions.RequestException as e:
            print(f"    Erreur tentative {attempt + 1}/{retries} : {e}")
            if attempt < retries - 1:
                time.sleep(3)

    return None


# ── Ecriture dans le Sheets ────────────────────────────────────────────────────

def write_metrics(ws, col, metrics, row_map):
    """
    Ecrit les metriques dans la feuille via batch_update.
    col et les valeurs de row_map sont 1-indexes.
    """
    updates = []
    for key, row in row_map.items():
        value = metrics.get(key)
        if value is not None:
            cell_ref = gspread.utils.rowcol_to_a1(row, col)
            updates.append({"range": cell_ref, "values": [[value]]})

    if updates:
        ws.batch_update(updates)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Argument : mois cible au format YYYY-MM
    if len(sys.argv) > 1:
        year_month = sys.argv[1]
    else:
        year_month = datetime.datetime.now().strftime("%Y-%m")

    try:
        target_dt = datetime.datetime.strptime(year_month, "%Y-%m")
    except ValueError:
        print(f"Format invalide : '{year_month}'. Utiliser YYYY-MM, ex: 2026-02")
        sys.exit(1)

    target_year  = target_dt.year
    target_month = target_dt.month

    print(f"WebPerf runner — cible : {target_dt.strftime('%B %Y')}")
    print(f"Spreadsheet    : {SPREADSHEET_ID}")
    print()

    # ── Connexion Google Sheets ───────────────────────────────────────────────
    print("Connexion Google Sheets...")
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc    = gspread.authorize(creds)
        sh    = gc.open_by_key(SPREADSHEET_ID)
        print(f"Connecte : '{sh.title}'\n")
    except Exception as e:
        print(f"ERREUR connexion : {e}")
        sys.exit(1)

    # ── Traitement de chaque feuille ──────────────────────────────────────────
    summary = {}

    for sheet_name, url in SHEETS_CONFIG.items():
        print(f"{'=' * 60}")
        print(f"[{sheet_name}]")
        print(f"  URL : {url}")

        # Recuperer la feuille
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  ERREUR : feuille '{sheet_name}' introuvable — skip\n")
            summary[sheet_name] = {"dsk": None, "mob": None, "error": "feuille introuvable"}
            continue

        # Trouver la colonne du mois cible
        dsk_header = ws.row_values(DSK_HEADER_ROW)
        col = find_target_column(dsk_header, target_year, target_month)

        if col == -1:
            readable = [v for v in dsk_header if v and v not in ("Reco", "DSK", "MOB")]
            print(f"  ERREUR : colonne '{year_month}' non trouvee dans le header")
            print(f"  Colonnes disponibles : {readable[:8]}")
            print()
            summary[sheet_name] = {"dsk": None, "mob": None, "error": "colonne introuvable"}
            continue

        col_letter = gspread.utils.rowcol_to_a1(1, col).rstrip("1")
        print(f"  Colonne cible : {col_letter} (col {col})")

        # PSI Desktop
        print(f"  PSI Desktop...")
        time.sleep(1.5)
        dsk = call_psi(url, "DESKTOP")
        if dsk:
            print(f"    Score={dsk['score']}  FCP={dsk['fcp']}s  LCP={dsk['lcp']}s  "
                  f"CLS={dsk['cls']}  SI={dsk['si']}s  TBT={dsk['tbt']}ms")
            write_metrics(ws, col, dsk, DSK_ROWS)
        else:
            print(f"    ECHEC PSI Desktop")

        # PSI Mobile
        print(f"  PSI Mobile...")
        time.sleep(1.5)
        mob = call_psi(url, "MOBILE")
        if mob:
            print(f"    Score={mob['score']}  FCP={mob['fcp']}s  LCP={mob['lcp']}s  "
                  f"CLS={mob['cls']}  SI={mob['si']}s  TBT={mob['tbt']}ms")
            write_metrics(ws, col, mob, MOB_ROWS)
        else:
            print(f"    ECHEC PSI Mobile")

        summary[sheet_name] = {"dsk": dsk, "mob": mob}
        print()

    # ── HP concurrent (scores uniquement, reutilise les resultats du loop) ─────
    print(f"{'=' * 60}")
    print("[HP concurrent]  (scores reutilises — pas de nouveaux appels PSI)")
    try:
        ws_conc = sh.worksheet("HP concurrent")
        dsk_header_conc = ws_conc.row_values(HP_CONCURRENT_DSK_HEADER)
        col_conc = find_target_column(dsk_header_conc, target_year, target_month)

        if col_conc == -1:
            print(f"  ERREUR : colonne '{year_month}' non trouvee dans HP concurrent")
        else:
            col_letter = gspread.utils.rowcol_to_a1(1, col_conc).rstrip("1")
            print(f"  Colonne cible : {col_letter} (col {col_conc})")
            updates = []
            # Mapping sheet_name → URL pour retrouver les resultats
            sheet_url_map = {v: k for k, v in SHEETS_CONFIG.items()}
            for url, (dsk_row, mob_row) in HP_CONCURRENT_ROWS.items():
                sheet_name = sheet_url_map.get(url, "")
                res = summary.get(sheet_name, {})
                dsk_score = res.get("dsk", {}).get("score") if res.get("dsk") else None
                mob_score = res.get("mob", {}).get("score") if res.get("mob") else None
                if dsk_score is not None:
                    updates.append({"range": gspread.utils.rowcol_to_a1(dsk_row, col_conc), "values": [[dsk_score]]})
                if mob_score is not None:
                    updates.append({"range": gspread.utils.rowcol_to_a1(mob_row, col_conc), "values": [[mob_score]]})
                print(f"  {url:<45} DSK={dsk_score}  MOB={mob_score}")
            if updates:
                ws_conc.batch_update(updates)
                print(f"  {len(updates)} cellules ecrites.")
    except gspread.exceptions.WorksheetNotFound:
        print("  ERREUR : feuille 'HP concurrent' introuvable")
    print()

    # ── Recap final ───────────────────────────────────────────────────────────
    print("=" * 60)
    ok_count = sum(1 for v in summary.values() if v.get("dsk") and v.get("mob"))
    print(f"TERMINE — {ok_count}/{len(SHEETS_CONFIG)} feuilles OK\n")
    for name, r in summary.items():
        err = r.get("error", "")
        if err:
            status = f"ERREUR ({err})"
        else:
            dsk_s = f"DSK={r['dsk']['score']}" if r.get("dsk") else "DSK=ECHEC"
            mob_s = f"MOB={r['mob']['score']}" if r.get("mob") else "MOB=ECHEC"
            status = f"{dsk_s}  {mob_s}"
        print(f"  {name:<20} {status}")


if __name__ == "__main__":
    main()
