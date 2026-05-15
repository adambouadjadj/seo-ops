#!/usr/bin/env python3
"""
PSI dev audit — appels API PageSpeed Insights + stockage JSON brut.
Usage: python audit.py configs/abcroisieres.yaml
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests
import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_PATH = PROJECT_ROOT / "tools" / ".env"
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def load_env(path):
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


def call_psi(url, strategy, api_key, retries=2):
    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
        "locale": "fr",
    }
    if api_key:
        params["key"] = api_key

    for attempt in range(retries + 1):
        try:
            resp = requests.get(PSI_ENDPOINT, params=params, timeout=60)
            if resp.status_code == 429:
                print(f"    [429] Rate limit — attente 10s avant retry")
                time.sleep(10)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries:
                print(f"    [Erreur attempt {attempt+1}] {e} — retry dans 3s")
                time.sleep(3)
            else:
                print(f"    [ECHEC] {url} ({strategy}) ignoré : {e}")
                return None
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python audit.py <config.yaml>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    env = load_env(ENV_PATH)
    api_key = env.get("PSI_API_KEY", "")
    if not api_key:
        print("[WARN] PSI_API_KEY non trouvée dans tools/.env — appels sans clé (quota réduit)")

    today = date.today().isoformat()
    runs_dir = SKILL_DIR / "runs" / today
    runs_dir.mkdir(parents=True, exist_ok=True)

    pages = config.get("pages", [])
    total = len(pages) * 2
    done = 0

    for page in pages:
        label = page["label"]
        url = page["url"]

        for strategy in ("mobile", "desktop"):
            done += 1
            print(f"[{done}/{total}] {label} — {strategy} : {url}")
            data = call_psi(url, strategy, api_key)

            if data is not None:
                out_path = runs_dir / f"{label}_{strategy}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                lhr = data.get("lighthouseResult", {})
                score = lhr.get("categories", {}).get("performance", {}).get("score")
                score_str = f"{round(score * 100)}" if score is not None else "N/A"
                print(f"    Score perf : {score_str} — sauvegardé dans {out_path.name}")
            else:
                print(f"    Skippé (erreur API)")

            if done < total:
                time.sleep(2)

    print(f"\nAudit terminé. JSON bruts dans : {runs_dir}")
    print(f"Lancer le rapport : python scripts/report.py runs/{today}/")


if __name__ == "__main__":
    main()
