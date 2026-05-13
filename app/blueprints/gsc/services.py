"""
app/blueprints/gsc/services.py
-------------------------------
Services pour le blueprint GSC :
 - Insights : quick wins, CTR gap, no-clicks, cannibalisations
 - Tracker  : CRUD TrackedPage + prise de snapshots
 - Questions GEO : questions/longue traîne GSC + Semrush PAA + export CSV
"""

import csv
import io
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

from app import db
from app.models import TrackedPage, PageSnapshot


# ── Insights ───────────────────────────────────────────────────────────────────

def run_insights(days=90):
    """
    Appelle gsc_client.get_insights() en ajoutant tools/ au path.
    Retourne le dict insights ou un dict {"error": "..."}.
    """
    _ensure_tools_in_path()
    try:
        from gsc_client import get_insights
        return get_insights(days=days)
    except Exception as e:
        return {"error": str(e)}


# ── Tracker ────────────────────────────────────────────────────────────────────

def list_tracked_pages():
    """Retourne toutes les pages trackées (actives en premier, puis archivées)."""
    return TrackedPage.query.order_by(
        TrackedPage.is_active.desc(),
        TrackedPage.tracked_since.desc()
    ).all()


def add_tracked_page(url, label, reason=None, tracked_since=None):
    """Crée une TrackedPage + prend le snapshot J0 (baseline) immédiatement."""
    if tracked_since is None:
        tracked_since = date.today()
    page = TrackedPage(url=url.strip(), label=label.strip(),
                       reason=reason, tracked_since=tracked_since)
    db.session.add(page)
    db.session.flush()  # pour avoir l'id avant le commit
    _take_snapshot(page, day_offset=-7)
    _take_snapshot(page, day_offset=0)
    db.session.commit()
    return page


def delete_tracked_page(page_id):
    page = TrackedPage.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()


def take_snapshot_for(page_id, day_offset):
    """Prend (ou re-prend) un snapshot pour une page + offset donnés."""
    page = TrackedPage.query.get_or_404(page_id)
    _take_snapshot(page, day_offset)
    db.session.commit()
    return page


def refresh_due_snapshots():
    """Prend tous les snapshots dus (disponibles mais pas encore pris)."""
    _ensure_tools_in_path()
    from gsc_client import snapshot_available, DAY_OFFSETS

    pages = TrackedPage.query.filter_by(is_active=True).all()
    taken = 0
    errors = []
    for page in pages:
        existing_offsets = {s.day_offset for s in page.snapshots}
        for offset in DAY_OFFSETS:
            if offset in existing_offsets:
                continue
            if not snapshot_available(page.tracked_since, offset):
                continue
            try:
                _take_snapshot(page, offset)
                taken += 1
            except Exception as e:
                errors.append(f"{page.label} J+{offset}: {e}")
    db.session.commit()
    return {"taken": taken, "errors": errors}


def _take_snapshot(page, day_offset):
    """Interne : appelle GSC et insère/met à jour le snapshot."""
    _ensure_tools_in_path()
    from gsc_client import fetch_page_snapshot

    metrics = fetch_page_snapshot(page.url, page.tracked_since, day_offset)

    # Upsert : si déjà existant, on met à jour
    existing = PageSnapshot.query.filter_by(
        tracked_page_id=page.id, day_offset=day_offset
    ).first()
    if existing:
        existing.snapshot_date = date.today()
        existing.clicks        = metrics["clicks"]
        existing.impressions   = metrics["impressions"]
        existing.ctr           = metrics["ctr"]
        existing.avg_position  = metrics["avg_position"]
        existing.top_queries   = metrics["top_queries"]
    else:
        snap = PageSnapshot(
            tracked_page_id=page.id,
            day_offset=day_offset,
            snapshot_date=date.today(),
            clicks=metrics["clicks"],
            impressions=metrics["impressions"],
            ctr=metrics["ctr"],
            avg_position=metrics["avg_position"],
            top_queries=metrics["top_queries"],
        )
        db.session.add(snap)


def _ensure_tools_in_path():
    """Ajoute tools/ au sys.path pour pouvoir importer gsc_client."""
    tools_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools")
    tools_dir = os.path.abspath(tools_dir)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)


# ── Helpers template ───────────────────────────────────────────────────────────

def snapshot_map(page):
    """
    Retourne un dict {day_offset: snapshot} pour une page.
    En cas de doublons sur un même offset, conserve le plus récent.
    """
    result = {}
    for s in sorted(page.snapshots, key=lambda x: x.snapshot_date or date.min):
        result[s.day_offset] = s
    return result


def parse_top_queries(snapshot):
    """Désérialise le JSON top_queries d'un snapshot."""
    if snapshot and snapshot.top_queries:
        try:
            return json.loads(snapshot.top_queries)
        except Exception:
            pass
    return []


# ── Insights export ────────────────────────────────────────────────────────────

def build_insights_csv(data):
    """Génère un CSV des 4 sections Insights. Retourne str."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Quick wins
    writer.writerow(["=== QUICK WINS (pos 4-20, impr >= 100) ==="])
    writer.writerow(["URL", "Position", "Impressions", "Clics", "CTR"])
    for p in data.get("quick_wins", []):
        writer.writerow([p["url"], p["position"], p["impressions"], p["clicks"], p["ctr"]])

    writer.writerow([])

    # CTR anormal
    writer.writerow(["=== CTR ANORMAL ==="])
    writer.writerow(["URL", "Position", "CTR réel", "CTR attendu", "Manque (pts)", "Impressions"])
    for p in data.get("ctr_gap", []):
        writer.writerow([p["url"], p["position"], p["ctr"], p["expected_ctr"], p["gap"], p["impressions"]])

    writer.writerow([])

    # Impressions sans clics
    writer.writerow(["=== IMPRESSIONS SANS CLICS ==="])
    writer.writerow(["URL", "Impressions", "CTR", "Position"])
    for p in data.get("no_clicks", []):
        writer.writerow([p["url"], p["impressions"], p["ctr"], p["position"]])

    writer.writerow([])

    # Cannibalisations
    writer.writerow(["=== CANNIBALISATIONS ==="])
    writer.writerow(["Requête", "URL", "Position", "Clics"])
    for c in data.get("cannibalisations", []):
        for pg in c["pages"]:
            writer.writerow([c["query"], pg["url"], pg["position"], pg["clicks"]])

    return output.getvalue()


# ── Questions GEO ──────────────────────────────────────────────────────────────

def run_questions_longtail(days=28):
    """Appelle gsc_client.get_questions_longtail(). Retourne le dict ou {"error": ...}."""
    _ensure_tools_in_path()
    try:
        from gsc_client import get_questions_longtail
        return get_questions_longtail(days=days)
    except Exception as e:
        return {"error": str(e)}


def get_semrush_questions(keyword, database="fr"):
    """
    Appelle l'API Semrush phrase_questions pour un mot-clé.
    Nécessite SEMRUSH_API_KEY dans tools/.env.
    Retourne {"rows": [...], "has_key": bool, "error": str|None, "keyword": str, "database": str}
    """
    import requests

    # Charger la clé depuis tools/.env
    env_path = Path(__file__).parent.parent.parent.parent / "tools" / ".env"
    api_key = _read_env_key(env_path, "SEMRUSH_API_KEY")

    result = {"rows": [], "has_key": bool(api_key), "error": None,
               "keyword": keyword, "database": database}

    if not api_key:
        result["error"] = "Configurer SEMRUSH_API_KEY dans tools/.env"
        return result

    if not keyword:
        result["error"] = "Mot-clé vide"
        return result

    url = (
        f"https://api.semrush.com/?type=phrase_questions"
        f"&key={api_key}"
        f"&phrase={quote(keyword)}"
        f"&database={database}"
        f"&export_columns=Ph,Nq,Co"
        f"&display_limit=20"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()

        if "ERROR" in text or "NOTHING FOUND" in text or not text:
            return result  # rows vides, pas d'erreur affichée

        lines = text.splitlines()
        if len(lines) < 2:
            return result

        rows = []
        for line in lines[1:]:  # skip header
            parts = line.split(";")
            if len(parts) < 3:
                continue
            try:
                volume = int(parts[1]) if parts[1].strip() else 0
            except ValueError:
                volume = 0
            try:
                competition = float(parts[2]) if parts[2].strip() not in ("", "N/A") else 0.0
            except ValueError:
                competition = 0.0
            rows.append({"phrase": parts[0].strip(), "volume": volume,
                          "competition": round(competition, 2)})
        result["rows"] = rows

    except Exception as e:
        result["error"] = str(e)

    return result


def build_questions_csv(gsc_data, semrush_data):
    """
    Génère un CSV GEO couvrant questions GSC, longue traîne GSC et questions Semrush.
    Retourne une chaîne CSV (str).
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Requête", "Page", "Source", "Statut", "Impressions", "Clics",
        "CTR", "Position", "Volume_Semrush", "Intent", "Thème",
    ])

    for row in gsc_data.get("questions", []):
        writer.writerow([
            row["query"], row.get("page", ""), "GSC_questions",
            "nouveau" if row.get("is_new") else "existant",
            row["impressions"], row["clicks"], row["ctr"], row["position"],
            "", "", "",
        ])

    for row in gsc_data.get("longtail", []):
        writer.writerow([
            row["query"], row.get("page", ""), "GSC_longtail",
            "nouveau" if row.get("is_new") else "existant",
            row["impressions"], row["clicks"], row["ctr"], row["position"],
            "", "", "",
        ])

    for row in semrush_data.get("rows", []):
        writer.writerow([
            row["phrase"], "Semrush", "", "", "", "", "",
            row["volume"], "", "",
        ])

    return output.getvalue()


def _read_env_key(env_path, key):
    """Lit une clé spécifique dans un fichier .env."""
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""
