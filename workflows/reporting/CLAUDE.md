# CLAUDE.md — Workflow Reporting SEO Hebdomadaire (AB Croisière)

## Objectif
Générer un mail de reporting SEO hebdomadaire prêt à envoyer pour AB Croisière.

## Langue & ton
- Français professionnel, clair, synthétique, orienté actions.
- Pas de jargon inutile.

## Inputs attendus
| Fichier | Chemin | Nommage |
|---|---|---|
| Monitorank | `inputs/Suivi positionnement AB DD-MM-YY.xlsx` | Ex : `Suivi positionnement AB 19-02-26.xlsx` |
| GSC | `inputs/GSC performance AB DD-MM-YY.xlsx` | Ex : `GSC performance AB 19-02-26.xlsx` |
| Actions | `tasks/task_DD_MM_YY.txt` | Un ou plusieurs fichiers |

## Output attendu
Mail structuré en 5 parties :
1. Contexte & état du trafic (synthèse macro GSC)
2. Progressions notables — Monitorank (Top gains)
3. Requêtes en baisse — Monitorank (Top baisses)
4. Actions réalisées (agrégées depuis `tasks/`)
5. Actions prévues semaine prochaine

---

## MODULE 1 — Monitorank (positionnement desktop)

### Structure du fichier Excel
| Élément | Valeur |
|---|---|
| Onglet | Index 0 — `Top MOC AB - Desktop` |
| Header | `pd.read_excel(..., header=1)` (Excel row 2) |
| 1ère ligne post-header | Sous-header "2026 / Pos / Pos…" → `df = df.iloc[1:]` |
| Col 0 | Mot-clé (`"Top Mots Clés "`) |
| Col 1 | Volume mensuel (`"Volume recherche"`) |
| Cols 2+ | Positions hebdomadaires (objets datetime) |
| Valeurs positions | Coercer : `pd.to_numeric(..., errors='coerce')` |

### Sélection des semaines
- **N** = dernière colonne avec données (la plus à droite avec `notna().sum() > 0`)
- **N-1** = colonne immédiatement précédente
- Si l'une des deux est vide → interrompre et demander un nouvel export.

### Nettoyage des lignes
Ignorer toute ligne où le mot-clé est vide/NaN **ou** commence par `"Moyenne"`.
Ne pas filtrer sur volume = 0.

### Dédoublonnage
Normaliser chaque mot-clé (minuscules + suppression accents) → conserver la première occurrence, ignorer les suivantes.

### Calcul de la variation
`variation = position_N − position_N-1`
- Négatif → amélioration (la page monte)
- Positif → dégradation (la page descend)

### Affichage dans le mail (inversé pour lisibilité métier)
Le signe affiché est l'opposé du calcul interne :
- Gain (variation < 0) → afficher **+X positions** (ex : variation = -2 → "+2 positions — entrée Top 3 ✅")
- Baisse (variation > 0) → afficher **-X positions** (ex : variation = +6 → "-6 positions — sortie Top 10 🔴")

Appliquer cette règle d'affichage à toutes les sections Monitorank (gains + baisses).

### Critères de sélection (4–5 gains, 4–5 baisses)

**Gains notables** (au moins un critère) :
- variation ≤ −3
- OU entrée Top 3 (N-1 > 3 et N ≤ 3)
- OU entrée Top 10 (N-1 > 10 et N ≤ 10)
- OU mot-clé stratégique (toute variation)

**Baisses notables** (au moins un critère) :
- variation ≥ +3
- OU sortie Top 3 (N-1 ≤ 3 et N > 3)
- OU sortie Top 10 (N-1 ≤ 10 et N > 10)
- OU mot-clé stratégique impacté

**Priorisation** : volume élevé > thématique business (MSC, Costa, Méditerranée, Antilles, Caraïbes) > amplitude de variation.

---

## MODULE 2 — GSC (performance trafic)

### Structure du fichier Excel
| Élément | Valeur |
|---|---|
| Onglets | `Queries` (1 500+ lignes) et `Pages` (1 300+ lignes) |
| Header | Row 0 → `pd.read_excel(..., header=0)` |
| Colonnes (9) | `Top queries/pages`, `Last 7 days Clicks`, `Previous 7 days Clicks`, `Last 7 days Impressions`, `Previous 7 days Impressions`, `Last 7 days CTR`, `Previous 7 days CTR`, `Last 7 days Position`, `Previous 7 days Position` |

**Aucune colonne "Différence" dans le fichier.** Calculer les deltas :
```
delta_clicks      = Last 7 days Clicks      − Previous 7 days Clicks
delta_impressions = Last 7 days Impressions − Previous 7 days Impressions
delta_ctr         = Last 7 days CTR         − Previous 7 days CTR
delta_position    = Last 7 days Position    − Previous 7 days Position
```
Convention position : `delta_position > 0` = rang qui empire ; `< 0` = rang qui s'améliore.

### Filtres avant analyse (réduction du bruit)
- **Onglet Queries** : garder uniquement les lignes avec `Last 7 days Impressions ≥ 200`
- **Onglet Pages** : garder uniquement les lignes avec `Last 7 days Clicks ≥ 20` OU `Previous 7 days Clicks ≥ 20`

### Sections à produire

#### 1. Synthèse macro (section 1 du mail)
Calculer sur **toutes les lignes** de l'onglet Pages (sans filtre — vision site-wide) :
- Σ clicks N vs Σ clicks N-1 → évolution %
- Σ impressions N vs Σ impressions N-1 → évolution %

Générer 1–2 phrases d'insight (ex : impressions en hausse mais CTR en baisse → enjeu snippet/title).

#### 2. Pages stratégiques en baisse (2–3)
Onglet **Pages**, filtré. Sélectionner 2–3 pages avec `delta_clicks` le plus négatif, en priorisant les pages business (compagnies, destinations, mini-croisière, dernière minute).
Pour chacune : URL raccourcie, Δ clicks, Δ impressions, Δ position, hypothèse courte.

#### 3. Opportunités Quick Wins (2–3)
Onglet **Queries**, filtré. Critères (au moins un) :
- `Last 7 days Position` entre 4 et 10 ET `Last 7 days Impressions ≥ 500` ET `Last 7 days CTR < 0.05`
- OU `delta_impressions > 0` ET `delta_clicks ≤ 0`

Pour chacune : requête, position actuelle, impressions, reco actionnable (title / meta / contenu / maillage).

---

## Sauvegarde de l'output
Une fois le mail généré, produire deux fichiers dans `output/reporting/` (même date que les fichiers inputs) :
- `output/reporting/reporting_AB_DD-MM-YY.md` — version Markdown (source, archivage)
- `output/reporting/reporting_AB_DD-MM-YY_email.html` — version HTML Outlook-ready (à ouvrir dans un navigateur, puis Ctrl+A / Ctrl+C / coller dans Outlook)

Contraintes HTML email :
- CSS inline uniquement (pas de bloc `<style>`)
- Mise en page via `<table>` (pas de flexbox/grid)
- Largeur max 640px, police Arial/Helvetica
- Gains en vert (#27ae60), baisses en rouge (#c0392b), CTR faible en orange (#e67e22)
- Pas de footer "Reporting généré automatiquement" ou mention similaire
- Pas de doubles tirets `--` comme séparateurs (trop IA) : utiliser `:` ou reformuler

## Règle générale
Si une information est manquante ou incohérente, l'indiquer clairement dans le mail plutôt que de l'omettre.
