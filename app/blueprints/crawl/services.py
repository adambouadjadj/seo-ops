import re
import sys
import threading
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # seo-ops/
OUTPUT_DIR = PROJECT_ROOT / 'output' / 'crawl_reports'

_jobs: dict = {}
_lock = threading.Lock()


def start_crawl(url: str) -> str:
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    with _lock:
        _jobs[job_id] = {
            'status': 'running',
            'output': '',
            'error': '',
            'started_at': datetime.now(),
            'url': url,
            'report': None,
        }
    t = threading.Thread(target=_run_crawl, args=(job_id, url), daemon=True)
    t.start()
    return job_id


def _run_crawl(job_id: str, url: str) -> None:
    try:
        result = subprocess.run(
            [sys.executable, 'tools/sf_crawler.py', '--url', url],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600,
        )
        # Find the HTML report generated for this crawl
        report_file = _find_latest_report()
        with _lock:
            if result.returncode == 0:
                _jobs[job_id].update({
                    'status': 'done',
                    'output': result.stdout,
                    'error': result.stderr,
                    'report': report_file,
                })
            else:
                _jobs[job_id].update({
                    'status': 'error',
                    'output': result.stdout,
                    'error': result.stderr,
                })
    except subprocess.TimeoutExpired:
        with _lock:
            _jobs[job_id].update({
                'status': 'error',
                'error': 'Timeout dépassé (1h)',
            })
    except Exception as exc:
        with _lock:
            _jobs[job_id].update({
                'status': 'error',
                'error': str(exc),
            })


def _find_latest_report() -> str | None:
    """Return the most recently modified crawl HTML report, as a path relative to OUTPUT_DIR."""
    if not OUTPUT_DIR.exists():
        return None
    # New structure: inside subfolders; old structure: flat
    candidates = list(OUTPUT_DIR.glob('*/crawl_*.html')) + list(OUTPUT_DIR.glob('crawl_*.html'))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(latest.relative_to(OUTPUT_DIR))


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def get_past_crawls() -> list:
    """
    List crawl HTML reports sorted by date desc.
    Handles both new (subfolder) and old (flat) structures.
    Returns paths relative to OUTPUT_DIR so routes can serve them safely.
    """
    if not OUTPUT_DIR.exists():
        return []

    # Collect all HTML reports: nested (new) + flat (old), deduplicate by stem
    by_stem: dict = {}
    for html_f in OUTPUT_DIR.glob('*/crawl_*.html'):
        by_stem[html_f.stem] = html_f
    for html_f in OUTPUT_DIR.glob('crawl_*.html'):
        if html_f.stem not in by_stem:  # flat only if no nested version
            by_stem[html_f.stem] = html_f

    html_files = sorted(by_stem.values(), key=lambda p: p.stat().st_mtime, reverse=True)

    crawls = []
    for html_f in html_files:
        stem = html_f.stem
        md_f = html_f.with_suffix('.md')
        m = re.search(r'(\d{2}-\d{2}-\d{2,4})$', stem)
        date_str = m.group(1) if m else stem
        slug_match = re.match(r'crawl_(.+?)_\d{2}-\d{2}-\d{2,4}$', stem)
        slug = slug_match.group(1) if slug_match else stem
        crawls.append({
            'html_path': str(html_f.relative_to(OUTPUT_DIR)),
            'md_path': str(md_f.relative_to(OUTPUT_DIR)) if md_f.exists() else None,
            'slug': slug,
            'date': date_str,
        })
    return crawls
