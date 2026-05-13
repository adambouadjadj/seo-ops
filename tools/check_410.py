"""
check_410.py — Recette redirections 410
Tire un échantillon aléatoire du fichier Babbar et vérifie que chaque URL répond 410.
Usage : python tools/check_410.py [--sample 50]
"""

import argparse
import random
import sys
import openpyxl
import requests

XLSX = r"C:\Users\abouadjadj\Downloads\babbar_4xx_abcroisiere.com_20260225_1644 (3).xlsx"

def load_urls(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    urls = [row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]]
    wb.close()
    return urls

RECETTE_HOST = "p5-www.abcroisiere.com"

def to_recette(url):
    return url.replace("www.abcroisiere.com", RECETTE_HOST, 1)

def check_url(url, session):
    recette_url = to_recette(url)
    try:
        r = session.head(recette_url, allow_redirects=True, timeout=10)
        return r.status_code
    except requests.exceptions.ConnectionError:
        return "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=50, help="Nombre d'URLs à tester (défaut: 50)")
    args = parser.parse_args()

    print(f"Chargement du fichier...")
    urls = load_urls(XLSX)
    print(f"{len(urls):,} URLs chargées.")

    sample = random.sample(urls, min(args.sample, len(urls)))
    print(f"Echantillon : {len(sample)} URLs\n")

    results = {"410": [], "other": []}

    with requests.Session() as session:
        for i, url in enumerate(sample, 1):
            code = check_url(url, session)
            status = "OK" if code == 410 else "KO"
            bucket = "410" if code == 410 else "other"
            results[bucket].append((url, code))
            print(f"[{i:>3}/{len(sample)}] {status} {code}  {to_recette(url)}")

    total = len(sample)
    ok = len(results["410"])
    ko = len(results["other"])

    print(f"\n{'='*60}")
    print(f"RESULTATS : {ok}/{total} URLs en 410  ({ok/total*100:.0f}%)")

    if results["other"]:
        print(f"\nURLs KO ({ko}) :")
        for url, code in results["other"]:
            print(f"  {code}  {to_recette(url)}")
    else:
        print("Tout est bon, toutes les URLs repondent 410.")

if __name__ == "__main__":
    main()
