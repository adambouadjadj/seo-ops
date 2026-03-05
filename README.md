# SEO Ops Toolkit

An end-to-end SEO automation suite built for real operational workflows: weekly reporting, technical crawl analysis, and monthly web performance tracking — all driven by scripts and a local web dashboard.

---

## What's inside

| Tool | Cadence | Description |
|---|---|---|
| **Task Manager** (Flask web app) | Daily | Track weekly SEO tasks, manage recurring checklists, export to reporting |
| **Weekly SEO Reporting** | Weekly | Auto-generate structured reporting emails from rank tracking + GSC exports |
| **Crawl Analysis** | On-demand | Run Screaming Frog via CLI, parse CSVs, generate full SEO health reports |
| **Monthly WebPerf** | Monthly | PageSpeed Insights → Google Sheets → Google Slides, fully automated |

---

## Stack

- **Backend:** Python, Flask 3.x, SQLAlchemy
- **Frontend:** HTMX, Jinja2, vanilla CSS (dark theme)
- **Automation:** pandas, gspread, Google APIs (Sheets, Slides, Drive, PSI)
- **Crawl:** Screaming Frog SEO Spider (CLI mode) + custom CSV parser
- **AI-assisted reporting:** Claude (prompt-driven reporting from structured exports)

---

## 1. Task Manager

A lightweight Flask web app to manage weekly SEO tasks with recurring templates and one-click export.

### Setup

```bash
git clone https://github.com/zhanpyu/seo-ops.git
cd seo-ops

python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

cp .env.example .env         # fill in your values
python run.py
```

Open [http://localhost:5000](http://localhost:5000)

### `.env` required

```bash
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:///seo_ops.db
FLASK_ENV=development
```

### Weekly workflow

1. **Monday** — click **Recurring** to generate the 8 recurring tasks for the week
2. **Throughout the week** — add tasks, update statuses
3. **Friday** — click **Export .txt** → feeds directly into the reporting workflow

---

## 2. Weekly SEO Reporting

Generates a structured HTML reporting email from rank tracking exports (Monitorank) and Google Search Console data.

### Inputs

| File | Path |
|---|---|
| Rank tracking export | `inputs/ranking_DD-MM-YY.xlsx` |
| GSC export | `inputs/gsc_DD-MM-YY.xlsx` |
| Weekly tasks | `tasks/task_DD_MM_YY.txt` (from Task Manager) |

### Usage

Open Claude Code in the `seo-ops/` directory with `workflows/reporting/CLAUDE.md` loaded, provide the 3 input files.

### Output

- `output/reporting/reporting_DD-MM-YY.md` — Markdown archive
- `output/reporting/reporting_DD-MM-YY_email.html` — Outlook-ready HTML (open in browser → Ctrl+A → paste into Outlook)

---

## 3. Crawl Analysis (Screaming Frog CLI)

Runs a full Screaming Frog crawl via CLI and generates a comprehensive SEO health report in Markdown and HTML.

### Usage

```bash
python tools/sf_crawler.py https://example.com
```

### What it analyzes

- HTTP status codes (4xx, 5xx)
- Page titles — missing, duplicates, length issues
- H1 tags — missing, duplicates
- Meta descriptions — missing, duplicates, length issues
- Canonical tags — missing, non-self-referencing
- Crawl depth distribution + pages buried beyond depth 5
- Internal linking — orphan pages, inlink counts
- Images — missing alt text
- Fasteryze/cache noise filtering (auto-removes false positives from `?frz-` parameters)

### Output

```
output/crawl_reports/
├── crawl_SITE_DD-MM-YY.md
├── crawl_SITE_DD-MM-YY.html
└── SITE_DD-MM-YY/
    ├── interne_tous.csv
    ├── codes_de_réponse_tous.csv
    └── ...
```

---

## 4. Monthly WebPerf

Collects PageSpeed Insights scores for strategic URLs and pushes them directly into a Google Sheets + Google Slides reporting deck.

### Prerequisites

```bash
pip install gspread google-auth requests google-api-python-client
```

Files required in `tools/` (not committed — obtain separately):
- `tools/.env` — contains `PSI_API_KEY`, `SPREADSHEET_ID`, `SLIDES_ID`
- `tools/credentials/service_account.json` — Google service account key

### Monthly run

```bash
# Step 1 — Collect PSI scores → push to Google Sheets
python tools/webperf_runner.py

# Step 2 — Pull from Sheets → update Google Slides tables
python tools/slides_updater.py

# Step 3 — Open Slides → Refresh all (linked charts)
```

For a specific month:
```bash
python tools/webperf_runner.py 2026-03
```

---

## Project Structure

```
seo-ops/
├── app/                          # Flask task manager
│   ├── blueprints/
│   │   ├── tasks/                # Task CRUD, export, recurring
│   │   ├── reporting/            # Reporting workflow UI
│   │   ├── crawl/                # Crawl trigger + results UI
│   │   └── main/
│   ├── models.py                 # Task, TaskTemplate
│   ├── static/                   # CSS + local HTMX
│   └── templates/                # Jinja2 templates
├── tools/                        # Automation scripts
│   ├── sf_crawler.py             # Screaming Frog CLI + report generator
│   ├── webperf_runner.py         # PSI → Google Sheets
│   ├── slides_updater.py         # Sheets → Google Slides
│   └── .env.example
├── workflows/
│   ├── reporting/CLAUDE.md       # Reporting prompt system
│   ├── webperf/CLAUDE.md         # WebPerf prompt system
│   └── crawl/CLAUDE.md           # Crawl prompt system
├── inputs/                       # Excel exports (gitignored)
├── output/                       # Generated reports (gitignored)
├── tasks/                        # Task exports (gitignored)
├── run.py
└── requirements.txt
```

---

## Environment Variables

### `seo-ops/.env` (Task Manager)

```bash
SECRET_KEY=
DATABASE_URL=sqlite:///seo_ops.db
FLASK_ENV=development
```

### `tools/.env` (Automation scripts)

```bash
PSI_API_KEY=          # Google PageSpeed Insights API
SPREADSHEET_ID=       # Google Sheets ID
SLIDES_ID=            # Google Slides ID
```

See `tools/.env.example` for the full reference.
