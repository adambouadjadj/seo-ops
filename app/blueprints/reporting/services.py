import re
from pathlib import Path
from datetime import date, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # seo-ops/
INPUTS_DIR = PROJECT_ROOT / 'inputs'
TASKS_DIR = PROJECT_ROOT / 'tasks'
OUTPUT_DIR = PROJECT_ROOT / 'output'


def _current_friday() -> date:
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7
    return today + timedelta(days=days_until_friday)


def _extract_date_from_filename(filename: str) -> str | None:
    """Try to extract a DD-MM-YY date pattern from a filename."""
    m = re.search(r'(\d{2})[-_](\d{2})[-_](\d{2,4})', filename)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)[-2:]}'
    return None


def stage_files(monitorank_file, gsc_file, task_filename: str) -> dict:
    """Save uploaded files to inputs/ using the standard naming convention.

    Naming: 'Suivi positionnement AB DD-MM-YY.xlsx' and 'GSC performance AB DD-MM-YY.xlsx'.
    The date is extracted from the uploaded filename or derived from the current Friday.
    Returns {'monitorank': Path, 'gsc': Path, 'task': Path|None, 'week_label': str}.
    """
    INPUTS_DIR.mkdir(exist_ok=True)

    raw_date = _extract_date_from_filename(monitorank_file.filename or '')
    if not raw_date:
        raw_date = _extract_date_from_filename(gsc_file.filename or '')
    if not raw_date:
        raw_date = _current_friday().strftime('%d-%m-%y')

    mono_name = f'Suivi positionnement AB {raw_date}.xlsx'
    gsc_name = f'GSC performance AB {raw_date}.xlsx'
    mono_path = INPUTS_DIR / mono_name
    gsc_path = INPUTS_DIR / gsc_name

    monitorank_file.save(str(mono_path))
    gsc_file.save(str(gsc_path))

    task_path = (TASKS_DIR / task_filename) if task_filename else None

    return {
        'monitorank': mono_path,
        'gsc': gsc_path,
        'task': task_path,
        'week_label': raw_date,
    }


def get_available_task_files() -> list:
    """List tasks/*.txt sorted by modification time desc.

    Returns [(filename, label)] where label is a human-readable date.
    """
    if not TASKS_DIR.exists():
        return []
    files = sorted(
        TASKS_DIR.glob('*.txt'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for f in files:
        # task_16_02_26.txt → 16/02/26
        label = f.stem.replace('task_', '').replace('_', '/')
        result.append((f.name, label))
    return result


def get_past_reports() -> list:
    """List paired reporting HTML + MD files from output/ sorted by date desc.

    Returns [{'name', 'html_path', 'md_path', 'date'}].
    """
    if not OUTPUT_DIR.exists():
        return []

    html_files = {
        f.name.replace('_email.html', ''): f
        for f in OUTPUT_DIR.glob('reporting_*_email.html')
    }
    md_files = {
        f.stem: f
        for f in OUTPUT_DIR.glob('reporting_*.md')
    }

    all_keys = set(html_files) | set(md_files)
    reports = []
    for key in all_keys:
        html_f = html_files.get(key)
        md_f = md_files.get(key)
        m = re.search(r'(\d{2}-\d{2}-\d{2,4})$', key)
        date_str = m.group(1) if m else key
        reports.append({
            'name': key,
            'html_path': html_f.name if html_f else None,
            'md_path': md_f.name if md_f else None,
            'date': date_str,
        })

    reports.sort(key=lambda r: r['date'], reverse=True)
    return reports
