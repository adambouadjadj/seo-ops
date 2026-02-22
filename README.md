# SEO Ops

Task manager local pour le suivi hebdomadaire des tâches SEO. Remplace les post-its par une web app dark/pro qui exporte vers le workflow de reporting existant.

## Stack

- **Backend** : Flask 3.x + SQLAlchemy (SQLite local → PostgreSQL-ready)
- **Frontend** : HTMX + Jinja2 + CSS vanilla (dark theme)
- **Auth** : Flask-WTF (CSRF)

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/zhanpyu/seo-ops.git
cd seo-ops

# 2. Créer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
cp .env.example .env  # puis éditer .env avec ta SECRET_KEY

# 5. Lancer
python run.py
```

Ouvrir [http://localhost:5000](http://localhost:5000)

## Configuration `.env`

```bash
SECRET_KEY=<générer avec: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:///seo_ops.db
FLASK_ENV=development
```

## Fonctionnalités

- **Tâches hebdomadaires** — CRUD complet, statuts (à faire / en cours / fait), catégories, priorités
- **Navigation par semaine** — historique consultable, export par semaine
- **Templates récurrents** — 8 tâches SEO pré-configurées, générées en un clic chaque lundi
- **Report de tâches** — les tâches manuelles non terminées sont proposées en carry-over la semaine suivante
- **Export `.txt`** — format compatible avec le workflow de reporting Claude (`tasks/task_DD_MM_YY.txt`)

## Structure

```
app/
├── blueprints/
│   ├── tasks/          # CRUD tâches + export + generate
│   ├── templates/      # Gestion des templates récurrents
│   └── main/           # Redirect /
├── models.py           # Task, TaskTemplate
├── static/             # CSS dark theme + HTMX local
└── templates/          # Jinja2 partials HTMX

tools/                  # Scripts Python existants (reporting, webperf, slides)
workflows/              # CLAUDE.md par workflow
```

## Workflow hebdomadaire

1. Lundi → cliquer **⟳ Récurrentes** pour générer les tâches de la semaine
2. Au fil de la semaine → ajouter les tâches au fil de l'eau, mettre à jour les statuts
3. Vendredi → cliquer **↓ Exporter .txt** → fichier prêt pour le reporting Claude

## Migration vers PostgreSQL

Changer une seule ligne dans `.env` :

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```
