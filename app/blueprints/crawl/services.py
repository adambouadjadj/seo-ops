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
    """Return the most recently modified crawl HTML report filename."""
    if not OUTPUT_DIR.exists():
        return None
    html_files = sorted(
        OUTPUT_DIR.glob('crawl_*.html'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return html_files[0].name if html_files else None


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def get_past_crawls() -> list:
    """List crawl HTML reports from output/crawl_reports/, sorted by date desc."""
    if not OUTPUT_DIR.exists():
        return []

    html_files = sorted(
        OUTPUT_DIR.glob('crawl_*.html'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    crawls = []
    for html_f in html_files:
        stem = html_f.stem  # e.g. crawl_abcroisiere_05-03-26
        md_f = OUTPUT_DIR / (stem + '.md')
        m = re.search(r'(\d{2}-\d{2}-\d{2,4})$', stem)
        date_str = m.group(1) if m else stem
        slug_match = re.match(r'crawl_(.+?)_\d{2}-\d{2}-\d{2,4}$', stem)
        slug = slug_match.group(1) if slug_match else stem
        crawls.append({
            'html_path': html_f.name,
            'md_path': md_f.name if md_f.exists() else None,
            'slug': slug,
            'date': date_str,
        })
    return crawls
