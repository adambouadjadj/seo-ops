"""
tools/gsc_client.py
-------------------
Wrapper Google Search Console Search Analytics API.
Utilise le service account existant (credentials/service_account.json).

Prérequis : l'email SA doit être ajouté comme utilisateur (Owner) dans GSC.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

_HERE = Path(__file__).parent
CREDENTIALS_FILE = str(_HERE / "credentials" / "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Offsets snapshot tracker (jours depuis la date de publication)
DAY_OFFSETS = [-7, 0, 7, 14, 30, 60]
OFFSET_LABELS = {-7: "J-7 (base)", 0: "J0", 7: "J+7", 14: "J+14", 30: "J+30", 60: "J+60"}

# CTR attendu par position (courbe moyenne industrie %)
EXPECTED_CTR = {
    1: 28.5, 2: 15.7, 3: 11.0, 4: 8.0, 5: 6.3,
    6: 4.9, 7: 3.9, 8: 3.3, 9: 2.7, 10: 2.4,
    11: 2.1, 12: 1.8, 13: 1.6, 14: 1.4, 15: 1.3,
    16: 1.1, 17: 1.0, 18: 0.9, 19: 0.8, 20: 0.7,
}


def _load_env():
    env = {}
    env_file = _HERE / ".env"
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


_ENV = _load_env()
SITE_URL = _ENV.get("GSC_SITE_URL", "sc-domain:abcroisiere.com")


def get_service():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds)


def search_analytics(start_date, end_date, dimensions, row_limit=1000, extra=None):
    """
    Appelle searchanalytics.query sur SITE_URL.
    start_date / end_date : str "YYYY-MM-DD"
    dimensions : list ex. ["page"] ou ["query", "page"]
    extra : dict optionnel (ex. dimensionFilterGroups)
    Retourne la liste de rows (peut être vide).
    """
    service = get_service()
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    if extra:
        body.update(extra)
    resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
    return resp.get("rows", [])


# ── Tracker helpers ────────────────────────────────────────────────────────────

def snapshot_date_range(tracked_since, day_offset):
    """
    Retourne (start_str, end_str) pour la fenêtre GSC d'un snapshot.
    J-14 (baseline) = 14 jours avant tracked_since (fenêtre 14j).
    J0              = 7 jours avant tracked_since (fenêtre 7j).
    J+X             = fenêtre 7j se terminant à tracked_since + day_offset.
    """
    if day_offset == -7:
        # Fenêtre 7j se terminant 8 jours avant le push (non-chevauchante avec J0)
        end = tracked_since - timedelta(days=8)
        start = tracked_since - timedelta(days=14)
    elif day_offset == 0:
        end = tracked_since - timedelta(days=1)
        start = tracked_since - timedelta(days=7)
    else:
        end = tracked_since + timedelta(days=day_offset)
        start = end - timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def snapshot_available(tracked_since, day_offset):
    """True si la fenêtre GSC est passée (lag de 3 jours inclus)."""
    if day_offset <= 0:
        return True
    end = tracked_since + timedelta(days=day_offset)
    return date.today() >= end + timedelta(days=3)


def fetch_page_snapshot(url, tracked_since, day_offset):
    """
    Récupère les métriques + top 10 requêtes d'une URL pour le snapshot donné.
    Retourne un dict prêt à stocker.
    """
    start, end = snapshot_date_range(tracked_since, day_offset)

    # Métriques globales
    rows = search_analytics(
        start, end, ["page"],
        row_limit=1,
        extra={"dimensionFilterGroups": [{"filters": [
            {"dimension": "page", "operator": "equals", "expression": url}
        ]}]},
    )
    if rows:
        r = rows[0]
        metrics = {
            "clicks":       int(r.get("clicks", 0)),
            "impressions":  int(r.get("impressions", 0)),
            "ctr":          round(r.get("ctr", 0) * 100, 2),
            "avg_position": round(r.get("position", 0), 1),
        }
    else:
        metrics = {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": 0.0}

    # Top requêtes
    query_rows = search_analytics(
        start, end, ["query"],
        row_limit=10,
        extra={"dimensionFilterGroups": [{"filters": [
            {"dimension": "page", "operator": "equals", "expression": url}
        ]}]},
    )
    top_queries = [
        {
            "query":       r["keys"][0],
            "clicks":      int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr":         round(r.get("ctr", 0) * 100, 2),
            "position":    round(r.get("position", 0), 1),
        }
        for r in query_rows
    ]
    metrics["top_queries"] = json.dumps(top_queries, ensure_ascii=False)
    return metrics


# ── Insights helpers ───────────────────────────────────────────────────────────

def get_insights(days=90):
    """
    Retourne un dict avec 4 listes d'opportunités SEO.
    days : période d'analyse (28, 90 ou 180)
    """
    end = date.today() - timedelta(days=3)   # lag GSC
    start = end - timedelta(days=days - 1)
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")

    # ── 1. Toutes les pages (hors FP .html — gérées par la prod) ─────────────
    page_rows = search_analytics(start_str, end_str, ["page"], row_limit=500)
    pages = [
        {
            "url":          r["keys"][0],
            "clicks":       int(r.get("clicks", 0)),
            "impressions":  int(r.get("impressions", 0)),
            "ctr":          round(r.get("ctr", 0) * 100, 2),
            "position":     round(r.get("position", 0), 1),
        }
        for r in page_rows
        if not r["keys"][0].endswith(".html")
    ]

    # ── 2. Quick wins — pos 4-20, impressions >= 100 ───────────────────────────
    quick_wins = sorted(
        [p for p in pages if 4 <= p["position"] <= 20 and p["impressions"] >= 100],
        key=lambda x: (x["position"], -x["impressions"]),
    )

    # ── 3. CTR anormal — CTR < 50% du CTR attendu pour la position ────────────
    ctr_gap = []
    for p in pages:
        pos_int = round(p["position"])
        if pos_int < 1 or pos_int > 20 or p["impressions"] < 50:
            continue
        expected = EXPECTED_CTR.get(pos_int, 0.5)
        if p["ctr"] < expected * 0.5:
            ctr_gap.append({**p, "expected_ctr": expected, "gap": round(expected - p["ctr"], 1)})
    ctr_gap.sort(key=lambda x: (-x["impressions"], x["position"]))

    # ── 4. Impressions sans clics — CTR < 0.5%, impressions >= 200 ────────────
    no_clicks = sorted(
        [p for p in pages if p["ctr"] < 0.5 and p["impressions"] >= 200],
        key=lambda x: -x["impressions"],
    )

    # ── 5. Cannibalisation — même requête, 2+ pages dans top 20 ──────────────
    _BRAND = ("abcroisiere", "ab croisiere", "abcroisieres", "ab-croisiere")

    qp_rows = search_analytics(start_str, end_str, ["query", "page"], row_limit=5000)
    query_pages = {}
    for r in qp_rows:
        if round(r.get("position", 99), 0) > 20:
            continue
        q, p = r["keys"][0], r["keys"][1]
        if any(b in q.lower() for b in _BRAND):
            continue
        if q not in query_pages:
            query_pages[q] = []
        query_pages[q].append({
            "url":      p,
            "position": round(r.get("position", 0), 1),
            "clicks":   int(r.get("clicks", 0)),
        })
    cannibalisations = [
        {"query": q, "pages": sorted(ps, key=lambda x: x["position"])}
        for q, ps in query_pages.items()
        if len(ps) >= 2
    ]
    cannibalisations.sort(key=lambda x: -sum(p["clicks"] for p in x["pages"]))

    return {
        "quick_wins":       quick_wins[:50],
        "ctr_gap":          ctr_gap[:50],
        "no_clicks":        no_clicks[:50],
        "cannibalisations": cannibalisations[:30],
        "period_days":      days,
        "start_date":       start_str,
        "end_date":         end_str,
    }


# ── Questions & Longue traîne ──────────────────────────────────────────────────

_QUESTIONS_RE = re.compile(
    r"^(qui|quoi|quand|où|ou|pourquoi|comment|lequel|laquelle|lesquels|lesquelles)\b",
    re.IGNORECASE,
)
_LONGTAIL_RE = re.compile(r"^(\S+\s+){4,}\S+$")


def get_questions_longtail(days=28):
    """
    Retourne les requêtes GSC filtrées par :
     - Questions : mots interrogatifs (qui, comment, pourquoi…)
     - Longue traîne : ≥ 5 mots
    Avec badge is_new = True si absent ou < 5 impressions sur la période précédente.
    """
    end   = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    prev_end   = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    start_str      = start.strftime("%Y-%m-%d")
    end_str        = end.strftime("%Y-%m-%d")
    prev_start_str = prev_start.strftime("%Y-%m-%d")
    prev_end_str   = prev_end.strftime("%Y-%m-%d")

    # Requête avec page pour avoir la page principale par requête
    current_rows = search_analytics(start_str, end_str, ["query", "page"], row_limit=5000)
    prev_rows    = search_analytics(prev_start_str, prev_end_str, ["query"], row_limit=5000)

    prev_map = {r["keys"][0]: int(r.get("impressions", 0)) for r in prev_rows}

    # Agréger par requête : additionner clics/impressions, garder la page avec la meilleure position
    query_agg = {}
    for r in current_rows:
        q, page = r["keys"][0], r["keys"][1]
        pos = r.get("position", 99)
        if q not in query_agg:
            query_agg[q] = {
                "query":       q,
                "top_page":    page,
                "top_pos":     pos,
                "impressions": int(r.get("impressions", 0)),
                "clicks":      int(r.get("clicks", 0)),
                "ctr":         r.get("ctr", 0),
                "position":    pos,
                "count":       1,
            }
        else:
            agg = query_agg[q]
            agg["impressions"] += int(r.get("impressions", 0))
            agg["clicks"]      += int(r.get("clicks", 0))
            agg["count"]       += 1
            if pos < agg["top_pos"]:
                agg["top_page"] = page
                agg["top_pos"]  = pos
            # Position moyenne pondérée par les impressions
            total_impr = agg["impressions"]
            if total_impr > 0:
                agg["position"] = round(agg["top_pos"], 1)

    def _row(agg):
        q = agg["query"]
        # CTR recalculé sur les agrégats
        ctr = round(agg["clicks"] / agg["impressions"] * 100, 2) if agg["impressions"] else 0.0
        return {
            "query":       q,
            "page":        agg["top_page"],
            "impressions": agg["impressions"],
            "clicks":      agg["clicks"],
            "ctr":         ctr,
            "position":    round(agg["top_pos"], 1),
            "is_new":      prev_map.get(q, 0) < 5,
        }

    questions = sorted(
        [_row(v) for v in query_agg.values() if _QUESTIONS_RE.match(v["query"])],
        key=lambda x: -x["impressions"],
    )[:200]

    longtail = sorted(
        [_row(v) for v in query_agg.values() if _LONGTAIL_RE.match(v["query"])],
        key=lambda x: -x["impressions"],
    )[:200]

    return {
        "questions":      questions,
        "longtail":       longtail,
        "period_days":    days,
        "start_date":     start_str,
        "end_date":       end_str,
        "prev_start_date": prev_start_str,
        "prev_end_date":  prev_end_str,
    }
