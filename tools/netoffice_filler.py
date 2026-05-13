"""
NetOffice Timesheet Filler
Remplit automatiquement les semaines manquantes sur NetOffice.

Usage:
    python tools/netoffice_filler.py                    # backfill Dec 8 -> fin Fév
    python tools/netoffice_filler.py --week 2025-12-08  # une seule semaine (lundi)
    python tools/netoffice_filler.py --from 2026-01-05 --to 2026-01-30
"""

import os
import sys
import time
import argparse

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from datetime import date, timedelta
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ──────────────────────────────────────────────────────────────────

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

NETOFFICE_URL  = os.getenv("NETOFFICE_URL",      "https://netoffice.in.karavel.com")
NETOFFICE_USER = os.getenv("NETOFFICE_USER",     "abouadjadj")
NETOFFICE_PASS = os.getenv("NETOFFICE_PASSWORD", "")
OWNER_ID       = "784"

# Anchor vérifié via inspection : dimanche 8 mars 2026 → form montre lun 9 - ven 13 mars
ANCHOR_MONDAY = date(2026, 3, 9)
ANCHOR_SDATE  = 1772971200  # timestamp du dimanche 8 mars 2026

# ── Template semaine AB-SEO ──────────────────────────────────────────────────
# Heures par tâche : [Lun, Mar, Mer, Jeu, Ven]
AB_SEO_TEMPLATE = [
    ("AB - SEO", "AB SEO - Maintenance évolutive (i)", [0, 2, 2, 2, 0]),
    ("AB - SEO", "AB SEO - Crawl et Audit (i)",        [2, 0, 2, 0, 2]),
    ("AB - SEO", "AB SEO - Netlinking (i)",            [2, 2, 0, 2, 2]),
    ("AB - SEO", "AB SEO - Optimisation de contenu (i)", [2, 2, 0, 2, 2]),
    ("AB - SEO", "AB SEO - Rédaction de contenu (i)",  [2, 2, 0, 2, 0]),
    ("AB - SEO", "AB SEO - Reporting (i)",             [0, 0, 4, 0, 0]),
]

# Congé Payé : 8h par jour (Lun-Ven)
# Note: le suffixe (i) sera vérifié au premier lancement congés
CONGE_TEMPLATE = [
    ("ABSENCE - Jours Fériés ou Congés", "Congé Payé", [8, 8, 8, 8, 6]),
]

# ── Semaines en congés (par lundi) ───────────────────────────────────────────
CONGE_MONDAYS = {
    date(2025, 12, 22),
    date(2025, 12, 29),
    date(2026, 1,  5),
}

# ── Bornes du backfill ────────────────────────────────────────────────────────
BACKFILL_FIRST_MONDAY = date(2025, 12, 8)
BACKFILL_LAST_MONDAY  = date(2026, 2, 23)


# ── Helpers ──────────────────────────────────────────────────────────────────

def monday_of(d: date) -> date:
    # Dimanche (weekday=6) : avancer au lundi suivant (NetOffice label = dimanche, travail = lun-ven)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d - timedelta(days=d.weekday())


def sdate_for(monday: date) -> int:
    """Timestamp sdate (dimanche avant le lundi) pour une semaine donnée."""
    delta_weeks = (ANCHOR_MONDAY - monday).days // 7
    return ANCHOR_SDATE - delta_weeks * 604800


def get_mondays(start: date, end: date):
    mondays = []
    d = monday_of(start)
    while d <= end:
        mondays.append(d)
        d += timedelta(weeks=1)
    return mondays


# ── Playwright ───────────────────────────────────────────────────────────────

def login(page, base_url, username, password):
    print(f"  >> Connexion ({username})...")
    page.goto(f"{base_url}/general/login.php")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="loginForm"]', username)
    page.fill('input[name="passwordForm"]', password)
    page.click('input[name="loginSubmit"]')
    page.wait_for_load_state("networkidle")
    if "login" in page.url.lower():
        raise RuntimeError("Echec login -- verifiez identifiants dans tools/.env")
    print("  OK Connecte")


def is_week_already_filled(page) -> bool:
    """Retourne True si la section Log Time contient déjà des entrées."""
    # "Pas d'enregistrements" = vide
    empty = page.locator("text=Pas d'enregistrements")
    return empty.count() == 0


def fill_week(page, base_url, monday, template):
    sdate    = sdate_for(monday)
    month_ts = monday.strftime("%Y%m")

    # 1) Aller sur la page timesheet de la semaine
    ts_url = (
        f"{base_url}/timesheet/viewtimesheet.php"
        f"?typeTimesheet=edit&owner={OWNER_ID}&monthTS={month_ts}&sdate={sdate}"
    )
    page.goto(ts_url)
    page.wait_for_load_state("networkidle")

    # 2) Vérifier si déjà remplie
    if is_week_already_filled(page):
        print(f"  /!\\ Semaine {monday} deja remplie -- skip")
        return False

    # 3) Cliquer sur l'icone "Add Work Hours" (img JS, pas un href classique)
    add_btn = page.locator('img[alt="Add Work Hours"]').first
    if add_btn.count() == 0:
        raise RuntimeError(f"Icone Add Work Hours introuvable sur {ts_url}")
    add_btn.click()
    page.wait_for_load_state("networkidle")
    print(f"  >> Formulaire : {page.url}")

    # 4) Remplir une tache par ligne, soumettre apres chaque
    # Apres chaque Envoyer : page recharge avec lignes precedentes figees + 1 nouvelle ligne vide en bas
    # => la nouvelle ligne vide est toujours a l'index idx (0, 1, 2...)
    for idx, (project, task, hours) in enumerate(template):
        print(f"     Tache {idx+1}/{len(template)} : {task} -> {hours}")

        # Attendre que la ligne vide (index idx) soit disponible
        page.wait_for_selector(f'select[name="prj[{idx}]"]', timeout=10000)

        # Selectionner le projet
        page.select_option(f'select[name="prj[{idx}]"]', label=project)

        # Attendre que les options de taches se chargent (AJAX)
        page.wait_for_function(
            f"document.querySelector('select[name=\"tas[{idx}]\"]').options.length > 1",
            timeout=8000
        )

        # Selectionner la tache
        page.select_option(f'select[name="tas[{idx}]"]', label=task)
        time.sleep(0.2)

        # Recuperer les noms des inputs heures pour la ligne idx
        jour_names = page.evaluate(f"""
            Array.from(document.querySelectorAll('input'))
                .filter(i => i.name && i.name.startsWith('jour') && i.name.endsWith('[{idx}]'))
                .map(i => i.name)
        """)

        # Remplir les heures Lun->Ven
        for day_idx, h in enumerate(hours):
            if day_idx < len(jour_names):
                page.fill(f'xpath=//input[@name="{jour_names[day_idx]}"]', str(h))

        # Soumettre -> page recharge avec la ligne figee + nouvelle ligne vide en dessous
        page.click('input[value="Envoyer"]')
        page.wait_for_load_state("networkidle")
        time.sleep(0.3)

    print(f"  OK Semaine {monday} complete ({len(template)} taches)")
    return True


# ── Main ─────────────────────────────────────────────────────────────────────

def run(weeks):
    print(f"\nNetOffice Filler — {len(weeks)} semaine(s) à traiter\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        page.set_default_timeout(15000)

        login(page, NETOFFICE_URL, NETOFFICE_USER, NETOFFICE_PASS)

        ok = 0
        skipped = 0
        errors = []

        for monday in weeks:
            tmpl = CONGE_TEMPLATE if monday in CONGE_MONDAYS else AB_SEO_TEMPLATE
            label = "CONGE" if monday in CONGE_MONDAYS else "AB-SEO"
            print(f"\n[{monday}] {label}")
            try:
                filled = fill_week(page, NETOFFICE_URL, monday, tmpl)
                if filled:
                    ok += 1
                else:
                    skipped += 1
            except PlaywrightTimeout as e:
                msg = f"Timeout semaine {monday} : {e}"
                print(f"  ✗ {msg}")
                errors.append(msg)
            except Exception as e:
                import traceback
                msg = f"Erreur semaine {monday} : {e}"
                print(f"  ✗ {msg}")
                traceback.print_exc()
                errors.append(msg)

        print(f"\n{'='*50}")
        print(f"Résultat : {ok} remplies | {skipped} déjà remplies | {len(errors)} erreurs")
        if errors:
            print("Erreurs :")
            for e in errors:
                print(f"  - {e}")

        print("\nFermeture dans 5s...")
        time.sleep(5)
        browser.close()


def main():
    parser = argparse.ArgumentParser(description="NetOffice Timesheet Filler")
    parser.add_argument("--week",      help="Remplir une seule semaine (YYYY-MM-DD, n'importe quel jour)")
    parser.add_argument("--from",      dest="from_date", help="Début backfill (YYYY-MM-DD)")
    parser.add_argument("--to",        dest="to_date",   help="Fin backfill (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.week:
        weeks = [monday_of(date.fromisoformat(args.week))]
    else:
        start = date.fromisoformat(args.from_date) if args.from_date else BACKFILL_FIRST_MONDAY
        end   = date.fromisoformat(args.to_date)   if args.to_date   else BACKFILL_LAST_MONDAY
        weeks = get_mondays(start, end)

    if not weeks:
        print("Aucune semaine à traiter.")
        return

    print("Semaines planifiées :")
    for w in weeks:
        label = "CONGE" if w in CONGE_MONDAYS else "AB-SEO"
        print(f"  {w}  [{label}]")

    confirm = input(f"\n{len(weeks)} semaine(s) — Lancer ? (o/n) : ").strip().lower()
    if confirm != "o":
        print("Annulé.")
        return

    run(weeks)


if __name__ == "__main__":
    main()
