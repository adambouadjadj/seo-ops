# SEO Ops

Boîte à outils SEO locale pour AB Croisière. Trois workflows automatisés :

| Outil | Fréquence | Description |
|---|---|---|
| **Task Manager** (web app) | Quotidien | Suivi des tâches SEO de la semaine, export vers le reporting |
| **Reporting hebdomadaire** | Vendredi | Génère le mail de reporting depuis Monitorank + GSC via Claude |
| **WebPerf mensuel** | 1x/mois | PSI → Google Sheets → Google Slides automatisé |

---

## 1. Task Manager (Flask web app)

### Installation

```bash
git clone https://github.com/zhanpyu/seo-ops.git
cd seo-ops

python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

cp .env.example .env         # puis éditer .env
python run.py
```

Ouvrir [http://localhost:5000](http://localhost:5000)

### `.env` requis

```bash
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:///seo_ops.db
FLASK_ENV=development
```

### Workflow hebdomadaire

1. **Lundi** — cliquer **⟳ Récurrentes** pour générer les 8 tâches récurrentes
2. **Au fil de la semaine** — ajouter les tâches, mettre à jour les statuts
3. **Vendredi** — cliquer **↓ Exporter .txt** → fichier `tasks/task_DD_MM_YY.txt` prêt pour le reporting

### Stack

- Flask 3.x + SQLAlchemy (SQLite local → PostgreSQL-ready via `DATABASE_URL`)
- HTMX + Jinja2 + CSS vanilla dark theme
- Flask-WTF (CSRF)

---

## 2. Reporting SEO hebdomadaire

Génère un mail de reporting structuré (Monitorank positions + GSC trafic + actions de la semaine).

### Inputs à préparer

| Fichier | Chemin |
|---|---|
| Export Monitorank | `inputs/Suivi positionnement AB DD-MM-YY.xlsx` |
| Export GSC | `inputs/GSC performance AB DD-MM-YY.xlsx` |
| Tâches de la semaine | `tasks/task_DD_MM_YY.txt` (généré par le Task Manager) |

### Usage

Ouvrir Claude (claude.ai ou Claude Code) dans le dossier `seo-ops/` avec le `workflows/reporting/CLAUDE.md` chargé, fournir les 3 fichiers inputs.

### Output

- `output/reporting_AB_DD-MM-YY.md` — version Markdown (archivage)
- `output/reporting_AB_DD-MM-YY_email.html` — HTML Outlook-ready (ouvrir dans navigateur → Ctrl+A → coller dans Outlook)

---

## 3. WebPerf mensuel

Collecte les scores PageSpeed Insights pour 9 URLs stratégiques et met à jour le Google Slides de reporting automatiquement.

### Prérequis (une seule fois)

```bash
pip install gspread google-auth requests google-api-python-client
```

Fichiers nécessaires dans `tools/` (non commités, à récupérer séparément) :
- `tools/.env` — contient `PSI_API_KEY`
- `tools/credentials/service_account.json` — credentials Google API

### Usage mensuel

```bash
# Étape 1 — Collecte PSI → Google Sheets
python tools/webperf_runner.py

# Étape 2 — Sheets → tableaux Google Slides
python tools/slides_updater.py

# Étape 3 — Graphiques : ouvrir Slides → "Refresh all"
```

Pour un mois spécifique :
```bash
python tools/webperf_runner.py 2026-03
```

---

## Structure du projet

```
seo-ops/
├── app/                        # Flask task manager
│   ├── blueprints/
│   │   ├── tasks/              # CRUD tâches, export, generate
│   │   ├── templates/          # Templates récurrents
│   │   └── main/
│   ├── models.py               # Task, TaskTemplate
│   ├── static/                 # CSS + HTMX local
│   └── templates/              # Jinja2 partials
├── tools/                      # Scripts automation
│   ├── webperf_runner.py       # PSI → Google Sheets
│   ├── slides_updater.py       # Sheets → Google Slides
│   ├── ppt_generator.py        # Génération PPT local
│   ├── make_template.py        # Template PPT base
│   ├── webperf_template.pptx   # Template PPT
│   └── .env.example            # Variables requises (sans secrets)
├── workflows/
│   ├── reporting/CLAUDE.md     # Prompt système reporting hebdo
│   └── webperf/CLAUDE.md       # Prompt système webperf mensuel
├── inputs/                     # Fichiers Excel (gitignored)
├── output/                     # Rapports générés (gitignored)
├── tasks/                      # Exports .txt tâches (gitignored)
├── instance/                   # SQLite DB (gitignored)
├── run.py
└── requirements.txt
```

---

## Variables d'environnement

### `seo-ops/.env` (Task Manager)

```bash
SECRET_KEY=
DATABASE_URL=sqlite:///seo_ops.db
FLASK_ENV=development
```

### `tools/.env` (Scripts automation)

```bash
PSI_API_KEY=          # Google PageSpeed Insights API
SPREADSHEET_ID=       # Google Sheets WebPerf
SLIDES_ID=            # Google Slides WebPerf
```

Voir `tools/.env.example` pour le détail complet.
