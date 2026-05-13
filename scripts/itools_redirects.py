"""
iTools Redirects Filler — Playwright Chromium
Importe des redirections 301/410 dans iTools (Karavel).

Credentials dans tools/.env :
  ITOOLS_USER=xxx
  ITOOLS_PASSWORD=xxx
  ITOOLS_URL=http://webint.ws.in.karavel.com:10670/seo.admin.webapp/redirects

Usage :
  python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode dry-run
  python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode test
  python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode run
  python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_410.dedup.csv --mode run
  python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode resume --log scripts/logs/itools_2026-05-06_120000.csv

Format CSV attendu (301) :
  URL actuelle (404), Action, URL cible (200), Nom bateau, Navire ID

Format CSV attendu (410) :
  URL actuelle (404), Action, Nom bateau, Navire ID
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ─────────────────────────────────────────────────────────────────────

_ENV = Path(__file__).parent.parent / "tools" / ".env"
load_dotenv(dotenv_path=_ENV)

ITOOLS_URL  = os.getenv("ITOOLS_URL", "http://webint.ws.in.karavel.com:10670/seo.admin.webapp/redirects")
ITOOLS_USER = os.getenv("ITOOLS_USER", "")
ITOOLS_PASS = os.getenv("ITOOLS_PASSWORD", "")

# Valeurs fixes
SITE_ARTEFACT = "abcroisiereCom"
DOMAINE       = "www.abcroisiere.com"
STATUS_VAL    = "ACTIVE"

# Colonnes CSV
COL_SOURCE = "URL actuelle (404)"
COL_TARGET = "URL cible (200)"
COL_ACTION = "Action"


# ── Helpers CSV ────────────────────────────────────────────────────────────────

def to_path(url: str) -> str:
    """Extrait le pathname d'une URL complète. Renvoie la valeur telle quelle si déjà un path."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http"):
        return urlparse(url).path
    return url


def load_csv(filepath: str) -> list[dict]:
    with open(filepath, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_processed(log_path: str) -> set[str]:
    """Retourne les sources déjà traitées avec succès depuis un log existant (mode resume)."""
    done = set()
    if not log_path or not Path(log_path).exists():
        return done
    with open(log_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("result") in ("created", "already_exists"):
                done.add(row["source"])
    return done


def make_log_path() -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / f"itools_{ts}.csv"


def write_log_header(log_path: Path):
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow(["line", "action", "source", "target", "result", "message", "timestamp"])


def append_log(log_path: Path, line: int, action: str, source: str,
               target: str, result: str, message: str):
    with open(log_path, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            line, action, source, target, result, message,
            datetime.now().isoformat(timespec="seconds"),
        ])


# ── Playwright ─────────────────────────────────────────────────────────────────

def login(page):
    print(f"  >> Navigation vers iTools...")
    page.goto(ITOOLS_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    # iTools redirige vers /login si non authentifié
    if "login" in page.url:
        print(f"  >> Connexion ({ITOOLS_USER})...")
        page.locator("input#username").fill(ITOOLS_USER)
        page.locator("input#password").fill(ITOOLS_PASS)
        page.locator("form").evaluate("f => f.submit()")
        page.wait_for_timeout(3000)  # attend la redirection post-login (vers /nifo)
        if "login" in page.url:
            raise RuntimeError("Echec login — vérifiez ITOOLS_USER / ITOOLS_PASSWORD dans tools/.env")
        print("  OK Connecté")
        # Post-login, iTools redirige toujours vers /nifo — on navigue vers /redirects
        print(f"  >> Redirection vers /redirects...")
        page.goto(ITOOLS_URL, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
    else:
        print("  OK Session active")


def _form_item(page, label: str):
    """Retourne le locator vaadin-form-item correspondant au label donné."""
    return page.locator(f'vaadin-form-item:has(label:text-is("{label}"))')


def click_new(page):
    """Ferme tout formulaire/overlay ouvert, puis clique New."""
    # Ferme les overlays ouverts (dropdown resté ouvert après erreur)
    page.evaluate("""() => {
        document.querySelectorAll('vaadin-select-overlay, vaadin-overlay').forEach(o => {
            try { o.opened = false; } catch(e) {}
        });
    }""")
    page.wait_for_timeout(150)
    # Ferme les formulaires ouverts via leur bouton X
    page.evaluate("""() => {
        document.querySelectorAll('vaadin-button[theme="icon"]').forEach(btn => {
            if (btn.querySelector('vaadin-icon[icon="vaadin:close"]')) btn.click();
        });
    }""")
    page.wait_for_timeout(300)
    # Clique New via JS
    page.evaluate("""() => {
        const btn = [...document.querySelectorAll('vaadin-button')]
            .find(b => b.textContent.trim() === 'New');
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(600)


def fill_field(page, label: str, value: str):
    """Remplit un champ vaadin-text-field par son label (dernier form-item si plusieurs)."""
    _form_item(page, label).last.locator('input[slot="input"]').fill(value)


def select_field(page, label: str, value: str):
    """Sélectionne une option dans un vaadin-select par son label.
    Les items sont des vaadin-select-item avec un attribut label= (texte dans shadow-root).
    """
    # Ouvre le dropdown via JS (dernier form-item avec ce label)
    page.evaluate(f"""() => {{
        const items = [...document.querySelectorAll('vaadin-form-item')].reverse();
        const fi = items.find(fi =>
            [...fi.querySelectorAll('label')].some(l => l.textContent.trim() === '{label}')
        );
        if (fi) {{
            const btn = fi.querySelector('vaadin-select-value-button');
            if (btn) btn.click();
        }}
    }}""")
    page.wait_for_timeout(400)
    # Clique l'item par son attribut label= (pas textContent qui est dans le shadow-root)
    clicked = page.evaluate(f"""() => {{
        const item = document.querySelector('vaadin-select-item[label="{value}"]');
        if (!item) return false;
        item.click();
        return true;
    }}""")
    if not clicked:
        raise RuntimeError(f"Option '{value}' introuvable dans '{label}'")
    page.wait_for_timeout(200)


def detect_result(page) -> tuple[str, str]:
    """
    Lit le retour après Save (interface Vaadin).
    Retourne (result, message) : created | already_exists | failed
    """
    # 1. vaadin-notification (message toast Vaadin)
    notif = page.locator("vaadin-notification-container")
    if notif.count() > 0:
        try:
            text = notif.inner_text().strip()
            if text:
                if any(w in text.lower() for w in ["already", "déjà", "existe", "duplicate"]):
                    return "already_exists", text[:200]
                if any(w in text.lower() for w in ["error", "erreur", "invalid", "failed"]):
                    return "failed", text[:200]
                return "created", text[:200]
        except Exception:
            pass

    # 2. Dialog d'erreur Vaadin
    dialog = page.locator("vaadin-dialog-overlay")
    if dialog.count() > 0:
        try:
            text = dialog.inner_text().strip()
            if text:
                if any(w in text.lower() for w in ["already", "déjà", "existe", "duplicate"]):
                    return "already_exists", text[:200]
                return "failed", text[:200]
        except Exception:
            pass

    # 3. Champ Url Source vide = formulaire réinitialisé après Save réussi
    try:
        val = _form_item(page, "Url Source").last.locator('input[slot="input"]').input_value()
        if not val:
            return "created", "form reset"
    except Exception:
        pass

    return "created", "no error detected"


def fill_redirect(page, source: str, target: str, code_http: str) -> tuple[str, str]:
    """Remplit et sauvegarde une redirection. Retourne (result, message)."""
    click_new(page)

    fill_field(page, "Url Source", source)
    fill_field(page, "Domaine", DOMAINE)
    select_field(page, "Site Artefact", SITE_ARTEFACT)
    fill_field(page, "Url Cible", target)  # vide pour 410
    fill_field(page, "Code Http", code_http)
    select_field(page, "Status", STATUS_VAL)

    page.locator('vaadin-button:has-text("Save")').last.click()
    page.wait_for_timeout(2000)

    return detect_result(page)


# ── Modes ──────────────────────────────────────────────────────────────────────

def dry_run(rows: list[dict]):
    print(f"\n{'='*60}")
    print(f"DRY RUN — {len(rows)} ligne(s)\n")
    for i, row in enumerate(rows, 1):
        source = to_path(row[COL_SOURCE])
        action = row[COL_ACTION]
        target = to_path(row.get(COL_TARGET, ""))
        print(f"  [{i:03d}] {action}  {source}  →  {target or '(vide)'}")
    print(f"\n{'='*60}")
    print("Fin dry-run — aucune modification effectuée.")


def run_browser(rows: list[dict], mode: str, log_path: Path, skip: set[str], limit: int = 0):
    if not limit:
        limit = 5 if mode == "test" else len(rows)
    to_do  = [r for r in rows if to_path(r[COL_SOURCE]) not in skip][:limit]
    skipped_count = len(rows) - len(to_do) if mode == "resume" else 0

    print(f"\niTools Redirects — {mode.upper()} — {len(to_do)} ligne(s) à traiter")
    if skipped_count:
        print(f"  (+ {skipped_count} déjà traitées, skippées)")

    write_log_header(log_path)
    created = already = failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page    = browser.new_page()
        page.set_default_timeout(15000)

        try:
            login(page)
        except Exception as e:
            browser.close()
            sys.exit(f"Erreur login : {e}")

        for i, row in enumerate(to_do, 1):
            source    = to_path(row[COL_SOURCE])
            action    = row[COL_ACTION]
            target    = to_path(row.get(COL_TARGET, ""))
            code_http = action  # "301" ou "410"

            print(f"  [{i:03d}/{len(to_do)}] {code_http}  {source}", end="  ...  ", flush=True)

            try:
                result, message = fill_redirect(page, source, target, code_http)
            except PlaywrightTimeout as e:
                result, message = "failed", f"Timeout: {e}"
            except Exception as e:
                result, message = "failed", str(e)

            # Log
            line_num = rows.index(row) + 1
            append_log(log_path, line_num, action, source, target, result, message)

            if result == "created":
                created += 1
                print("OK créé")
            elif result == "already_exists":
                already += 1
                print("already_exists")
            else:
                failed += 1
                print(f"FAILED: {message}")
                # Screenshot
                try:
                    ss_dir = log_path.parent / "screenshots"
                    ss_dir.mkdir(exist_ok=True)
                    page.screenshot(path=str(ss_dir / f"failed_{i:03d}_{source.replace('/', '_')[:40]}.png"))
                except Exception:
                    pass

            time.sleep(0.2)

        print(f"\n{'='*60}")
        print(f"Résultat : {created} créées | {already} déjà existantes | {failed} erreurs")
        print(f"Log      : {log_path}")

        print("\nFermeture dans 5s...")
        time.sleep(5)
        browser.close()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="iTools Redirects Filler")
    parser.add_argument("--file", required=True,
                        help="Chemin du CSV source (301 ou 410)")
    parser.add_argument("--mode", required=True,
                        choices=["dry-run", "test", "run", "resume"],
                        help="dry-run | test (5 lignes max) | run (tout) | resume (reprendre depuis log)")
    parser.add_argument("--log",
                        help="Log CSV existant pour --mode resume")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de lignes (ex: --limit 20)")
    args = parser.parse_args()

    if not Path(args.file).exists():
        sys.exit(f"Fichier introuvable : {args.file}")

    rows = load_csv(args.file)
    print(f"CSV chargé : {len(rows)} lignes  ({args.file})")

    if args.mode == "dry-run":
        dry_run(rows)
        return

    if not ITOOLS_USER or not ITOOLS_PASS:
        sys.exit("ITOOLS_USER / ITOOLS_PASSWORD manquants dans tools/.env")

    skip = set()
    if args.mode == "resume":
        if not args.log:
            sys.exit("--mode resume requiert --log <chemin_log>")
        skip = load_processed(args.log)
        print(f"Resume : {len(skip)} ligne(s) déjà traitées (skippées)")

    log_path = Path(args.log) if args.mode == "resume" else make_log_path()

    if args.limit:
        limit_label = f"{args.limit} lignes max (--limit)"
    elif args.mode == "test":
        limit_label = "5 lignes max"
    else:
        limit_label = f"{len(rows)} lignes"
    confirm = input(f"\nMode {args.mode.upper()} — {limit_label} — Lancer ? (o/n) : ").strip().lower()
    if confirm != "o":
        print("Annulé.")
        return

    run_browser(rows, args.mode, log_path, skip, limit=args.limit)


if __name__ == "__main__":
    main()
