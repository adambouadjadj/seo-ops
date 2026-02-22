# CLAUDE.md — Workflow WebPerf Mensuel (AB Croisière)

## Objectif
Collecter les scores PageSpeed Insights (Desktop + Mobile) pour 9 URLs stratégiques,
les écrire dans le Google Sheets de suivi, et mettre à jour les tableaux + graphiques
du reporting Google Slides automatiquement.

---

## Prérequis (à faire une seule fois)

```bash
pip install gspread google-auth requests google-api-python-client
```

- Google Sheets partagé avec : `webperf-writer@deep-byte-488016-b6.iam.gserviceaccount.com` (Éditeur)
- Google Slides partagé avec : `webperf-writer@deep-byte-488016-b6.iam.gserviceaccount.com` (Éditeur)
- Clé API PSI dans `tools/.env` : `PSI_API_KEY=...`

---

## Usage mensuel (3 étapes)

```bash
# Étape 1 — PSI → Google Sheets (données brutes)
python tools/webperf_runner.py

# Étape 2 — Sheets → tableaux Google Slides
python tools/slides_updater.py

# Étape 3 — Graphiques Google Slides
# Ouvrir la présentation → bandeau "Refresh" en haut → cliquer "Refresh all"
```

Pour un mois spécifique (optionnel) :
```bash
python tools/webperf_runner.py 2026-03
python tools/slides_updater.py   # lit toujours le Sheets à jour
```

Les deux scripts sont **multi-mois** : ils détectent automatiquement la colonne
du mois cible en scannant les en-têtes du Sheets. Aucun mois n'est hardcodé.

---

## Ressources clés

| Ressource | ID / Lien |
|---|---|
| Google Sheets | `1D7IYLK2GQ77L8o-mXJzFzFqxgM0m7DLH0cxtw8khtn8` |
| Google Slides "Reporting Webperf ABCroisière" | `1O5uFDwyMXchEi4LiaRBaF6Tie9XpKZ_1v7sefQObZp4` |
| Service account | `webperf-writer@deep-byte-488016-b6.iam.gserviceaccount.com` |
| Projet GCP | `deep-byte-488016-b6` |

---

## Feuilles Sheets traitées automatiquement

| Feuille | URL testée |
|---|---|
| HP | https://www.abcroisiere.com/ |
| HP croisierenet | https://www.croisierenet.com/ |
| HP croisieres.fr | https://www.croisieres.fr/ |
| HP croisieres.com | https://www.croisieres.com/ |
| MSC | .../croisiere-msc-croisieres/compagnie,13/ |
| COSTA | .../croisiere-costa-croisieres/compagnie,7/ |
| SL | .../croisiere-mediterranee/destination,53,0/ |
| FP | .../croisiere-italie-malte-espagne-1553162.html |
| LP navire | .../costa-toscana/navire,1420/ |
| HP concurrent | Scores globaux des 4 sites (réutilisés, pas de nouveaux appels PSI) |

---

## Structure des feuilles Sheets (référence)

```
Row 1  : URL de la page
Row 3  : Header DSK  →  [vide, Reco, DSK, janv.-26, févr.-26, ..., févr.-27]
Row 4  : Score DSK       (0–100)
Row 5  : FCP (s) DSK
Row 6  : LCP (s) DSK
Row 7  : CLS DSK
Row 8  : FID (ms) DSK    ← déprécié, rempli avec 0
Row 9  : SI (s) DSK
Row 10 : TTI (s) DSK     ← déprécié, rempli avec 0
Row 11 : TBT (ms) DSK

Row 13 : Header MOB  →  même layout que DSK
Row 14 : Score MOB
...
Row 21 : TBT (ms) MOB
```

**Note FID/TTI** : ces métriques sont dépréciées. Les cellules doivent contenir `0`
(pas vide) pour éviter les bugs d'affichage des graphiques Google Sheets.

**Métriques PSI** : lab data (Lighthouse simulé), pas field data.
- Score : `categories.performance.score × 100`
- FCP/LCP/SI : `numericValue / 1000` → secondes
- CLS : `numericValue` → float 3 décimales
- TBT : `numericValue` → ms

---

## Structure Google Slides (référence)

Les tableaux de données sont sur ces slides (1-based) :

| Slide | Contenu |
|---|---|
| 13 / 15 | HP — DSK / MOB |
| 18 / 20 | HP concurrent — DSK / MOB |
| 22 / 24 | HP croisierenet — DSK / MOB |
| 26 / 28 | HP croisieres.fr — DSK / MOB |
| 30 / 32 | HP croisieres.com — DSK / MOB |
| 39 / 41 | MSC — DSK / MOB |
| 43 / 45 | COSTA — DSK / MOB |
| 48 / 50 | SL — DSK / MOB |
| 53 / 55 | FP — DSK / MOB |
| 58 / 60 | LP navire — DSK / MOB |

Les **graphiques** sont liés directement au Sheets — ils se rafraîchissent via
"Refresh all" dans Slides (pas besoin de script).

---

## Données manuelles (hors script)

| Feuille | Source | Action |
|---|---|---|
| URLS Statut DSK | GSC → Core Web Vitals | Saisie manuelle mensuelle |
| URLS Statut MOB | GSC → Core Web Vitals | Saisie manuelle mensuelle |

---

## Fin de période (dans ~12 mois)

Le Sheets contient des colonnes jusqu'à **févr.-27**. Quand cette limite approche :
1. Ajouter de nouvelles colonnes dans chaque feuille Sheets (continuer les mois)
2. Ajouter les nouvelles colonnes dans les tableaux Slides (continuer les en-têtes)
3. Les scripts détecteront automatiquement les nouvelles colonnes

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `colonne introuvable` | Mois absent du Sheets | Vérifier que la colonne du mois existe dans la ligne header (row 3) |
| `WorksheetNotFound` | Nom de feuille différent | Vérifier le nom exact dans le Sheets |
| `401 / permission denied` | Ressource non partagée | Partager Sheets + Slides avec le service account |
| `400 deleteText` | Cellule Slides vide | Bug déjà géré dans slides_updater.py |
| PSI `429` | Quota épuisé | Vérifier la clé API dans `tools/.env` |
| Graphiques pas mis à jour | Refresh non effectué | Ouvrir Slides → "Refresh all" |

---

## Fichiers clés

```
tools/
  webperf_runner.py         ← Étape 1 : PSI → Sheets
  slides_updater.py         ← Étape 2 : Sheets → tableaux Slides
  .env                      ← PSI_API_KEY (GITIGNORE)
  credentials/
    service_account.json    ← credentials Google (GITIGNORE)
```
