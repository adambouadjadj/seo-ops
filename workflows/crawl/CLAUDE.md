# Workflow 3 — Crawl SEO (Screaming Frog CLI)

## Objectif
Lancer un crawl headless SF, exporter les CSVs clés, générer un rapport de santé SEO structuré.

## Commande

```bash
# Crawl abcroisiere.com (défaut)
python tools/sf_crawler.py

# Autre site ou URL spécifique
python tools/sf_crawler.py --url https://www.promocroisiere.com
python tools/sf_crawler.py --url https://www.abcroisiere.com/croisiere-mediterranee/
```

Un seul crawl à la fois. `--url` remplace le défaut, n'additionne pas.

## Outputs

```
output/crawl_reports/
  ABCROISIERE_DD-MM-YY/        ← CSVs bruts SF
    internal_all.csv
    response_codes_all.csv
    page_titles_all.csv
    h1_all.csv
    all_inlinks.csv
  crawl_ABCROISIERE_DD-MM-YY.md    ← rapport structuré
  crawl_ABCROISIERE_DD-MM-YY.html  ← version HTML (ouvrir navigateur → Ctrl+A → Outlook)
```

## Sections du rapport
1. Résumé global (pages crawlées, statuts, indexabilité)
2. Erreurs & redirections HTTP (4xx, 5xx, 3xx)
3. Balises Title (manquants, dupliqués, trop longs >60, trop courts <30)
4. Balises H1 (manquants, dupliqués, multiples)
5. Pages sans inlinks internes (orphelines)

## SF CLI
- Exécutable : `C:\Program Files (x86)\Screaming Frog SEO Spider\ScreamingFrogSEOSpiderCli.exe`
- Licence payante requise (crawl illimité)
- Mode headless : pas d'interface graphique, SF quitte quand le crawl est terminé

## Dépendances
```bash
pip install pandas
```
