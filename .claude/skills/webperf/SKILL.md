---
name: webperf
description: Workflow WebPerf mensuel AB Croisière. Utiliser quand l'utilisateur parle de PageSpeed Insights, scores performance, Core Web Vitals, PSI, LCP/CLS/TBT, Slides WebPerf, recap mensuel performance, ou mail WebPerf.
---

# Workflow WebPerf Mensuel (AB Croisière)

## Objectif
Collecter les scores PageSpeed Insights, les écrire dans le Sheets, mettre à jour les Slides,
générer un recap comparatif, investiguer les alertes via MCP, puis produire le mail mensuel.

---

## Prérequis (à faire une seule fois)

```bash
pip install gspread google-auth requests google-api-python-client
```

- Google Sheets partagé avec : `webperf-writer@deep-byte-488016-b6.iam.gserviceaccount.com` (Éditeur)
- Google Slides partagé avec : `webperf-writer@deep-byte-488016-b6.iam.gserviceaccount.com` (Éditeur)
- Clé API PSI dans `tools/.env` : `PSI_API_KEY=...`

---

## Flow mensuel complet (7 étapes)

### Étapes 1–4 : données (via webapp /webperf ou CLI)

```bash
python tools/webperf_runner.py [2026-03]   # Étape 1 : PSI → Sheets
python tools/slides_updater.py             # Étape 2 : Sheets → tableaux Slides
# Étape 3 : Ouvrir Slides → "Refresh all" (graphiques liés) — MANUEL
python tools/webperf_recap.py [2026-03]   # Étape 4 : Sheets → recap MD N vs N-1
# Output : output/webperf/YYYY-MM/recap_MM-YYYY.md
```

### Étape 5 : Investigation MCP

L'utilisateur partage le recap MD. Lire la **section 2 (Alertes)** et **section 5 (Pages à investiguer)**.

Pour chaque page flaggée, lancer via MCP Chrome DevTools :
1. `lighthouse_audit` → score détaillé, opportunités prioritaires, élément LCP identifié
2. `performance_start_trace` → charger la page → `performance_stop_trace` → `performance_analyze_insight`
   → identifier : quel élément déclenche le LCP, quels scripts bloquent le TBT, cause du CLS
3. `list_network_requests` si besoin → ressources lourdes (images non optimisées, JS tiers, etc.)

Produire un **tableau de diagnostic** :

| Page | Device | Problème | Cause identifiée | Recommandation |
|---|---|---|---|---|
| HP | DSK | CLS 0,152 | Bannière chargée async au-dessus du fold | Réserver l'espace via CSS min-height |
| HP | MOB | TBT 394ms | Script analytics bloquant au rendu | Différer en `defer` ou `async` |

### Étape 6 : Tickets Jira

L'utilisateur crée les tickets depuis le tableau de diagnostic (ou via Claude Desktop).
Récupérer les refs tickets (ex : `SEO-142`) pour les intégrer dans le mail.

### Étape 7 : Mail final HTML

L'utilisateur fournit :
- Le recap MD (contient déjà les données GSC CWV section 0 + scores PSI)
- Les refs tickets Jira (si alertes)

Générer le mail HTML Outlook-ready selon la structure ci-dessous.

---

## Structure du mail final

### Contraintes HTML
- CSS inline uniquement (pas de bloc `<style>`)
- Mise en page via `<table>` (pas de flexbox/grid)
- Largeur max 660px, police Arial/Helvetica
- Couleurs : vert `#27ae60`, orange `#e67e22`, rouge `#c0392b`, bleu `#1a3a5c`
- En-tête bleue, badges scores colorés, encarts contextuels en bas de section
- Pas de doubles tirets `--` comme séparateurs

### Sections du mail

**Header** : "Reporting WebPerf — Mois YYYY" · AB Croisière | abcroisiere.com · Date MAJ

**Intro** : 2-3 phrases sur les signaux forts du mois (tendance générale, point critique, point positif).

**Section 1 — GSC Core Web Vitals** *(données fournies manuellement)*
Tableau 4 lignes : Desktop N-1 / Desktop N / Mobile N-1 / Mobile N.
Colonnes : URLs lentes · URLs à améliorer · URLs rapides.
Note contextuelle sous le tableau.

**Section 2 — Homepage AB Croisière**
- Si alerte (score drop ≥ 5pts ou métrique hors seuil) : tableau métriques complet DSK + MOB (Score, FCP, LCP, CLS, TBT) avec encart cause identifiée + ref ticket si dispo.
- Si pas d'alerte : ligne dans le tableau condensé section 3 uniquement.

**Section 3 — Pages internes** *(tableau condensé — scores uniquement)*
Colonnes : Page | DSK N-1 | DSK N | MOB N-1 | MOB N.
Badges colorés (vert ≥90, orange 50-89, rouge <50). Delta en couleur (+/-).
Note contextuelle sous le tableau.
Inclure HP si pas d'alerte. Exclure les pages qui ont déjà un tableau détaillé section 2.

**Section 4 — Analyse concurrentielle**
Tableau scores HP : abcroisiere.com (ligne mise en avant `#f0f5ff`) + 3 concurrents.
Colonnes : Site | DSK N-1 | DSK N | MOB N-1 | MOB N.
Note de positionnement concurrentiel.

**Section 5 — Points d'attention & tickets** *(conditionnel)*
- Si alertes : liste numérotée. Pour chaque point : cause identifiée (issue MCP), action en cours, ref ticket Jira, timeline si connue. Couleur du numéro selon criticité (rouge = critique, orange = vigilance, vert = positif).
- Si pas d'alertes : titre "Bilan du mois", liste des progressions notables uniquement.

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

**Note FID/TTI** : dépréciés. Les cellules doivent contenir `0` (pas vide) pour éviter les bugs graphiques.

**Métriques PSI** : lab data (Lighthouse simulé), pas field data.
- Score : `categories.performance.score × 100`
- FCP/LCP/SI : `numericValue / 1000` → secondes
- CLS : `numericValue` → float 3 décimales
- TBT : `numericValue` → ms

---

## Données manuelles (hors script)

| Données | Source | Quand |
|---|---|---|
| URLS Statut DSK/MOB (Sheets) | GSC → Core Web Vitals | Saisie mensuelle dans Sheets **avant** de lancer webperf_runner.py |

`webperf_recap.py` lit ces feuilles automatiquement et les inclut en section 0 du recap MD.

---

## Structure Google Slides (référence)

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

---

## Fin de période (dans ~12 mois)

Le Sheets contient des colonnes jusqu'à **févr.-27**. Quand cette limite approche :
1. Ajouter de nouvelles colonnes dans chaque feuille Sheets
2. Ajouter les nouvelles colonnes dans les tableaux Slides
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
  webperf_recap.py          ← Étape 4 : Sheets → recap MD comparatif N vs N-1
  .env                      ← PSI_API_KEY (GITIGNORE)
  credentials/
    service_account.json    ← credentials Google (GITIGNORE)
output/webperf/YYYY-MM/
  recap_MM-YYYY.md          ← recap généré par webperf_recap.py
  webperf_AB_DD-MM-YY_email.html  ← mail final généré à l'étape 7
```
