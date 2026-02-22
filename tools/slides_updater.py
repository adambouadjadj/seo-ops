#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/slides_updater.py
-----------------------
Met à jour les tableaux de données dans Google Slides à partir du Google Sheets.

Usage:
    python tools/slides_updater.py
"""

import unicodedata
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ── Configuration ──────────────────────────────────────────────────────────────
CREDENTIALS_FILE = "tools/credentials/service_account.json"
SPREADSHEET_ID   = "1D7IYLK2GQ77L8o-mXJzFzFqxgM0m7DLH0cxtw8khtn8"
PRESENTATION_ID  = "1O5uFDwyMXchEi4LiaRBaF6Tie9XpKZ_1v7sefQObZp4"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]

# Mapping slide (1-based) → (feuille Sheets, bloc DSK/MOB)
SLIDE_DATA_MAP = {
    13: ("HP",                "DSK"),
    15: ("HP",                "MOB"),
    22: ("HP croisierenet",   "DSK"),
    24: ("HP croisierenet",   "MOB"),
    26: ("HP croisieres.fr",  "DSK"),
    28: ("HP croisieres.fr",  "MOB"),
    30: ("HP croisieres.com", "DSK"),
    32: ("HP croisieres.com", "MOB"),
    39: ("MSC",               "DSK"),
    41: ("MSC",               "MOB"),
    43: ("COSTA",             "DSK"),
    45: ("COSTA",             "MOB"),
    48: ("SL",                "DSK"),
    50: ("SL",                "MOB"),
    53: ("FP",                "DSK"),
    55: ("FP",                "MOB"),
    58: ("LP navire",         "DSK"),
    60: ("LP navire",         "MOB"),
}

HP_CONCURRENT_SLIDES = {18: "DSK", 20: "MOB"}

# Mapping ligne table Slides (0-based) → métrique
TABLE_ROW_TO_METRIC = {
    1: "score",
    2: "fcp",
    3: "lcp",
    4: "cls",
    # row 5 = FID (déprécié) → skip
    6: "si",
    # row 7 = TTI (déprécié) → skip
    8: "tbt",
}

# Layout Sheets (0-based dans all_values)
DSK_HEADER_ROW  = 3   # row 3 Sheets (1-based) → index 2 (0-based)
DSK_METRIC_ROWS = {
    "score": 3,   # Sheets row 4
    "fcp":   4,
    "lcp":   5,
    "cls":   6,
    "si":    8,   # Sheets row 9
    "tbt":   10,  # Sheets row 11
}

MOB_HEADER_ROW  = 13
MOB_METRIC_ROWS = {
    "score": 13,  # Sheets row 14
    "fcp":   14,
    "lcp":   15,
    "cls":   16,
    "si":    18,  # Sheets row 19
    "tbt":   20,  # Sheets row 21
}

HP_CONC_DSK_HEADER_IDX = 3
HP_CONC_DSK_DATA_START  = 4
HP_CONC_MOB_HEADER_IDX  = 9
HP_CONC_MOB_DATA_START  = 10


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

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

def parse_month_key(cell_str):
    if not cell_str:
        return None
    clean = _strip_accents(cell_str.lower()).replace('.', '').replace(',', '').strip()
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

def format_value(val):
    if val is None or val == '':
        return ''
    s = str(val).strip()
    if not s:
        return ''
    try:
        f = float(s.replace(',', '.'))
        if f == int(f) and '.' not in s and ',' not in s:
            return str(int(f))
        return str(f).replace('.', ',')
    except (ValueError, OverflowError):
        return s

def get_cell_text(cell):
    text = ''
    for el in cell.get('text', {}).get('textElements', []):
        if 'textRun' in el:
            text += el['textRun'].get('content', '')
    return text.strip()

def make_cell_requests(table_id, row_idx, col_idx, new_text, current_text=''):
    """Requêtes pour vider puis réécrire une cellule de tableau Slides."""
    cell_loc = {"rowIndex": row_idx, "columnIndex": col_idx}
    reqs = []
    if current_text:  # deleteText échoue si la cellule est déjà vide
        reqs.append({
            "deleteText": {
                "objectId": table_id,
                "cellLocation": cell_loc,
                "textRange": {"type": "ALL"}
            }
        })
    if new_text:
        reqs.append({
            "insertText": {
                "objectId": table_id,
                "cellLocation": cell_loc,
                "insertionIndex": 0,
                "text": new_text
            }
        })
    return reqs


# ── Lecture Sheets ─────────────────────────────────────────────────────────────

def read_sheet_data(ws):
    values = ws.get_all_values()

    def get_row(idx):
        return values[idx] if idx < len(values) else []

    def parse_months(row):
        return [parse_month_key(c) for c in row]

    dsk_months = parse_months(get_row(DSK_HEADER_ROW - 1))
    dsk_data = {"months": dsk_months}
    for metric, row_idx in DSK_METRIC_ROWS.items():
        dsk_data[metric] = get_row(row_idx)

    mob_months = parse_months(get_row(MOB_HEADER_ROW - 1))
    mob_data = {"months": mob_months}
    for metric, row_idx in MOB_METRIC_ROWS.items():
        mob_data[metric] = get_row(row_idx)

    return {"DSK": dsk_data, "MOB": mob_data}

def read_concurrent_data(ws):
    values = ws.get_all_values()

    def get_row(idx):
        return values[idx] if idx < len(values) else []

    def parse_months(row):
        return [parse_month_key(c) for c in row]

    return {
        "DSK": {
            "months": parse_months(get_row(HP_CONC_DSK_HEADER_IDX)),
            "rows": [get_row(HP_CONC_DSK_DATA_START + i) for i in range(4)]
        },
        "MOB": {
            "months": parse_months(get_row(HP_CONC_MOB_HEADER_IDX)),
            "rows": [get_row(HP_CONC_MOB_DATA_START + i) for i in range(4)]
        }
    }


# ── Construction des requêtes ──────────────────────────────────────────────────

def build_metrics_requests(table_id, table_rows, sheet_data, block):
    """Requêtes pour un tableau métriques 9r x 16c."""
    data = sheet_data[block]
    sheet_months = data["months"]
    requests = []

    # Lire les mois depuis la ligne de header du tableau Slides (row 0)
    header_cells = table_rows[0].get('tableCells', [])
    slide_month_cols = {}
    for col_idx, cell in enumerate(header_cells):
        mk = parse_month_key(get_cell_text(cell))
        if mk:
            slide_month_cols[col_idx] = mk

    for col_idx, slide_month in slide_month_cols.items():
        # Colonne correspondante dans Sheets
        sheet_col = next(
            (i for i, m in enumerate(sheet_months) if m == slide_month),
            None
        )

        for row_idx, metric_key in TABLE_ROW_TO_METRIC.items():
            if row_idx >= len(table_rows):
                continue
            if sheet_col is None:
                val = ''
            else:
                row_data = data.get(metric_key, [])
                val = row_data[sheet_col] if sheet_col < len(row_data) else ''

            cells = table_rows[row_idx].get('tableCells', [])
            cur = get_cell_text(cells[col_idx]) if col_idx < len(cells) else ''
            requests.extend(make_cell_requests(table_id, row_idx, col_idx, format_value(val), cur))

    return requests

def build_concurrent_requests(table_id, table_rows, conc_data, block):
    """Requêtes pour le tableau HP concurrent 5r x 15c."""
    data = conc_data[block]
    sheet_months = data["months"]
    site_rows = data["rows"]
    requests = []

    header_cells = table_rows[0].get('tableCells', [])
    slide_month_cols = {}
    for col_idx, cell in enumerate(header_cells):
        mk = parse_month_key(get_cell_text(cell))
        if mk:
            slide_month_cols[col_idx] = mk

    for col_idx, slide_month in slide_month_cols.items():
        sheet_col = next(
            (i for i, m in enumerate(sheet_months) if m == slide_month),
            None
        )

        for site_idx in range(4):
            row_idx = site_idx + 1
            if row_idx >= len(table_rows):
                continue
            if sheet_col is None or site_idx >= len(site_rows):
                val = ''
            else:
                row_data = site_rows[site_idx]
                val = row_data[sheet_col] if sheet_col < len(row_data) else ''

            cells = table_rows[row_idx].get('tableCells', [])
            cur = get_cell_text(cells[col_idx]) if col_idx < len(cells) else ''
            requests.extend(make_cell_requests(table_id, row_idx, col_idx, format_value(val), cur))

    return requests


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Slides Updater — WebPerf AB")
    print(f"Spreadsheet : {SPREADSHEET_ID}")
    print(f"Presentation: {PRESENTATION_ID}")
    print()

    # Connexion
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    slides_service = build('slides', 'v1', credentials=creds)

    # Lecture Sheets
    print("Connexion Google Sheets...")
    sh = gc.open_by_key(SPREADSHEET_ID)
    print(f"Connecte : '{sh.title}'\n")

    sheet_names = set(v[0] for v in SLIDE_DATA_MAP.values())
    sheets_data = {}
    for name in sorted(sheet_names):
        try:
            ws = sh.worksheet(name)
            sheets_data[name] = read_sheet_data(ws)
            print(f"  {name} — OK")
        except Exception as e:
            print(f"  {name} — ERREUR : {e}")

    try:
        conc_data = read_concurrent_data(sh.worksheet("HP concurrent"))
        print(f"  HP concurrent — OK")
    except Exception as e:
        print(f"  HP concurrent — ERREUR : {e}")
        conc_data = None

    # Lecture Slides
    print("\nLecture de la présentation...")
    pres = slides_service.presentations().get(presentationId=PRESENTATION_ID).execute()
    slides = pres.get('slides', [])
    print(f"  {len(slides)} slides\n")

    # Construction des requêtes
    all_requests = []
    filled = 0

    for slide_num, (sheet_name, block) in sorted(SLIDE_DATA_MAP.items()):
        slide_idx = slide_num - 1
        if slide_idx >= len(slides):
            print(f"  Slide {slide_num:2d} — hors limite")
            continue

        slide = slides[slide_idx]
        tables = [e for e in slide.get('pageElements', []) if 'table' in e]
        metric_table = next(
            (t for t in tables if len(t['table'].get('tableRows', [])) == 9),
            None
        )

        if not metric_table:
            print(f"  Slide {slide_num:2d} — table introuvable")
            continue
        if sheet_name not in sheets_data:
            print(f"  Slide {slide_num:2d} — données manquantes '{sheet_name}'")
            continue

        table_id = metric_table['objectId']
        table_rows = metric_table['table']['tableRows']
        reqs = build_metrics_requests(table_id, table_rows, sheets_data[sheet_name], block)
        all_requests.extend(reqs)
        print(f"  Slide {slide_num:2d} — {sheet_name} {block} ({len(reqs)} req)")
        filled += 1

    # HP concurrent
    if conc_data:
        for slide_num, block in sorted(HP_CONCURRENT_SLIDES.items()):
            slide_idx = slide_num - 1
            if slide_idx >= len(slides):
                continue
            slide = slides[slide_idx]
            tables = [e for e in slide.get('pageElements', []) if 'table' in e]
            conc_table = next(
                (t for t in tables if len(t['table'].get('tableRows', [])) == 5),
                None
            )
            if not conc_table:
                print(f"  Slide {slide_num:2d} — table HP concurrent introuvable")
                continue

            table_id = conc_table['objectId']
            table_rows = conc_table['table']['tableRows']
            reqs = build_concurrent_requests(table_id, table_rows, conc_data, block)
            all_requests.extend(reqs)
            print(f"  Slide {slide_num:2d} — HP concurrent {block} ({len(reqs)} req)")
            filled += 1

    print(f"\nTotal requêtes : {len(all_requests)}")

    if not all_requests:
        print("Rien à envoyer.")
        return

    # Envoi en batches de 500 (limite API)
    BATCH_SIZE = 500
    batches = [all_requests[i:i+BATCH_SIZE] for i in range(0, len(all_requests), BATCH_SIZE)]
    print(f"Envoi en {len(batches)} batch(es)...")

    for i, batch in enumerate(batches, 1):
        slides_service.presentations().batchUpdate(
            presentationId=PRESENTATION_ID,
            body={"requests": batch}
        ).execute()
        print(f"  Batch {i}/{len(batches)} OK ({len(batch)} requêtes)")

    print(f"\nTERMINE — {filled} tableaux mis à jour dans Google Slides")


if __name__ == "__main__":
    main()
