---
name: backlink-gap
description: Analyse de gap backlinks via Babbar API. Utiliser quand l'utilisateur veut identifier des opportunités de netlinking, comparer les backlinks avec les concurrents, faire de l'outreach, analyser les domaines référents manquants, vérifier la qualité des domaines (spam, langue, statut HTTP), ou préparer une liste d'outreach.
---

# Workflow Backlink Gap (Babbar API)

## Objectif
Identifier les domaines qui linkent les concurrents mais pas le site cible, prioriser par BAS Babbar, puis vérifier la qualité des domaines avant outreach.

## Étapes du workflow

### Étape 1 — Analyse du gap
### Étape 2 — Vérification qualité (optionnelle, recommandée avant outreach)

---

## ÉTAPE 1 — Analyse du gap

### Collecte des paramètres

Si l'utilisateur ne précise pas tous les paramètres, demander :
1. **Domaine cible** — ex: `www.abcroisiere.com`
2. **Concurrents principaux** — liste de domaines (groupe 1, outreach direct)
3. **Groupe secondaire** (optionnel) — ex: armateurs, grandes marques (vue stratégique uniquement)
4. **Enrichissement BAS** — recommander `--enrich` par défaut (ajoute ~30-60 min mais améliore la priorisation)

### Commandes

```bash
# AB Croisière — concurrents hardcodés, mode standard
python tools/backlink_gap.py --enrich

# AB Croisière — avec armateurs
python tools/backlink_gap.py --include-armateurs --enrich

# Autre site — concurrents fournis en paramètre
python tools/backlink_gap.py \
  --url www.promocroisiere.com \
  --competitors "croisierenet:www.croisierenet.com,croisieres.fr:www.croisieres.fr,okcroisiere:www.okcroisiere.fr" \
  --enrich

# Avec groupe secondaire
python tools/backlink_gap.py \
  --url www.promocroisiere.com \
  --competitors "croisierenet:www.croisierenet.com,croisieres.fr:www.croisieres.fr" \
  --groups "msc:www.msccroisieres.fr,costa:www.costacroisieres.fr" \
  --enrich
```

### Format `--competitors` et `--groups`

`"label:domain,label:domain"` — le label apparaît dans la colonne "Linkent" du Excel.
Si pas de label : `"www.croisierenet.com,www.croisieres.fr"` (label = domaine sans www).

### Output

```
output/backlinks/
  backlink_gap_{site}_{DD-MM-YY}.xlsx            ← Excel priorisé
  backlink_gap_{site}_{DD-MM-YY}.csv             ← CSV gap comparateurs
  backlink_gap_{site}_{DD-MM-YY}_enriched.xlsx   ← si --enrich (recommandé)
```

### Structure Excel
- **Sheet 1 — Gap Comparateurs** : opportunités actionnables, triées par nb concurrents puis BAS
- **Sheet 2 — Gap Groupe 2** : vue large (si --groups ou --include-armateurs)
- **Sheet 3 — Stats** : nb domaines référents trouvés par site

### Colonnes
| Colonne | Description |
|---|---|
| Domaine référent | Le host qui ne linke pas encore le site cible |
| BAS | Babbar Authority Score (0-100) |
| Nb concurrents | Combien de concurrents ce domaine linke |
| Linkent | Quels concurrents |
| Ancres observées | Textes d'ancre extraits |
| Priorité outreach | HAUTE / MOYENNE / BASSE |
| Catégorie | Thématique Babbar (après enrichissement) |

### Logique de priorité
- **HAUTE** : BAS ≥ 30 ET linke ≥ 2 concurrents
- **MOYENNE** : BAS ≥ 15 OU linke ≥ 2 concurrents
- **BASSE** : BAS < 15 ET linke 1 seul concurrent

### Pourquoi séparer comparateurs et groupe secondaire
Les domaines qui linkent des grandes marques (armateurs, institutionnels) le font souvent
pour des raisons non transférables à un comparateur (partenariats B2B, presse corporate).
Les inclure dans le groupe principal gonflerait la liste avec des opportunités inatteignables.
Utiliser `--groups` uniquement pour la vue stratégique.

### Concurrents AB Croisière (hardcodés par défaut)
```
Comparateurs : croisierenet.com, croisieres.fr, croisieres.com,
               destockagecroisieres.fr, okcroisiere.fr, croisiland.com
Armateurs    : msccroisieres.fr, costacroisieres.fr, croisieurope.com
```

### Temps d'exécution estimé
- Mode standard (6 concurrents) : ~15-30 min selon volume
- Avec groupe secondaire : +10-15 min
- Enrichissement BAS (`--enrich`) : +30-60 min selon nb domaines à BAS=0
- Rate limit Babbar géré automatiquement (pause 62s si 429)

---

## ÉTAPE 2 — Vérification qualité avant outreach

À lancer après l'étape 1, sur les domaines HAUTE priorité (ou HAUTE + MOYENNE).
Vérifie automatiquement : statut HTTP, langue, signaux spam.

### Commandes

```bash
# Vérifier les HAUTE priorité (défaut) — prend le dernier fichier _enriched.xlsx
python tools/backlink_check.py

# Vérifier HAUTE + MOYENNE
python tools/backlink_check.py --priority HAUTE MOYENNE

# Sur un fichier spécifique
python tools/backlink_check.py --input output/backlinks/mon_fichier_enriched.xlsx
```

### Ce que le script vérifie

| Check | Comment |
|---|---|
| **Statut HTTP** | GET homepage → actif / mort / redirige / 503 (bot-bloqué) |
| **Langue** | html lang= + heuristique mots FR/EN |
| **Spam score 0-3** | Mots suspects dans title/H1, nb liens externes > 80, mots spam dans le body |

**Spam keywords détectés :** casino, poker, slot, betting, viagra, pharmacy, forex, crypto, bitcoin, escort, payday loan, replica, buy links...

**Note sur les HTTP 503/403 :** ce sont souvent des gros médias (parismatch, etc.) qui bloquent les bots. Ne pas les éliminer — vérifier manuellement. Ils comptent comme "non-actifs" dans le script mais sont probablement exploitables.

### Output

```
output/backlinks/
  backlink_check_{priorite}_{DD-MM-YY}.xlsx
    Sheet "Verification" — tous les domaines avec statut, langue, spam score, title, H1
    Sheet "Recap"        — synthèse chiffrée + nb domaines recommandés outreach
```

### Colonnes du rapport
| Colonne | Description |
|---|---|
| Statut | actif / mort / redirige / HTTP 503... |
| Code HTTP | code retourné |
| URL finale | URL après redirections |
| Langue | fr / en / autre |
| Title homepage | titre de la page d'accueil |
| H1 | premier H1 |
| Liens ext. | nb de liens externes sur la homepage |
| Spam score | 0 = clean, 1 = attention, 2-3 = suspect |
| Spam flags | détail des signaux détectés |

### Interprétation des résultats
- **Actif + FR + spam 0** → à contacter directement
- **503/403 + FR** → vérifier manuellement (probablement actif)
- **Spam score 1** → regarder le title/flags, souvent un faux positif
- **Spam score 2-3** → éliminer (expired domain hijack probable)
- **Mort** → exclure

### Temps d'exécution
~1-2 min pour 91 domaines (pause 1s entre chaque).

---

## Dépendances
```bash
pip install openpyxl
```
