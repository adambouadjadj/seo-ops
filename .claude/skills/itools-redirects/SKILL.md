# /itools-redirects — Import de redirections dans iTools (Karavel)

## Ce que fait ce skill

Automatise l'import en masse de redirections 301 et 410 dans iTools Karavel via Playwright Chromium.

Modes d'exécution :
- `dry-run` : affiche ce qui serait traité, sans ouvrir le navigateur
- `test` : exécution réelle sur les 5 premières lignes uniquement
- `run` : exécution complète sur tout le CSV
- `resume` : reprend depuis un log existant, skip les lignes déjà traitées

---

## Usage

```
python scripts/itools_redirects.py --file <CSV> --mode <dry-run|test|run|resume> [--log <log_csv>] [--limit N]
```

### Flags

| Flag | Requis | Description |
|---|---|---|
| `--file` | Oui | Chemin du CSV source (301 ou 410) |
| `--mode` | Oui | `dry-run` / `test` (5 lignes) / `run` (tout) / `resume` (reprendre depuis log) |
| `--log` | Non (requis pour resume) | Log CSV existant pour `--mode resume` |
| `--limit N` | Non | Limite à N lignes (ex: `--limit 20` pour un test intermédiaire) |

### Exemples

```bash
# Vérifier le CSV sans rien faire
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode dry-run

# Test sur 5 lignes (navigateur visible)
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode test

# Lancement complet
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode run

# Lancement limité (test intermédiaire, ex: 20 lignes)
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode run --limit 20

# Import des 410
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_410.dedup.csv --mode run

# Reprise après interruption
python scripts/itools_redirects.py --file scripts/mapping_pages_bateau_301.csv --mode resume --log scripts/logs/itools_2026-05-06_120000.csv
```

---

## Format CSV attendu

### 301 (source → cible)

| Colonne | Description |
|---|---|
| `URL actuelle (404)` | URL source (complète ou path) |
| `Action` | `301` |
| `URL cible (200)` | URL cible (complète ou path) |
| Autres colonnes | Ignorées (Nom bateau, Navire ID…) |

### 410 (suppression définitive)

| Colonne | Description |
|---|---|
| `URL actuelle (404)` | URL source (complète ou path) |
| `Action` | `410` |
| Autres colonnes | Ignorées (Nom bateau, Navire ID…) |

Les URLs complètes (`https://www.abcroisiere.com/fr/...`) sont automatiquement converties en path (`/fr/...`).

### Types de redirections

`Code Http` est un champ texte libre dans iTools. 301 et 410 couvrent 100% des besoins SEO courants. Le script accepte techniquement n'importe quel code HTTP (302, 307, etc.) sans modification — il suffit que la valeur soit dans la colonne `Action` du CSV.

---

## Credentials

Dans `tools/.env` :

```
ITOOLS_URL=http://webint.ws.in.karavel.com:10670/seo.admin.webapp/redirects
ITOOLS_USER=xxx
ITOOLS_PASSWORD=xxx
```

---

## Valeurs fixes (hardcodées)

| Champ | Valeur |
|---|---|
| Site Artefact | `abcroisiereCom` |
| Domaine | `www.abcroisiere.com` |
| Status | `ACTIVE` |
| Url Cible | vide pour les 410 |

---

## Fichiers

```
scripts/
├── itools_redirects.py          ← script principal
├── mapping_pages_bateau_301.csv ← CSV source 301 (gitignored)
├── mapping_pages_bateau_410.dedup.csv ← CSV source 410 (gitignored)
└── logs/
    ├── itools_YYYY-MM-DD_HHMMSS.csv   ← log par run (gitignored)
    └── screenshots/
        └── failed_NNN_path.png         ← screenshot auto sur erreur
```

---

## Log CSV

Chaque run produit un log dans `scripts/logs/itools_YYYY-MM-DD_HHMMSS.csv` :

| Colonne | Valeurs |
|---|---|
| `line` | Numéro de ligne dans le CSV source |
| `action` | `301` ou `410` |
| `source` | Path source |
| `target` | Path cible (vide pour 410) |
| `result` | `created` / `already_exists` / `failed` |
| `message` | Détail (message iTools, "form reset", erreur…) |
| `timestamp` | ISO 8601 |

---

## Détection du résultat

Après chaque Save, le script inspecte la page dans cet ordre :

1. **`vaadin-notification-container`** (toast Vaadin) :
   - "already" / "déjà" / "existe" / "duplicate" → `already_exists`
   - "error" / "erreur" / "invalid" / "failed" → `failed`
   - Autre texte non vide → `created`
2. **`vaadin-dialog-overlay`** (dialog d'erreur Vaadin) :
   - Même logique que le toast
3. **Reset du champ Url Source** (vide = formulaire réinitialisé après Save réussi) → `created`
4. **Fallback** → `created` avec message "no error detected"

En cas de `failed` : screenshot automatique dans `scripts/logs/screenshots/`.

---

## Mode resume

Pour reprendre après une interruption :

```bash
python scripts/itools_redirects.py \
  --file scripts/mapping_pages_bateau_301.csv \
  --mode resume \
  --log scripts/logs/itools_2026-05-06_120000.csv
```

Le script lit le log existant, considère comme traitées les lignes avec `result` = `created` ou `already_exists`, et reprend à partir de la première ligne non traitée. **Le log existant est complété** (pas écrasé).

---

## Notes techniques (Vaadin web components)

iTools est une application **Vaadin Flow** — les composants sont des web components avec shadow DOM. Les sélecteurs Playwright standards (`get_by_label`, `locator('label:has-text(...)')`, `td:has-text(...)`) ne fonctionnent pas.

### Sélecteurs qui fonctionnent

**Champs texte** :
```python
page.locator('vaadin-form-item:has(label:text-is("Url Source"))').last.locator('input[slot="input"]').fill(value)
```

**Dropdowns (vaadin-select)** — ouvrir via JS puis cliquer par attribut `label=` :
```python
# Ouvre le dropdown
page.evaluate(f"""() => {{
    const items = [...document.querySelectorAll('vaadin-form-item')].reverse();
    const fi = items.find(fi => [...fi.querySelectorAll('label')].some(l => l.textContent.trim() === '{label}'));
    if (fi) fi.querySelector('vaadin-select-value-button')?.click();
}}""")
page.wait_for_timeout(400)
# Clique l'item — le texte est dans le shadow-root, pas dans textContent → utiliser label=
page.evaluate(f'document.querySelector(\'vaadin-select-item[label="{value}"]\')?.click()')
```

**Pourquoi `label=` et pas `textContent`** : le texte affiché dans `vaadin-select-item` est rendu dans le `#shadow-root`, inaccessible via `querySelector` classique ou `textContent`. L'attribut `label=` sur l'élément hôte contient le texte visible.

**`.last` est une propriété, pas une méthode** — écrire `.last.locator(...)` et non `.last().locator(...)`.

---

## Workflow recommandé

1. Placer les CSV dans `scripts/`
2. Vérifier avec `--mode dry-run`
3. Tester avec `--mode test` (5 lignes, navigateur visible)
4. Valider les 5 lignes dans iTools
5. Optionnel : `--mode run --limit 20` pour un test à plus grande échelle
6. Lancer `--mode run` pour le batch complet
7. En cas d'interruption : `--mode resume --log scripts/logs/<dernier_log>.csv`

---

## Prérequis

```bash
pip install playwright python-dotenv
playwright install chromium
```

> **Note Windows N** : Firefox Playwright ne fonctionne pas sur Windows N (Media Foundation manquant). Utiliser Chromium uniquement.
