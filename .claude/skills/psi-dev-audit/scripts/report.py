#!/usr/bin/env python3
"""
PSI dev audit — génération ticket.md + CSVs cumulatifs depuis JSON bruts.
Usage: python report.py runs/YYYY-MM-DD/
"""

import csv
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]


def score_emoji(score):
    if score is None:
        return ""
    if score >= 0.9:
        return "🟢"
    if score >= 0.5:
        return "🟠"
    return "🔴"


def fmt_ms(val, unit="ms"):
    if val is None:
        return "—"
    if unit == "ms":
        return f"{round(val)}ms"
    return f"{val:.2f}s"


def fmt_kb(b):
    if b is None:
        return "—"
    return f"{round(b / 1024)} KB"


def parse_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_metrics(lhr):
    audits = lhr.get("audits", {})
    cats = lhr.get("categories", {})

    def metric(key):
        a = audits.get(key, {})
        return {"value": a.get("numericValue"), "score": a.get("score")}

    return {
        "perf_score": cats.get("performance", {}).get("score"),
        "fcp": metric("first-contentful-paint"),
        "lcp": metric("largest-contentful-paint"),
        "tbt": metric("total-blocking-time"),
        "cls": metric("cumulative-layout-shift"),
        "si": metric("speed-index"),
    }


def extract_third_party(lhr):
    audits = lhr.get("audits", {})
    # Lighthouse 12+: third-parties-insight; older: third-party-summary
    tps = audits.get("third-parties-insight") or audits.get("third-party-summary") or {}
    items = tps.get("details", {}).get("items", [])
    result = []
    for item in items:
        entity = item.get("entity", "")
        if isinstance(entity, dict):
            entity = entity.get("text", str(entity))
        sub_items = []
        sub = item.get("subItems", {}).get("items", [])
        for s in sub:
            url = s.get("url", "")
            if isinstance(url, dict):
                url = url.get("url", str(url))
            sub_items.append({
                "url": url,
                "mainThreadTime": s.get("mainThreadTime"),
            })
        result.append({
            "entity": entity,
            "mainThreadTime": item.get("mainThreadTime"),
            "blockingTime": item.get("blockingTime") or item.get("tbtImpact"),
            "transferSize": item.get("transferSize"),
            "subItems": sub_items,
        })
    return result


def extract_bootup(lhr):
    items = lhr.get("audits", {}).get("bootup-time", {}).get("details", {}).get("items", [])
    result = []
    for item in items:
        url = item.get("url", "")
        if isinstance(url, dict):
            url = url.get("url", str(url))
        result.append({
            "url": url,
            "total": item.get("total"),
            "scripting": item.get("scripting"),
            "scriptParseCompile": item.get("scriptParseCompile"),
        })
    return result


def extract_mainthread(lhr):
    audit = lhr.get("audits", {}).get("mainthread-work-breakdown", {})
    items = audit.get("details", {}).get("items", [])
    display = audit.get("displayValue", "")
    groups = []
    for item in items:
        label = item.get("groupLabel", "")
        if isinstance(label, dict):
            label = label.get("value", str(label))
        groups.append({"label": label, "duration": item.get("duration")})
    return {"displayValue": display, "groups": groups}


def extract_lcp_element(lhr):
    audits = lhr.get("audits", {})
    selector = ""
    snippet = ""
    phases = []

    # Lighthouse 12+: lcp-breakdown-insight
    lcp_b = audits.get("lcp-breakdown-insight", {})
    b_items = lcp_b.get("details", {}).get("items", [])
    for b_item in b_items:
        if b_item.get("type") == "node":
            selector = b_item.get("selector", "")
            snippet = b_item.get("snippet", "")
        elif b_item.get("type") == "table":
            for phase in b_item.get("items", []):
                label = phase.get("label") or phase.get("subpart", "")
                phases.append({"label": label, "duration": phase.get("duration")})

    # Fallback: oldest format largest-contentful-paint-element
    if not selector:
        old = audits.get("largest-contentful-paint-element", {})
        old_items = old.get("details", {}).get("items", [])
        if old_items:
            sub = old_items[0].get("items", [])
            if sub:
                node = sub[0].get("node", {})
                if isinstance(node, dict):
                    selector = node.get("selector", "")
                    snippet = node.get("snippet", "")

    display = lcp_b.get("displayValue", "")
    return {"displayValue": display, "selector": selector, "snippet": snippet, "phases": phases}


def extract_render_blocking(lhr):
    audits = lhr.get("audits", {})
    # Lighthouse 12+: render-blocking-insight; older: render-blocking-resources
    audit = audits.get("render-blocking-insight") or audits.get("render-blocking-resources") or {}
    items = audit.get("details", {}).get("items", [])
    result = []
    for item in items:
        url = item.get("url", "")
        if isinstance(url, dict):
            url = url.get("url", str(url))
        result.append({
            "url": url,
            "totalBytes": item.get("totalBytes"),
            "wastedMs": item.get("wastedMs"),
        })
    return result


def build_ticket(run_date, pages_data):
    lines = []
    lines.append(f"# Ticket Web Perf ABCroisières — {run_date}\n")

    # Synthèse
    lines.append("## Synthèse par template\n")
    lines.append("| Template | Device | Perf | FCP | LCP | TBT | CLS | SI |")
    lines.append("|----------|--------|------|-----|-----|-----|-----|-----|")

    for p in pages_data:
        m = p["metrics"]
        ps = m["perf_score"]
        fcp = m["fcp"]
        lcp = m["lcp"]
        tbt = m["tbt"]
        cls = m["cls"]
        si = m["si"]

        def cell(metric, is_ms=True):
            v = metric["value"]
            s = metric["score"]
            if v is None:
                return "—"
            display = f"{v/1000:.1f}s" if is_ms else f"{v:.3f}"
            return f"{display} {score_emoji(s)}"

        perf_str = f"{round(ps * 100)} {score_emoji(ps)}" if ps is not None else "—"
        row = (
            f"| {p['label_display']} | {p['device'].capitalize()} "
            f"| {perf_str} "
            f"| {cell(fcp)} "
            f"| {cell(lcp)} "
            f"| {cell(tbt)} "
            f"| {cell(cls, is_ms=False)} "
            f"| {cell(si)} |"
        )
        lines.append(row)

    lines.append("")

    # Diagnostic par template
    lines.append("## Diagnostic par template\n")

    for p in pages_data:
        m = p["metrics"]
        device_cap = p["device"].capitalize()
        lines.append(f"### {p['label_display']} ({device_cap})\n")

        # LCP element
        lcp_el = p["lcp_element"]
        if lcp_el["selector"] or lcp_el["snippet"] or lcp_el.get("phases"):
            lines.append("**LCP — Élément identifié**")
            if lcp_el["selector"]:
                lines.append(f"- Sélecteur : `{lcp_el['selector']}`")
            if lcp_el["snippet"]:
                lines.append(f"- HTML : `{lcp_el['snippet'][:120]}`")
            phases = lcp_el.get("phases", [])
            if phases:
                phase_parts = []
                for ph in phases:
                    label = ph["label"]
                    dur = ph["duration"]
                    dur_str = f"{round(dur)}ms" if dur is not None else "—"
                    phase_parts.append(f"{label} {dur_str}")
                lines.append(f"- Phases : {' / '.join(phase_parts)}")
            lines.append("")

        # Render blocking
        rb = p["render_blocking"]
        if rb:
            lines.append("**FCP — Ressources bloquantes**")
            lines.append("| URL | Taille | Économies potentielles |")
            lines.append("|-----|--------|------------------------|")
            for r in rb:
                url = r["url"]
                size = fmt_kb(r["totalBytes"])
                wasted = fmt_ms(r["wastedMs"])
                lines.append(f"| `{url}` | {size} | {wasted} |")
            lines.append("")

        # Third-party scripts
        tp = p["third_party"]
        if tp:
            lines.append("**TBT — Scripts tiers (temps CPU par entité)**")
            lines.append("| Entité | Main Thread (ms) | Blocking (ms) | Transfer Size |")
            lines.append("|--------|------------------|---------------|---------------|")
            for t in tp:
                mt = f"{round(t['mainThreadTime'])}ms" if t["mainThreadTime"] is not None else "—"
                bt = f"{round(t['blockingTime'])}ms" if t["blockingTime"] is not None else "—"
                ts = fmt_kb(t["transferSize"])
                lines.append(f"| {t['entity']} | {mt} | {bt} | {ts} |")
                for s in t.get("subItems", []):
                    smt = f"{round(s['mainThreadTime'])}ms" if s["mainThreadTime"] is not None else "—"
                    short_url = s["url"]
                    if len(short_url) > 80:
                        short_url = "…" + short_url[-77:]
                    lines.append(f"| &nbsp;&nbsp;↳ `{short_url}` | {smt} | — | — |")
            lines.append("")

        # Main thread breakdown
        mt = p["mainthread"]
        if mt["groups"]:
            lines.append(f"**Thread principal — Répartition ({mt['displayValue']})**")
            lines.append("| Groupe | Durée |")
            lines.append("|--------|-------|")
            for g in mt["groups"]:
                dur = f"{g['duration'] / 1000:.1f}s" if g["duration"] is not None else "—"
                lines.append(f"| {g['label']} | {dur} |")
            lines.append("")

        # Bootup time
        bootup = p["bootup"]
        if bootup:
            lines.append("**Scripts — Détail CPU par URL**")
            lines.append("| URL | CPU total | Scripting | Parse/Compile |")
            lines.append("|-----|-----------|-----------|---------------|")
            for b in bootup:
                url = b["url"]
                if len(url) > 80:
                    url = "…" + url[-77:]
                total = fmt_ms(b["total"])
                scripting = fmt_ms(b["scripting"])
                parse = fmt_ms(b["scriptParseCompile"])
                lines.append(f"| `{url}` | {total} | {scripting} | {parse} |")
            lines.append("")

    return "\n".join(lines)


def write_csv_cumulative(path, fieldnames, rows):
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) < 2:
        print("Usage: python report.py runs/YYYY-MM-DD/")
        sys.exit(1)

    runs_path = Path(sys.argv[1])
    if not runs_path.is_absolute():
        runs_path = Path.cwd() / runs_path

    if not runs_path.exists():
        print(f"Dossier introuvable : {runs_path}")
        sys.exit(1)

    run_date = runs_path.name
    outputs_dir = SKILL_DIR / "outputs" / run_date
    outputs_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(runs_path.glob("*.json"))
    if not json_files:
        print("Aucun JSON trouvé dans ce dossier.")
        sys.exit(1)

    pages_data = []

    for jf in json_files:
        stem = jf.stem
        parts = stem.rsplit("_", 1)
        if len(parts) != 2 or parts[1] not in ("mobile", "desktop"):
            print(f"  [SKIP] Nom de fichier inattendu : {jf.name}")
            continue

        label = parts[0]
        device = parts[1]
        label_display = label.replace("_", " ").title()

        data = parse_json(jf)
        lhr = data.get("lighthouseResult", {})

        metrics = extract_metrics(lhr)
        third_party = extract_third_party(lhr)
        bootup = extract_bootup(lhr)
        mainthread = extract_mainthread(lhr)
        lcp_element = extract_lcp_element(lhr)
        render_blocking = extract_render_blocking(lhr)

        pages_data.append({
            "label": label,
            "label_display": label_display,
            "device": device,
            "metrics": metrics,
            "third_party": third_party,
            "bootup": bootup,
            "mainthread": mainthread,
            "lcp_element": lcp_element,
            "render_blocking": render_blocking,
        })

    # Trier : mobile avant desktop, par label
    pages_data.sort(key=lambda x: (x["label"], x["device"] != "mobile"))

    # ticket.md
    ticket = build_ticket(run_date, pages_data)
    ticket_path = outputs_dir / "ticket.md"
    with open(ticket_path, "w", encoding="utf-8") as f:
        f.write(ticket)
    print(f"ticket.md généré : {ticket_path}")

    # audits.csv (cumulatif)
    audits_csv_path = SKILL_DIR / "outputs" / "audits.csv"
    audits_rows = []
    for p in pages_data:
        m = p["metrics"]
        lcp_el = p["lcp_element"]
        mt_display = p["mainthread"]["displayValue"]
        # parse total seconds from displayValue like "6.1 s"
        mt_total = ""
        if mt_display:
            import re
            match = re.search(r"[\d.]+", mt_display)
            if match:
                mt_total = match.group()
        audits_rows.append({
            "date": run_date,
            "template": p["label"],
            "device": p["device"],
            "perf_score": round(m["perf_score"] * 100) if m["perf_score"] is not None else "",
            "fcp_ms": round(m["fcp"]["value"]) if m["fcp"]["value"] is not None else "",
            "fcp_score": m["fcp"]["score"] if m["fcp"]["score"] is not None else "",
            "lcp_ms": round(m["lcp"]["value"]) if m["lcp"]["value"] is not None else "",
            "lcp_score": m["lcp"]["score"] if m["lcp"]["score"] is not None else "",
            "tbt_ms": round(m["tbt"]["value"]) if m["tbt"]["value"] is not None else "",
            "tbt_score": m["tbt"]["score"] if m["tbt"]["score"] is not None else "",
            "cls": m["cls"]["value"] if m["cls"]["value"] is not None else "",
            "cls_score": m["cls"]["score"] if m["cls"]["score"] is not None else "",
            "si_ms": round(m["si"]["value"]) if m["si"]["value"] is not None else "",
            "lcp_element": lcp_el["selector"],
            "mainthread_total_s": mt_total,
        })
    write_csv_cumulative(
        audits_csv_path,
        ["date", "template", "device", "perf_score", "fcp_ms", "fcp_score",
         "lcp_ms", "lcp_score", "tbt_ms", "tbt_score", "cls", "cls_score",
         "si_ms", "lcp_element", "mainthread_total_s"],
        audits_rows,
    )
    print(f"audits.csv mis à jour : {audits_csv_path}")

    # third_party_scripts.csv (cumulatif)
    tp_csv_path = SKILL_DIR / "outputs" / "third_party_scripts.csv"
    tp_rows = []
    for p in pages_data:
        for t in p["third_party"]:
            tp_rows.append({
                "date": run_date,
                "template": p["label"],
                "device": p["device"],
                "entity": t["entity"],
                "main_thread_ms": round(t["mainThreadTime"]) if t["mainThreadTime"] is not None else "",
                "blocking_ms": round(t["blockingTime"]) if t["blockingTime"] is not None else "",
                "transfer_size_kb": round(t["transferSize"] / 1024, 1) if t["transferSize"] is not None else "",
            })
    write_csv_cumulative(
        tp_csv_path,
        ["date", "template", "device", "entity", "main_thread_ms", "blocking_ms", "transfer_size_kb"],
        tp_rows,
    )
    print(f"third_party_scripts.csv mis à jour : {tp_csv_path}")
    print(f"\nRapport complet dans : {outputs_dir}")


if __name__ == "__main__":
    main()
