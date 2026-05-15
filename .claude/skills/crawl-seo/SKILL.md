---
name: crawl-seo
description: Lance un crawl Screaming Frog CLI et génère le rapport de santé SEO. Utiliser quand l'utilisateur veut crawler un site, lancer Screaming Frog, analyser des erreurs 4xx/5xx, auditer les balises title/H1, vérifier la profondeur de crawl ou générer un rapport SEO technique.
---

# Workflow Crawl SEO (Screaming Frog CLI)

## Objectif
Lancer un crawl headless Screaming Frog, exporter les CSVs clés, générer un rapport de santé SEO structuré.

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
  {SLUG}_{DD-MM-YY}/           ← CSVs bruts Screaming Frog
    interne_tous.csv
    codes_de_réponse_tous.csv
    title_des_pages_tous.csv
    h1_tous.csv
    images_tous.csv
    liens_entrants_tous.csv
  crawl_{SLUG}_{DD-MM-YY}.md   ← rapport structuré
  crawl_{SLUG}_{DD-MM-YY}.html ← version HTML (ouvrir navigateur → Ctrl+A → Outlook)
```

## Sections du rapport
1. Résumé global (pages crawlées, statuts HTTP, indexabilité)
2. Erreurs & redirections HTTP (4xx, 5xx, 3xx avec destinations)
3. Balises Title (manquants, dupliqués, trop longs >60 car, trop courts <30 car)
4. Balises H1 (manquants, dupliqués, multiples H1)
5. Pages sans inlinks internes (orphelines)
6. Meta descriptions (manquantes, dupliquées, hors longueur)
7. Canoniques (pages sans canonical, canoniques non auto-référencés)
8. Profondeur de crawl (distribution par niveau, pages > profondeur 5)
9. Pages lentes (> 2000 ms)
10. Quasi-doublons de contenu
11. Images sans attribut alt
12. Liens internes brisés (inlinks vers pages 4xx/5xx)

## SF CLI
- Exécutable : `C:\Program Files (x86)\Screaming Frog SEO Spider\ScreamingFrogSEOSpiderCli.exe`
- Licence payante requise (crawl illimité — limite 500 URLs en mode gratuit)
- Mode headless : pas d'interface graphique, SF quitte quand le crawl est terminé
- Le script Python génère automatiquement le .md et le .html après le crawl

## Dépendances
```bash
pip install pandas
```

## Via la webapp
Le crawl peut aussi être lancé depuis `/crawl` dans la webapp Flask.
Le job tourne en arrière-plan (threading) et le rapport est accessible dans la liste des crawls passés.
