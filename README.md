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
| **GSC Native** | On-demand | Search Console API: Insights, cannibalization detection, Tracker J+7/14/30/60 |
| **Backlink Gap** | On-demand | Babbar API: competitor gap analysis, quality scoring, outreach export |
| **iTools Redirects** | On-demand | Playwright: bulk 301/410 import into Karavel CMS via browser automation |
| **URL Catalogue** | On-demand | 485 categorized internal URLs for structured internal linking |
| **SL Optimizer** (Claude Code skill) | On-demand | AI-powered landing page generation: SERP analysis → pattern selection → content → SEO/GEO validation |

---

## Stack

- **Backend:** Python, Flask 3.x, SQLAlchemy
- **Frontend:** HTMX, Jinja2, vanilla CSS (dark theme)
- **Automation:** pandas, gspread, Google APIs (Sheets, Slides, Drive, PSI)
- **Crawl:** Screaming Frog SEO Spider (CLI mode) + custom CSV parser
- **AI-assisted reporting:** Claude (prompt-driven reporting from structured exports)
- **Search Console:** Google Search Console API (Search Analytics, OAuth via service account)
- **Backlinks:** Babbar API (domain authority, backlink gap analysis)
- **Browser automation:** Playwright Chromium (headless CMS form filling)
- **Content AI:** DataForSEO API (SERP analysis, PAA extraction), Textguru API (semantic briefs)

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

## 5. GSC Native (Search Console Blueprint)

A Flask blueprint that connects directly to the Google Search Console API — no manual exports needed.

### Features

- **Insights** — top queries by clicks/impressions with cannibalization detection (multiple URLs ranking for the same query)
- **Tracker** — add strategic pages and track their GSC performance over time: J+7, J+14, J+30, J+60 snapshots stored in SQLite
- **Auto-fetch** — one-click GSC export from the Reporting UI replaces manual CSV downloads

### Setup

Add to `tools/.env`:

```bash
GSC_SITE_URL=https://www.example.com/
```

Requires a Google service account with Search Console access and the `webmasters.readonly` scope.

---

## 6. Backlink Gap Analysis

Identifies competitor backlink opportunities using the Babbar API.

```bash
# Compare your backlinks against competitors
python tools/backlink_gap.py --competitors https://competitor1.com https://competitor2.com

# Group analysis (multiple sites per group)
python tools/backlink_gap.py --groups group_config.json

# Enrich results with domain authority scoring
python tools/backlink_gap_enrich.py --input output/backlink_gap.csv
```

### Output

- `output/backlink_gap.csv` — domains linking to competitors but not to your site
- `output/backlink_gap_enriched.csv` — enriched with Babbar authority scores, sorted by opportunity value

Requires `BABBAR_API_KEY` in `tools/.env`.

---

## 7. iTools Redirects (CMS Automation)

Automates bulk 301/410 redirect imports into the Karavel CMS using Playwright Chromium. Handles Vaadin form interactions that can't be scripted with simple HTTP requests.

```bash
# Full batch
python scripts/itools_redirects.py --file scripts/mapping_redirects.csv --mode 301

# Resume interrupted batch from log
python scripts/itools_redirects.py --file scripts/mapping.csv --mode resume --log scripts/logs/itools_2026-05-06.csv

# Dry run (limit to first N rows)
python scripts/itools_redirects.py --file scripts/mapping.csv --mode 410 --limit 5
```

Requires `ITOOLS_*` credentials in `tools/.env`.

---

## 8. URL Catalogue

Builds a structured catalogue of 485 internal URLs categorized by type (destination, company, cruise line, ship, port…) for use in internal linking workflows.

```bash
python scripts/catalogue_builder.py
```

Output: `output/catalogue_urls.json` — used by the SL Optimizer skill to resolve internal links.

---

## 9. SL Optimizer (Claude Code Skill)

A 12-module Claude Code skill that automates the production of SEO landing pages (SLs) from brief to validated HTML output.

### Pipeline

```
Brief (YAML)
  → 1. Content fetch (live URL scrape)
  → 2. Diagnostics (H1/meta/links audit)
  → 3. Textguru brief (semantic targets: SOSEO/DSEO, PAA, entities)
  → 4. SERP analysis (DataForSEO: top 20, featured snippet, PAA)
  → 5. Pattern selection (A: dense prose / B: structured / C: minimal)
  → 6. FAQ decision (add FAQ block if PAA signal strong enough)
  → 7. Data assembly (merge all signals into generation context)
  → 7bis. Link resolver (map entities to catalogue URLs)
  → 8. Content generation (Claude — top content + destination content)
  → 9a. SEO validation (20 hard checks: title/meta length, H structure, links, bold keyword…)
  → 9b. GEO validation (7 signals: entity density, concrete figures, FAQ microdata, author signature…)
  → 10. Output (9 files: HTML, title/meta, SEO/GEO reports, maillage gaps, metadata)
```

### Usage

```bash
# In Claude Code
/sl-optimize
```

Provide the brief path when prompted. The skill runs interactively, asking for confirmation at key steps.

### Output files per run

| File | Contents |
|---|---|
| `full_cms_ready.html` | Top + destination HTML, ready for CMS paste |
| `title_meta.txt` | Title and meta description with character counts |
| `bilan_seo.md` | SEO validation results (20 checks, pass/fail) |
| `bilan_geo.md` | GEO/LLM-readiness score (7 signals, informational) |
| `diagnostic_report.md` | Pre-generation anomalies (current page audit) |
| `maillage_manquant.md` | Named entities without a catalogue URL (link gap opportunities) |
| `metadata.json` | Full run metadata (pattern, scores, timestamps) |

Requires `YTG_API` (Textguru) and `DATAFORSEO_*` credentials in `tools/.env`.

---

## Project Structure

```
seo-ops/
├── app/                          # Flask web app (7 blueprints)
│   ├── blueprints/
│   │   ├── tasks/                # Task CRUD, export, recurring
│   │   ├── reporting/            # Reporting workflow UI + GSC auto-fetch
│   │   ├── crawl/                # Screaming Frog trigger + results
│   │   ├── webperf/              # PSI + Slides + monthly recap
│   │   ├── gsc/                  # Search Console: Insights + Tracker
│   │   └── main/
│   ├── models.py                 # Task, TaskTemplate, TrackedPage, PageSnapshot
│   ├── static/                   # CSS + local HTMX
│   └── templates/                # Jinja2 templates
├── tools/                        # Automation scripts
│   ├── sf_crawler.py             # Screaming Frog CLI + report generator
│   ├── webperf_runner.py         # PSI → Google Sheets
│   ├── slides_updater.py         # Sheets → Google Slides
│   ├── webperf_recap.py          # WebPerf N vs N-1 markdown recap
│   ├── gsc_client.py             # Google Search Console API wrapper
│   ├── backlink_check.py         # Single domain backlink check (Babbar)
│   ├── backlink_gap.py           # Competitor gap analysis (Babbar)
│   ├── backlink_gap_enrich.py    # Enrich gap results with authority scores
│   ├── check_410.py              # Batch 410 status checker
│   ├── sl_opportunity_scanner.py # Detect SL cannibalization from GSC data
│   ├── netoffice_filler.py       # Timesheet automation (Playwright)
│   └── .env.example
├── scripts/
│   ├── catalogue_builder.py      # Build 485-URL internal link catalogue
│   └── itools_redirects.py       # Bulk 301/410 import in Karavel CMS (Playwright)
├── .claude/skills/               # Claude Code automation skills
│   └── sl-optimize/              # SL content generation (12 modules)
│       ├── SKILL.md              # Skill entrypoint and instructions
│       ├── runner.py             # Orchestrator (steps 1–10)
│       ├── modules/              # 12 Python modules
│       └── reference/            # SL anatomy, patterns, brand constraints, examples
├── inputs/                       # Excel/CSV exports (gitignored)
├── output/                       # Generated reports and HTML (gitignored)
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
GSC_SITE_URL=         # Google Search Console property URL
BABBAR_API_KEY=       # Babbar API (backlink analysis)
YTG_API=              # Textguru API (semantic briefs for SL optimizer)
DATAFORSEO_LOGIN=     # DataForSEO login (SERP analysis)
DATAFORSEO_PASSWORD=  # DataForSEO password
ITOOLS_URL=           # Karavel iTools CMS URL
ITOOLS_USER=          # iTools login
ITOOLS_PASS=          # iTools password
```

See `tools/.env.example` for the full reference.
